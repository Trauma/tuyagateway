"""TuyaMQTT."""
import time
import paho.mqtt.client as mqtt
import json
import queue
import threading
import logging
from .cmdline import ARGS
import database
from tuyaface.tuyaclient import TuyaClient


LOGLEVEL = logging.INFO
if ARGS.ll == "INFO":
    LOGLEVEL = logging.INFO
elif ARGS.ll == "WARN":
    LOGLEVEL = logging.WARN
elif ARGS.ll == "ERROR":
    LOGLEVEL = logging.ERROR
elif ARGS.ll == "DEBUG":
    LOGLEVEL = logging.DEBUG

logging.basicConfig(
    format="%(asctime)s %(levelname)-8s (%(threadName)s) [%(name)s] %(message)s",
    level=LOGLEVEL,
)
logger = logging.getLogger(__name__)


def connack_string(state):
    """Return mqtt connection string."""
    states = [
        "Connection successful",
        "Connection refused - incorrect protocol version",
        "Connection refused - invalid client identifier",
        "Connection refused - server unavailable",
        "Connection refused - bad username or password",
        "Connection refused - not authorised",
    ]
    return states[state]


def payload_bool(payload: str):
    """Convert string to boolean."""
    str_payload = str(payload.decode("utf-8"))
    if str_payload in ("True", "ON", "1"):
        return True
    if str_payload in ("False", "OFF", "0"):
        return False
    return payload


def bool_payload(config: dict, boolvalue: bool):
    """Convert boolean to payload value."""
    # TODO: get from entity
    if boolvalue:
        return config["General"]["payload_on"]
    return config["General"]["payload_off"]


def bool_availability(config: dict, boolvalue: bool):
    """Convert boolean to payload value."""
    # TODO: get from entity
    if boolvalue:
        return config["General"]["availability_online"]
    return config["General"]["availability_offline"]


