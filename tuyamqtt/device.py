"""Device data and validation (WIP)."""
import json


def _validate_data_point_config(data_point: dict) -> bool:

    if "type_value" not in data_point:
        return False
    if data_point["type_value"] not in ["bool", "str", "int", "float"]:
        return False

    if data_point["type_value"] in ["str", "int", "float"] and (
        "maximal" not in data_point or "minimal" not in data_point
    ):
        return False
    if data_point["type_value"] in ["str", "int", "float"]:
        if data_point["maximal"] > data_point["minimal"]:
            return False
    return True


def payload_bool(payload: str):
    """Convert string to boolean."""
    str_payload = str(payload.decode("utf-8"))
    if str_payload in ["True", "true", "TRUE", "ON", "On", "on", "1"]:
        return True
    return False


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
    _input_sanitize = {}
    _output_type = "bool"
    _mqtt_payload = {}
    _tuya_payload = {}

    def __init__(self, message, topic_config=False):
        """Initialize Device."""
        self.topic_config = topic_config
        if message == "":
            # device from db
            return

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

        # validate device
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
            self.attributes["dps"][int(data_point["key"])] = None
            self.attributes["via"][int(data_point["key"])] = "mqtt"
            if _validate_data_point_config(data_point):
                self._input_sanitize[int(data_point["key"])] = data_point
                if "type_value" not in data_point:
                    return
                self._output_type = data_point["type_value"]

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

    def get_tuya_payload(self):
        """Get the sanitized Tuya command message payload."""
        return self._mqtt_payload

    def get_mqtt_payload(self):
        """Get the sanitized MQTT reply message payload."""
        return self._tuya_payload

    def get_tuya_dp_payload(self, data_point_key: int):
        """Get the sanitized Tuya command message payload for data point."""
        return self._mqtt_payload[data_point_key]

    def get_mqtt_dp_payload(self, data_point_key: int):
        """Get the sanitized MQTT reply message payload for data point."""
        return self._tuya_payload[data_point_key]

    def set_tuya_message(self, message, via: str):
        """Set the Tuya reply message payload."""
        # TODO: sanitize message and add to _tuya_payload

    def set_mqtt_message(self, message):
        """Set the MQTT command message payload."""
        # will give problems with topics without dp key
        # e.g. /<topic>/command which is invalid but would pass the filter
        entity_parts = message.topic.split("/")
        data_point_key = int(entity_parts[len(entity_parts) - 2])
        if data_point_key not in self.attributes["dps"]:
            self.attributes["dps"][data_point_key] = None
        if data_point_key not in self.attributes["via"]:
            self.attributes["via"][data_point_key] = "mqtt"

        self._mqtt_payload[data_point_key] = self._sanitize_mqtt_input(
            data_point_key, message.payload
        )

    def _sanitize_mqtt_input(self, data_point_key: int, payload):

        # set defaults for topic config devices
        if data_point_key not in self._input_sanitize:
            self._input_sanitize[data_point_key] = {"type_value": "bool"}
            self._output_type = "bool"

        input_sanitize = self._input_sanitize[data_point_key]
        if input_sanitize["type_value"] == "bool":
            return payload_bool(payload)
        if input_sanitize["type_value"] == "str":
            tmp_payload = payload
            if len(payload) > input_sanitize["maximal"]:
                tmp_payload = payload[: input_sanitize["maximal"]]
            return tmp_payload
        if input_sanitize["type_value"] == "int":
            tmp_payload = int(payload)
        elif input_sanitize["type_value"] == "float":
            tmp_payload = float(payload)
        return max(
            input_sanitize["minimal"], min(tmp_payload, input_sanitize["maximal"])
        )

    def get_legacy_device(self) -> dict:
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
        self.topic_config = True
        self.is_valid = True
        self._set_mqtt_topic()

        for data_point in self.attributes["dps"]:
            self.attributes["dps"][data_point] = None
            self.attributes["via"][data_point] = "mqtt"
