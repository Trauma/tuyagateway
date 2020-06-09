"""DeviceThread."""
import time
import paho.mqtt.client as mqtt
import json
import queue
import threading
import asyncio
from .configure import logger
from .device import Device
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


def bool_availability(config: dict, boolvalue: bool):
    """Convert boolean to payload value."""
    # TODO: get from device
    if boolvalue:
        return "online"  # config["General"]["availability_online"]
    return "offline"  # config["General"]["availability_offline"]


class DeviceThread(threading.Thread):
    """Run thread for device."""

    delay = 0.1

    def __init__(self, key: str, device: Device, transform: Transform, parent):
        """Initialize DeviceThread."""
        super().__init__()
        self.key = key
        self.name = key  # Set thread name to key

        self._device = device
        self.parent = parent
        self.config = self.parent.config

        self.transform = transform

        self.mqtt_topic = device.mqtt_topic

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
            self._device.ip_address,
            message.topic,
            message.retain,
            str(message.payload.decode("utf-8")),
        )

        # We're in the MQTT client's context, queue a call to handle the message
        self.command_queue.put((self._handle_mqtt_message, (message,)))

    def _handle_mqtt_message(self, message):

        # TODO: transform payload for tuya
        entity_parts = message.topic.split("/")
        if entity_parts[len(entity_parts) - 2].isnumeric():
            dp_key = int(entity_parts[len(entity_parts) - 2])
            # payload in bytes
            self._device.set_mqtt_request(message.payload, dp_key, "command")
            payload = self._device.get_tuya_payload(dp_key)

            self.set_state(dp_key, payload)
            return

        try:
            payload_dict = json.loads(message.payload)
        except Exception:
            logger.exception("(%s) MQTT message, invalid json", self._device.ip_address)

        self._device.set_mqtt_request(payload_dict)
        payload = self._device.get_tuya_payload()
        self.set_status(payload)

    def on_mqtt_connect(self, client, userdata, flags, return_code):
        """MQTT connect callback, executed in the MQTT client's context."""
        logger.info(
            "MQTT Connection state: %s for %s",
            connack_string(return_code),
            self.mqtt_topic,
        )

        topics = self.transform.get_subscribe_topics()
        client.subscribe(topics)

    def _set_availability(self, availability: bool):

        if availability == self.availability:
            return

        self.availability = availability
        logger.debug("->publish %s/availability", self.mqtt_topic)

        pub_content = self.transform.get_publish_content("availability", availability)
        for item in pub_content:
            self.mqtt_client.publish(
                item["topic"], item["payload"], retain=True,
            )

    def on_tuya_connected(self, connected: bool):
        """Tuya connection state updated."""
        self._set_availability(connected)
        # We're in TuyaClient's context, queue a call to tuyaclient.status
        self.command_queue.put((self.request_status, ("mqtt", True)))

    def _mqtt_publish(self, topic: str, subtopic: str, payload: str):

        logger.debug("(%s) ->publish %s/%s", self._device.ip_address, topic, subtopic)
        self.mqtt_client.publish(
            f"{topic}/{subtopic}", payload,
        )

    def on_tuya_status(self, data: dict, status_from: str):
        """Tuya status message callback."""
        via = "tuya"
        if status_from == "command":
            via = "mqtt"
        self._device.set_tuya_payload(data, via=via)
        # TODO: let transform process the data
        # TODO: use right publish endpoint based on config
        pub_content = self.transform.get_publish_content("state")
        for item in pub_content:
            self.mqtt_client.publish(item["topic"], item["payload"])

    def request_status(self, via: str = "tuya", force_mqtt: bool = False):
        """Poll Tuya device for status."""
        try:
            data = self.tuya_client.status()
            if not data:
                return
            self._device.set_tuya_payload(data, via=via)

            # TODO: let transform process the data
            # TODO: use right publish endpoint based on config
            pub_content = self.transform.get_publish_content("state")
            for item in pub_content:
                self.mqtt_client.publish(item["topic"], item["payload"])
        except Exception:
            logger.exception("(%s) status request error", self._device.ip_address)

    def _log_request_error(self, request_type: str):
        logger.error(
            "(%s) %s request on topic %s failed",
            self._device.ip_address,
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
            self._device.ip_address,
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
            # print(self.key, "wait for config")
            loop.run_until_complete(self.transform.update_config())
        finally:
            loop.close()
            # print(self.key, self._device.ip_address, "config done")

        self.mqtt_connect()
        self.tuya_client = TuyaClient(
            self._device.get_tuyaface_device(),
            self.on_tuya_status,
            self.on_tuya_connected,
        )
        self.tuya_client.start()

        while not self.stop.is_set():

            while not self.command_queue.empty():
                command, args = self.command_queue.get()
                command(*args)

            time.sleep(self.delay)

    def stop_entity(self):
        """Shut down MQTT client, TuyaClient and worker thread."""
        logger.info("Stopping DeviceThread %s", self.name)
        self.tuya_client.stop_client()
        self.mqtt_client.loop_stop()
        self.stop.set()
        self.join()