class TuyaMQTTEntity(threading.Thread):
    """Run thread for device."""

    delay = 0.1

    def __init__(self, key, entity, parent):
        """Initialize TuyaMQTTEntity."""
        super().__init__()
        self.key = key
        self.name = key  # Set thread name to key

        self.entity = entity
        self.parent = parent
        self.config = self.parent.config

        self.tuya_discovery = False
        self.mqtt_topic = f"{self.config['General']['topic']}/{entity['protocol']}/{entity['deviceid']}/{entity['localkey']}/{entity['ip']}"
        if "tuya_discovery" in entity and entity["tuya_discovery"]:
            self.tuya_discovery = True
            self.mqtt_topic = f"{self.config['General']['topic']}/{entity['deviceid']}"

        self.availability = False
        self.tuya_client = None
        self.stop = threading.Event()
        self.mqtt_client = mqtt.Client()

        self.command_queue = queue.Queue()

    def mqtt_connect(self):
        """Create MQTT client."""
        self.mqtt_client.enable_logger()
        if self.config["MQTT"]["user"] and self.config["MQTT"]["pass"]:
            self.mqtt_client.username_pw_set(
                self.config["MQTT"]["user"], self.config["MQTT"]["pass"]
            )
        self.mqtt_client.will_set(
            f"{self.mqtt_topic}/availability",
            bool_availability(self.config, False),
            retain=True,
        )
        self.mqtt_client.connect_async(
            self.config["MQTT"].get("host", "127.0.0.1"),
            int(self.config["MQTT"].get("port", 1883)),
            60,
        )
        self.mqtt_client.on_connect = self.on_mqtt_connect
        self.mqtt_client.on_message = self.on_mqtt_message
        self.mqtt_client.loop_start()

    def on_mqtt_message(self, client, userdata, message):
        """MQTT message callback, executed in the MQTT client's context."""
        if message.topic[-4:] == "kill":
            self.stop_entity()

        if message.topic[-7:] != "command":
            return

        logging.debug(
            "(%s) topic %s retained %s message received %s",
            self.entity["ip"],
            message.topic,
            message.retain,
            str(message.payload.decode("utf-8")),
        )

        # We're in the MQTT client's context, queue a call to handle the message
        self.command_queue.put((self._handle_mqtt_message, (message,)))

    def _handle_mqtt_message(self, message):

        # will give problem with custom topics
        entity_parts = message.topic.split("/")
        dps_key = str(entity_parts[len(entity_parts) - 2])

        if dps_key not in self.entity["attributes"]["dps"]:
            self._set_dps(dps_key, None)
        if dps_key not in self.entity["attributes"]["via"]:
            self._set_via(dps_key, "mqtt")
        self.set_state(dps_key, payload_bool(message.payload))

    def on_mqtt_connect(self, client, userdata, flags, return_code):
        """MQTT connect callback, executed in the MQTT client's context."""
        logger.info(
            "MQTT Connection state: %s for %s",
            connack_string(return_code),
            self.mqtt_topic,
        )
        client.subscribe(f"{self.mqtt_topic}/#")

    def _set_dps(self, dps_key, dps_value: str):

        self.entity["attributes"]["dps"][dps_key] = dps_value
        self.parent.set_entity_dps_item(self.key, dps_key, dps_value)

    def _set_via(self, dps_key, via: str):

        self.entity["attributes"]["via"][dps_key] = via
        self.parent.set_entity_via_item(self.key, dps_key, via)

    def _set_availability(self, availability: bool):

        if availability != self.availability:
            self.availability = availability
            logger.debug("->publish %s/availability", self.mqtt_topic)
            self.mqtt_client.publish(
                f"{self.mqtt_topic}/availability",
                bool_availability(self.config, availability),
                retain=True,
            )

    def _process_data(self, data: dict, via: str, force_mqtt: bool = False):

        changed = force_mqtt

        for dps_key, dps_value in data["dps"].items():

            if dps_key not in self.entity["attributes"]["dps"]:
                self._set_dps(dps_key, None)
            logger.debug(
                "(%s) _process_data %s : %s", self.entity["ip"], dps_key, dps_value
            )

            if dps_key not in self.entity["attributes"]["via"]:
                self._set_via(dps_key, "init")
            if dps_value != self.entity["attributes"]["dps"][dps_key] or force_mqtt:
                changed = True
                self._set_dps(dps_key, dps_value)

                logger.debug(
                    "(%s) ->publish %s/%s/state",
                    self.entity["ip"],
                    self.mqtt_topic,
                    dps_key,
                )
                self.mqtt_client.publish(
                    f"{self.mqtt_topic}/{dps_key}/state",
                    bool_payload(self.config, dps_value),
                )

                if via != self.entity["attributes"]["via"][dps_key]:
                    self._set_via(dps_key, via)

                attr_item = {
                    "dps": self.entity["attributes"]["dps"][dps_key],
                    "via": self.entity["attributes"]["via"][dps_key],
                    "time": time.time(),
                }

                logger.debug(
                    "(%s) ->publish %s/%s/attributes",
                    self.entity["ip"],
                    self.mqtt_topic,
                    dps_key,
                )
                self.mqtt_client.publish(
                    f"{self.mqtt_topic}/{dps_key}/attributes", json.dumps(attr_item)
                )

        if changed:
            attr = {
                "dps": self.entity["attributes"]["dps"],
                "via": self.entity["attributes"]["via"],
                "time": time.time(),
            }

            logger.debug(
                "(%s) ->publish %s/attributes", self.entity["ip"], (self.mqtt_topic)
            )
            self.mqtt_client.publish(f"{self.mqtt_topic}/attributes", json.dumps(attr))

    def on_tuya_status(self, data: dict):
        """Tuya status message callback."""
        # TODO: via is broken. When state command comes in from mqtt via should be mqtt
        self._process_data(data, "tuya")

    def on_tuya_connected(self, connected: bool):
        """Tuya connection state updated."""
        self._set_availability(connected)
        # We're in TuyaClient's context, queue a call to tuyaclient.status
        self.command_queue.put((self.request_status, ("mqtt", True)))

    def request_status(self, via: str = "tuya", force_mqtt: bool = False):
        """Poll Tuya device for status."""
        try:
            data = self.tuya_client.status()

            if not data:
                return

            self._process_data(data, via, force_mqtt)

        except Exception:
            logger.exception("(%s) status request error", self.entity["ip"])

    def set_state(self, dps_item, payload):
        """Set state of Tuya device."""
        try:
            result = self.tuya_client.set_state(payload, dps_item)
            if not result:
                logger.error(
                    "(%s) set_state request on topic %s failed",
                    self.entity["ip"],
                    self.mqtt_topic,
                )

        except Exception:
            logger.error(
                "(%s) set_state request on topic %s",
                self.entity["ip"],
                self.mqtt_topic,
                exc_info=True,
            )

    def run(self):
        """Tuya MQTTEntity main loop."""
        self.mqtt_connect()
        self.tuya_client = TuyaClient(
            self.entity, self.on_tuya_status, self.on_tuya_connected
        )
        self.tuya_client.start()

        while not self.stop.is_set():
            while not self.command_queue.empty():
                command, args = self.command_queue.get()
                command(*args)

            time.sleep(self.delay)

    def stop_entity(self):
        """Shut down MQTT client, TuyaClient and worker thread."""
        logger.info("Stopping TuyaMQTTEntity %s", self.name)
        self.tuya_client.stop_client()
        self.mqtt_client.loop_stop()
        self.stop.set()
        self.join()


