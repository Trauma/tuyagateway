"""TuyaMQTT."""
import time
import sys
import paho.mqtt.client as mqtt
import json
import queue
import threading
import logging
from .cmdline import ARGS
import database

try:
    if ARGS.ttf:
        from tuya.tuyaface.tuyaclient import TuyaClient
    else:
        from tuyaface.tuyaclient import TuyaClient
except Exception as ex:
    print(ex)
    sys.exit()

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
        """Initialize thread."""
        super().__init__()
        self.key = key

        self.entity = entity
        self.parent = parent
        self.config = self.parent.config

        self.tuya_discovery = False
        self.mqtt_topic = f"{self.config['General']['topic']}/{entity['protocol']}/{entity['deviceid']}/{entity['localkey']}/{entity['ip']}"
        if "tuya_discovery" in entity and entity["tuya_discovery"]:
            self.tuya_discovery = True
            self.mqtt_topic = f"{self.config['General']['topic']}/{entity['deviceid']}"

        self.mqtt_connected = False
        self.availability = False
        self.client = None
        self.stop = threading.Event()
        self.mqtt_client = None

        self.command_queue = queue.Queue()

    def mqtt_connect(self):
        """Write something useful."""
        try:
            self.mqtt_client = mqtt.Client()
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
            self.mqtt_client.connect(
                self.config["MQTT"].get("host", "127.0.0.1"),
                int(self.config["MQTT"].get("port", 1883)),
                60,
            )
            self.mqtt_client.on_connect = self.on_connect
            self.mqtt_client.loop_start()
            self.mqtt_client.on_message = self.on_message

        except Exception as ex:
            logger.warning(
                "(%s) Failed to connect to MQTT Broker %s", self.entity["ip"], ex
            )
            self.mqtt_connected = False

    def on_message(self, client, userdata, message):
        """Write something useful."""
        if message.topic[-4:] == "kill":
            self.client.stop_client()
            self.stop.set()
            self.join()
            return

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

    def on_connect(self, client, userdata, flags, return_code):
        """Write something useful."""
        logger.info(
            "MQTT Connection state: %s for %s",
            connack_string(return_code),
            self.mqtt_topic,
        )
        client.subscribe(f"{self.mqtt_topic}/#")
        self.mqtt_connected = True

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

    def on_status(self, data: dict):
        """Write something useful."""
        # TODO: via is broken. When state command comes in from mqtt via should be mqtt
        self._process_data(data, "tuya")

    def on_connection(self, connected: bool):
        """Write something useful."""
        self._set_availability(connected)
        # We're in TuyaClient's context, queue a call to tuyaclient.status
        self.command_queue.put((self.status, ("mqtt", True)))

    def status(self, via: str = "tuya", force_mqtt: bool = False):
        """Write something useful."""
        try:
            data = self.client.status()

            if not data:
                return

            self._process_data(data, via, force_mqtt)

        except Exception:
            logger.exception("(%s) status request error", self.entity["ip"])

    def set_state(self, dps_item, payload):
        """Write something useful."""
        try:
            result = self.client.set_state(payload, dps_item)
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
        """Write something useful."""
        self.client = TuyaClient(self.entity, self.on_status, self.on_connection)
        self.client.start()

        while True:

            if not self.mqtt_connected:
                self.mqtt_connect()
                time.sleep(1)

            while not self.command_queue.empty():
                command, args = self.command_queue.get()
                command(*args)

            time.sleep(self.delay)


class TuyaMQTT:
    """Write something useful."""

    delay = 0.1
    config = []
    dict_entities = {}

    def __init__(self, config):
        """Write something useful."""
        self.config = config
        # TODO: set fixed, not need to be dynamic here
        self.mqtt_topic = config["General"]["topic"]
        self.mqtt_connected = False
        self.mqtt_client = None

        self.database = database
        self.database.setup()

    def mqtt_connect(self):
        """Write something useful."""
        try:
            self.mqtt_client = mqtt.Client()
            self.mqtt_client.enable_logger()
            if self.config["MQTT"]["user"] and self.config["MQTT"]["pass"]:
                self.mqtt_client.username_pw_set(
                    self.config["MQTT"]["user"], self.config["MQTT"]["pass"]
                )
            self.mqtt_client.connect(
                self.config["MQTT"].get("host", "127.0.0.1"),
                int(self.config["MQTT"].get("port", 1883)),
                60,
            )
            self.mqtt_client.on_connect = self.on_connect
            self.mqtt_client.loop_start()
            self.mqtt_client.on_message = self.on_message
        except Exception:
            logger.info("Failed to connect to MQTT Broker")
            self.mqtt_connected = False

    def on_connect(self, client, userdata, flags, return_code):
        """Write something useful."""
        logger.info(
            "MQTT Connection state: %s for topic %s",
            connack_string(return_code),
            self.mqtt_topic,
        )
        client.subscribe(f"{self.mqtt_topic}/#")
        self.mqtt_connected = True

    def write_entity(self):
        """Write something useful."""
        self.database.upsert_entities(self.dict_entities)

    def read_entity(self):
        """Write something useful."""
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
        """Write something useful."""
        return self.dict_entities[key]

    def set_entity_dps_item(self, key, dps, value):
        """Write something useful."""
        self.dict_entities[key]["attributes"]["dps"][dps] = value
        self.database.update_entity(self.dict_entities[key])

    def set_entity_via_item(self, key, dps, value):
        """Write something useful."""
        self.dict_entities[key]["attributes"]["via"][dps] = value
        self.database.update_entity(self.dict_entities[key])

    def on_message(self, client, userdata, message):
        """Write something useful."""
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
            thread_object.setName(key)
            thread_object.start()

    def main_loop(self):
        """Send / receive from tuya devices."""
        self.read_entity()

        tpool = []
        for key, entity in self.dict_entities.items():
            thread_object = TuyaMQTTEntity(key, entity, self)
            thread_object.setName(key)
            thread_object.start()
            tpool.append(thread_object)

        time_run_save = 0

        while True:

            if not self.mqtt_connected:
                self.mqtt_connect()
                time.sleep(2)
                continue

            if time.time() > time_run_save:
                self.write_entity()
                time_run_save = time.time() + 300

            time.sleep(self.delay)
