"""Device data and validation (WIP)."""
import json


class Device:
    """Datacontainer for device."""

    key = None
    ip_address = None
    localkey = None
    protocol = "3.3"
    attributes = {"dps": {}, "via": {}}
    topic_config = False
    is_valid = False
    mqtt_topic = None
    pref_status_cmd = 10
    _topic_parts = []

    def __init__(self, message, topic_config=False):
        """Initialize Device."""
        self.topic_config = topic_config
        self._set_key(message.topic)
        if not self.topic_config:
            self._set_gc_config(message.payload)
        else:
            self._set_topic_config()
        self._set_mqtt_topic()

    def _set_key(self, topic):

        self._topic_parts = topic.split("/")
        self.key = self._topic_parts[2]

    def _set_gc_config(self, message):

        if message == b"":
            return
        device = json.loads(message)

        if "localkey" not in device:
            return
        self.localkey = device["localkey"]
        if "deviceid" not in device:
            return
        if device["deviceid"] != self.key:
            return
        if "ip" not in device:
            return
        self.ip_address = device["ip"]

        if "protocol" in device:
            self._set_protocol(device["protocol"])
        if "pref_status_cmd" in device:
            self._set_pref_status_cmd(device["pref_status_cmd"])

        for data_point in device["dps"]:
            self.attributes["dps"][str(data_point["key"])] = None
            self.attributes["via"][str(data_point["key"])] = "mqtt"

        # TODO check dp config

        self.is_valid = True

    def _set_topic_config(self):

        self._set_protocol(self._topic_parts[1])
        self.localkey = self._topic_parts[3]
        self.ip_address = self._topic_parts[4]

    def _set_pref_status_cmd(self, pref_status_cmd: int):

        if pref_status_cmd in [10, 13]:
            self.pref_status_cmd = pref_status_cmd

    def _set_protocol(self, protocol):
        if protocol in ["3.1", "3.3"]:
            self.protocol = protocol

    def _set_mqtt_topic(self):
        self.mqtt_topic = (
            f"tuya/{self.protocol}/{self.key}/{self.localkey}/{self.ip_address}"
        )
        if not self.topic_config:
            self.mqtt_topic = f"tuya/{self.key}"

    def get_legacy_device(self):
        """Support for old structure."""
        return {
            "protocol": self.protocol,
            "deviceid": self.key,
            "localkey": self.localkey,
            "ip": self.ip_address,
            "attributes": self.attributes,
            "topic_config": self.topic_config,
            "pref_status_cmd": self.pref_status_cmd,
        }

    def set_legacy_device(self, device: dict):
        """Support for old structure."""
        self._set_protocol(device["protocol"])
        self.key = device["deviceid"]
        self.localkey = device["localkey"]
        self.ip_address = device["ip"]
        self.attributes = device["attributes"]
        self.topic_config = device["topic_config"]
        self.is_valid = True