class TuyaMQTT:
    """Manages a set of TuyaMQTTEntities."""

    delay = 0.1
    config = []
    dict_entities = {}
    worker_threads = {}

    def __init__(self, config):
        """Initialize TuyaMQTTEntity."""
        self.config = config
        # TODO: set fixed, not need to be dynamic here
        self.mqtt_topic = config["General"]["topic"]
        self.mqtt_client = mqtt.Client()

        self.database = database
        self.database.setup()

    def mqtt_connect(self):
        """Create MQTT client."""
        self.mqtt_client.enable_logger()
        if self.config["MQTT"]["user"] and self.config["MQTT"]["pass"]:
            self.mqtt_client.username_pw_set(
                self.config["MQTT"]["user"], self.config["MQTT"]["pass"]
            )
        self.mqtt_client.connect_async(
            self.config["MQTT"].get("host", "127.0.0.1"),
            int(self.config["MQTT"].get("port", 1883)),
            60,
        )
        self.mqtt_client.on_connect = self.on_mqtt_connect
        self.mqtt_client.on_message = self.on_mqtt_message
        self.mqtt_client.loop_start()

    def on_mqtt_connect(self, client, userdata, flags, return_code):
        """Write something useful."""
        logger.info(
            "MQTT Connection state: %s for topic %s",
            connack_string(return_code),
            self.mqtt_topic,
        )
        client.subscribe(f"{self.mqtt_topic}/#")

    def write_entities(self):
        """Write entities to database."""
        self.database.upsert_entities(self.dict_entities)

    def read_entity(self):
        """Read entities from database."""
        self.dict_entities = self.database.get_entities()

    def add_entity_dict_topic(self, entity_raw, retain):
        """Write something useful."""
        entity_parts = entity_raw.split("/")

        key = entity_parts[2]

        if key in self.dict_entities:
            return False

        entity = {
            "protocol": entity_parts[1],
            "deviceid": entity_parts[2],
            "localkey": entity_parts[3],
            "ip": entity_parts[4],
            "attributes": {"dps": {}, "via": {}},
            "hass_discover": False,
        }

        self.dict_entities[key] = entity
        self.database.insert_entity(entity)
        return key

    def add_entity_dict_discovery(self, key: str, entity: dict):
        """Write something useful."""
        if key in self.dict_entities:
            self.database.delete_entity(self.dict_entities[key])

        self.dict_entities[key] = entity
        return key

    def get_entity(self, key):
        """Get entity data for key."""
        return self.dict_entities[key]

    def set_entity_dps_item(self, key, dps, value):
        """Write something useful."""
        self.dict_entities[key]["attributes"]["dps"][dps] = value
        self.database.update_entity(self.dict_entities[key])

    def set_entity_via_item(self, key, dps, value):
        """Write something useful."""
        self.dict_entities[key]["attributes"]["via"][dps] = value
        self.database.update_entity(self.dict_entities[key])

    def on_mqtt_message(self, client, userdata, message):
        """MQTT message callback, executed in the MQTT client's context."""
        topic_parts = message.topic.split("/")

        if topic_parts[1] == "discovery":
            if message.payload == b"":
                return
            print(message.payload)
            # TODO: kill thread on payload None -- isn't received -> trigger reload from mqttdevices
            entity = json.loads(message.payload)
            print(message.topic, entity)

            entity["attributes"] = {"dps": {}, "via": {}}
            self.add_entity_dict_discovery(topic_parts[2], entity)

            logger.info(
                "discovery message received %s topic %s retained %s ",
                str(message.payload.decode("utf-8")),
                message.topic,
                message.retain,
            )
            thread_object = TuyaMQTTEntity(topic_parts[2], entity, self)
            thread_object.setName(topic_parts[2])
            thread_object.start()
        # return

        # will be removed eventually
        if message.topic[-7:] != "command":
            return

        key = self.add_entity_dict_topic(message.topic, message.retain)

        if key:
            logger.info(
                "topic config message received %s topic %s retained %s ",
                str(message.payload.decode("utf-8")),
                message.topic,
                message.retain,
            )
            entity = self.get_entity(key)

            thread_object = TuyaMQTTEntity(key, entity, self)
            thread_object.start()
            self.worker_threads[key] = thread_object

    def main_loop(self):
        """Send / receive from tuya devices."""
        try:
            self.mqtt_connect()
            self.read_entity()

            for key, entity in self.dict_entities.items():
                thread_object = TuyaMQTTEntity(key, entity, self)
                thread_object.start()
                self.worker_threads[key] = thread_object

            time_run_save = 0

            while True:
                if time.time() > time_run_save:
                    self.write_entities()
                    time_run_save = time.time() + 300

                time.sleep(self.delay)
        except KeyboardInterrupt:
            for key, thread in self.worker_threads.items():
                thread.stop_entity()
                thread.join()
