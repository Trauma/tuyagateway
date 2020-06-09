"""TuyaMQTT."""
import time
import paho.mqtt.client as mqtt
import json
import queue
import threading
import asyncio
from .configure import logger
from .device import Device
from tuyagateway import database
from tuyagateway.transform.homeassistant import Transform
from tuyaface.tuyaclient import TuyaClient


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
        return "online"  # config["General"]["availability_online"]
    return "offline"  # config["General"]["availability_offline"]


class TuyaMQTTEntity(threading.Thread):
    """Run thread for device."""

    delay = 0.1

    def __init__(self, key: str, entity: Device, transform: Transform, parent):
        """Initialize TuyaMQTTEntity."""
        super().__init__()
        self.key = key
        self.name = key  # Set thread name to key

        self.entity = entity
        self.parent = parent
        self.config = self.parent.config

        self.transform = transform

        self.mqtt_topic = entity.mqtt_topic

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
        # TODO: get avail topic
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
        if message.topic[-7:] != "command":
            return

        logger.debug(
            "(%s) topic %s retained %s message received %s",
            self.entity.ip_address,
            message.topic,
            message.retain,
            str(message.payload.decode("utf-8")),
        )

        # We're in the MQTT client's context, queue a call to handle the message
        self.command_queue.put((self._handle_mqtt_message, (message,)))

    def _handle_mqtt_message(self, message):

        # command from ha always str
        # device dp can be "any" type

        # TODO: transform payload for tuya
        entity_parts = message.topic.split("/")
        if entity_parts[len(entity_parts) - 2].isnumeric():
            dp_key = int(entity_parts[len(entity_parts) - 2])
            # payload in bytes
            self.entity.set_mqtt_request(message.payload, dp_key, "command")
            payload = self.entity.get_tuya_payload(dp_key)

            self.set_state(dp_key, payload)
            return

        try:
            payload_dict = json.loads(message.payload)
        except Exception:
            logger.exception("(%s) MQTT message, invalid json", self.entity.ip_address)

        self.entity.set_mqtt_request(payload_dict)
        payload = self.entity.get_tuya_payload()
        self.set_status(payload)

    def on_mqtt_connect(self, client, userdata, flags, return_code):
        """MQTT connect callback, executed in the MQTT client's context."""
        logger.info(
            "MQTT Connection state: %s for %s",
            connack_string(return_code),
            self.mqtt_topic,
        )

        topics = self.transform.get_subscribe_topics()
        # print(self.mqtt_topic, topics)
        if len(topics) != 0:
            client.subscribe(topics)
        else:
            client.subscribe(f"{self.mqtt_topic}/#")
        # pub_topics = self.transform.get_publish_topics()
        # print("pub_topics", self.mqtt_topic, pub_topics)

    def _set_availability(self, availability: bool):

        if availability == self.availability:
            return

        self.availability = availability
        logger.debug("->publish %s/availability", self.mqtt_topic)

        pub_content = self.transform.get_publish_content("availability", availability)
        done = False
        for item in pub_content:
            for subitem in item:
                # print("_set_availability",self.mqtt_topic, subitem)
                self.mqtt_client.publish(
                    subitem["topic"], subitem["payload"], retain=True,
                )
                done = True
        if done:
            return

        self.mqtt_client.publish(
            f"{self.mqtt_topic}/availability",
            bool_availability(self.config, availability),
            retain=True,
        )

    def on_tuya_connected(self, connected: bool):
        """Tuya connection state updated."""
        self._set_availability(connected)
        # We're in TuyaClient's context, queue a call to tuyaclient.status
        self.command_queue.put((self.request_status, ("mqtt", True)))

    def _mqtt_publish(self, topic: str, subtopic: str, payload: str):

        logger.debug("(%s) ->publish %s/%s", self.entity.ip_address, topic, subtopic)
        self.mqtt_client.publish(
            f"{topic}/{subtopic}", payload,
        )

    def _handle_status(self):

        sane_reply = self.entity.get_mqtt_response(output_topic="attributes")

        if True not in sane_reply["changed"].values():
            return
        self._mqtt_publish(self.mqtt_topic, "attributes", json.dumps(sane_reply))

        for dp_key, dp_value in sane_reply["changed"].items():
            if not dp_value:
                continue

            data_point_topic = f"{self.mqtt_topic}/{dp_key}"
            self._mqtt_publish(
                data_point_topic,
                "attributes",
                json.dumps(
                    self.entity.get_mqtt_response(dp_key, output_topic="attributes")
                ),
            )
            self._mqtt_publish(
                data_point_topic,
                "state",
                self.entity.get_mqtt_response(dp_key, output_topic="state"),
            )

    def on_tuya_status(self, data: dict, status_from: str):
        """Tuya status message callback."""
        via = "tuya"
        if status_from == "command":
            via = "mqtt"
        self.entity.set_tuya_payload(data, via=via)
        # self._handle_status()
        # TODO: let transform process the data
        # TODO: use right publish endpoint based on config
        pub_content = self.transform.get_publish_content("state")
        for item in pub_content:
            for subitem in item:
                self.mqtt_client.publish(subitem["topic"], subitem["payload"])

    def request_status(self, via: str = "tuya", force_mqtt: bool = False):
        """Poll Tuya device for status."""
        try:
            data = self.tuya_client.status()
            if not data:
                return
            self.entity.set_tuya_payload(data, via=via)
            self._handle_status()
            # TODO: let transform process the data
        except Exception:
            logger.exception("(%s) status request error", self.entity.ip_address)

    def _log_request_error(self, request_type: str):
        logger.error(
            "(%s) %s request on topic %s failed",
            self.entity.ip_address,
            request_type,
            self.mqtt_topic,
            exc_info=True,
        )

    def set_state(self, dps_item: int, payload):
        """Set state of Tuya device."""
        try:
            result = self.tuya_client.set_state(payload, dps_item)
            if not result:
                self._log_request_error("set_state")
        except Exception:
            self._log_request_error("set_state")

    def set_status(self, payload: dict):
        """Set status of Tuya device."""
        logger.warning(
            "(%s) set_status not implemented yet %s failed",
            self.entity.ip_address,
            self.mqtt_topic,
        )
        # try:
        #     result = self.tuya_client.set_status(payload)
        #     if not result:
        #         self._log_request_error("set_status")
        # except Exception:
        #     self._log_request_error("set_status")

    def run(self):
        """Tuya MQTTEntity main loop."""

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self.transform.update_config())
        finally:
            loop.close()

        self.mqtt_connect()
        self.tuya_client = TuyaClient(
            self.entity.get_legacy_device(), self.on_tuya_status, self.on_tuya_connected
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
    _transform = {}
    worker_threads = {}
    _ha_config = {}
    _ha_component = {}

    def __init__(self, config):
        """Initialize TuyaMQTTEntity."""
        self.config = config

        self.mqtt_topic = "tuya"
        self.mqtt_client = mqtt.Client()

        # TODO remove db
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
        client.subscribe(
            [(f"{self.mqtt_topic}/#", 0), ("homeassistant/#", 0), ("tuyagateway/#", 0)]
        )

    def write_entities(self):
        """Write entities to database."""
        for (
            key,  # pylint: disable=unused-variable
            device,
        ) in self.dict_entities.items():
            self.database.upsert_entity(device.get_legacy_device())

    def read_entities(self):
        """Read entities from database."""
        for (key, legacy_device) in self.database.get_entities().items():
            device = Device()
            device.set_legacy_device(legacy_device)
            transform = Transform(self, device)
            self._transform[key] = transform
            self.dict_entities[key] = device
            self._start_entity_thread(key, device, transform)

    def add_entity_dict_topic(self, device):
        """Write something useful."""
        entity_keys = self._find_entity_keys(device.key, device.ip_address)
        if len(entity_keys) != 0:
            return None

        self.dict_entities[device.key] = device
        self.database.insert_entity(device.get_legacy_device())
        return device.key

    def _start_entity_thread(self, key, entity, transform):
        thread_object = TuyaMQTTEntity(key, entity, transform, self)
        thread_object.setName(f"tuyagateway_{key}")
        thread_object.start()
        self.worker_threads[key] = thread_object

    def _find_entity_keys(self, key: str, ip_address=None):

        keys = []
        for ent_key, item in self.dict_entities.items():
            if item.ip_address == ip_address:
                keys.append(ent_key)

        if key in self.dict_entities:
            keys.append(key)

        return keys

    def _handle_discover_message(self, topic: dict, message):
        """Handle discover message from GismoCaster.

        If a discover message arrives we kill the thread for the
        device (if any), and restart with new config (if any)
        """

        logger.info(
            "discovery message received %s topic %s retained %s ",
            str(message.payload.decode("utf-8")),
            message.topic,
            message.retain,
        )

        discover_dict = {}
        try:
            if message.payload:
                discover_dict = json.loads(message.payload)
        except Exception as ex:
            print("_handle_discover_message", ex)
            return

        device_key = topic[2]
        device = Device(discover_dict, False)
        # TODO: check ha_publish
        transform = Transform(self, device)

        entity_keys = self._find_entity_keys(device_key, device.ip_address)

        for entity_key in entity_keys:
            self.database.delete_entity(
                self.dict_entities[entity_key].get_legacy_device()
            )

            if entity_key in self.worker_threads:
                try:
                    self.worker_threads[entity_key].stop_entity()
                    self.worker_threads[entity_key].join()
                except Exception:
                    pass

        if not device.is_valid():
            return
        self.dict_entities[device.key] = device
        self._transform[device.key] = transform
        self._start_entity_thread(device.key, device, transform)

    def _handle_command_message(self, message):

        device = Device()
        topic_parts = message.topic.split("/")
        device.set_legacy_device(
            {
                "protocol": topic_parts[1],
                "deviceid": topic_parts[2],
                "localkey": topic_parts[3],
                "ip": topic_parts[4],
            }
        )

        key = self.add_entity_dict_topic(device)
        if not key:
            return

        logger.info(
            "topic config message received %s topic %s retained %s ",
            str(message.payload.decode("utf-8")),
            message.topic,
            message.retain,
        )
        transform = Transform(self, device)
        self._transform[device.key] = transform
        self._start_entity_thread(device.key, device, transform)

    # TODO: test this, do we still need the db
    def _handle_command_message2(self, message):

        device = Device()
        topic_parts = message.topic.split("/")
        device.set_legacy_device(
            {
                "protocol": topic_parts[1],
                "deviceid": topic_parts[2],
                "localkey": topic_parts[3],
                "ip": topic_parts[4],
            }
        )

        entity_keys = self._find_entity_keys(device.key, device.ip_address)
        if len(entity_keys) != 0:
            return None

        self.dict_entities[device.key] = device

        logger.info(
            "topic config message received %s topic %s retained %s ",
            str(message.payload.decode("utf-8")),
            message.topic,
            message.retain,
        )
        transform = Transform(self, device)
        self._transform[device.key] = transform
        self._start_entity_thread(device.key, device, transform)

    async def get_ha_config(self, key: str, idx: int):
        """Get the HomeAssistant configuration."""
        # wait till conf available
        while key not in self._ha_config or idx not in self._ha_config[key]:
            asyncio.sleep(0.1)
        return self._ha_config[key][idx]

    def _handle_ha_config_message(self, topic: dict, message):
        if not message.payload:
            return

        try:
            ha_dict = json.loads(message.payload)
        except Exception as ex:
            print(ex)
            return
        # add context to ha_dict
        ha_dict["device_component"] = topic[1]

        if "uniq_id" not in ha_dict:
            # skip it for now
            return

        if topic[2] != ha_dict["uniq_id"]:
            return
        id_parts = ha_dict["uniq_id"].split("_")
        if id_parts[0] not in ha_dict["device"]["identifiers"]:
            return
        if id_parts[0] not in self._ha_config:
            self._ha_config[id_parts[0]] = {}
        if not id_parts[1].isnumeric():
            return
        id_int = int(id_parts[1])
        self._ha_config[id_parts[0]][id_int] = ha_dict

        if id_parts[0] in self._transform:
            self._transform[id_parts[0]].set_homeassistant_config(id_int, ha_dict)

    async def get_ha_component(self, key: str):
        """Get the HomeAssistant component configuration."""
        # wait till conf available
        while key not in self._ha_component:
            asyncio.sleep(0.1)
        return self._ha_component[key]

    def _handle_ha_component_message(self, topic: dict, message):

        logger.info(
            "config message topic %s retained %s ", message.topic, message.retain,
        )
        try:
            payload_dict = json.loads(message.payload)
        except Exception as ex:
            print(ex)

        component_name = topic[3]
        self._ha_component[component_name] = payload_dict

        for _, transform in self._transform.items():
            transform.set_component_config(payload_dict, component_name)

    def on_mqtt_message(self, client, userdata, message):
        """MQTT message callback, executed in the MQTT client's context."""
        topic_parts = message.topic.split("/")
        # print(topic_parts)
        if (
            topic_parts[0] == "homeassistant"
            and topic_parts[len(topic_parts) - 1] == "config"
        ):
            self._handle_ha_config_message(topic_parts, message)
            return
        if topic_parts[0] == "tuyagateway":

            if topic_parts[1] == "config" and topic_parts[2] == "homeassistant":
                self._handle_ha_component_message(topic_parts, message)
                return

            if topic_parts[1] == "discovery":
                self._handle_discover_message(topic_parts, message)
                return
        # will be removed eventually

        if topic_parts[0] != "tuya":
            return

        if len(topic_parts) == 7 and topic_parts[6] == "command":
            self._handle_command_message(message)

    def main_loop(self):
        """Send / receive from tuya devices."""

        time_run_save = time.time() + 60
        try:

            self.read_entities()

            # wait for threads to be started before
            # opening up for changes
            self.mqtt_connect()

            while True:
                if time.time() > time_run_save:
                    # should really be locking dict_entities
                    self.write_entities()
                    time_run_save = time.time() + 300

                time.sleep(self.delay)
        except KeyboardInterrupt:
            for _, thread in self.worker_threads.items():
                thread.stop_entity()
                thread.join()
