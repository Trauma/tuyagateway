"""Device data and validation (WIP)."""


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

    def __init__(self, gismo_dict: dict = None, topic_config=True):
        """Initialize Device."""
        # TODO: message and topic should come in as separate params

        self.topic_config = topic_config
        if not gismo_dict:
            # device from db
            return

        if not self.topic_config:
            self._set_gc_config(gismo_dict)
        self._set_mqtt_topic()

    def _set_key(self, deviceid: str):
        """Set the deviceid for the device."""
        self.key = deviceid

    def _set_protocol(self, protocol: str):
        """Set the protocol for the device."""
        if protocol in ["3.1", "3.3"]:
            self.protocol = protocol
            return
        raise Exception("Unsupported protocol.")

    def _set_localkey(self, localkey: str):
        """Set the localkey for the device."""
        self.localkey = localkey

    def _set_ip_address(self, ip_address: str):
        """Set the ip address for the device."""
        # TODO: check format
        self.ip_address = ip_address

    def _set_gc_config(self, gismo_dict: dict):
        # validate device
        if "localkey" not in gismo_dict:
            return
        self._set_localkey(gismo_dict["localkey"])
        if "deviceid" not in gismo_dict:
            return
        self._set_key(gismo_dict["deviceid"])
        if "ip" not in gismo_dict:
            return
        self._set_ip_address(gismo_dict["ip"])

        if "protocol" in gismo_dict:
            self._set_protocol(gismo_dict["protocol"])
        if "pref_status_cmd" in gismo_dict:
            self._set_pref_status_cmd(gismo_dict["pref_status_cmd"])

        for data_point in gismo_dict["dps"]:
            dp_key = int(data_point["key"])
            self.attributes["dps"][dp_key] = None
            self.attributes["via"][dp_key] = "mqtt"
            if _validate_data_point_config(data_point):
                self._input_sanitize[dp_key] = data_point
                if "type_value" not in data_point:
                    return
                # uhm? What?
                self._output_type = data_point["type_value"]

        self.is_valid = True

    def _set_pref_status_cmd(self, pref_status_cmd: int):

        if pref_status_cmd in [10, 13]:
            self.pref_status_cmd = pref_status_cmd

    def _set_mqtt_topic(self):
        self.mqtt_topic = (
            f"tuya/{self.protocol}/{self.key}/{self.localkey}/{self.ip_address}"
        )
        if not self.topic_config:
            self.mqtt_topic = f"tuya/{self.key}"

    def get_tuya_payload(self, dp_key: int = None):
        """Get the sanitized Tuya command message payload."""
        if dp_key:
            return self._get_tuya_dp_payload(dp_key)
        return self._mqtt_payload

    def _get_tuya_dp_payload(self, dp_key: int):
        """Get the sanitized Tuya command message payload for data point."""
        return self._mqtt_payload[dp_key]

    def get_mqtt_payload(self, dp_key: int = None):
        """Get the sanitized MQTT reply message payload."""
        if dp_key:
            return self._get_mqtt_dp_payload(dp_key)
        return self._tuya_payload

    def _get_mqtt_dp_payload(self, dp_key: int):
        """Get the sanitized MQTT reply message payload for data point."""
        return self._tuya_payload[dp_key]

    def set_tuya_message(self, data: dict, dp_key: int = None, via: str = "mqtt"):
        """Set the Tuya reply message payload."""

        if dp_key:
            self._set_tuya_dp_message(data, dp_key, via)
            return
        for (dp_idx, dp_data) in data.items():
            self._set_tuya_dp_message(dp_data, dp_idx, via)

    def _set_tuya_dp_message(self, data: dict, dp_key: int, via: str):
        """Set the Tuya reply message payload for data point."""
        # TODO: sanitize message and add to _tuya_payload
        # we don't know what endpoint expects.
        # read ha discover / put data in gc discover?
        self._tuya_payload[dp_key] = data

    def set_mqtt_message(self, data, dp_key: int = None):
        """Set the MQTT command message payload."""
        if dp_key:
            self._set_mqtt_dp_message(data, dp_key)
            return
        # TODO: parse json and check if we have dict
        for (dp_idx, dp_data) in data.items():
            self._set_mqtt_dp_message(dp_data, dp_idx)

    def _set_mqtt_dp_message(self, data: bytes, dp_key: int):
        """Set the MQTT command message payload for data point."""

        if dp_key not in self.attributes["dps"]:
            self.attributes["dps"][dp_key] = None
        if dp_key not in self.attributes["via"]:
            self.attributes["via"][dp_key] = "mqtt"

        self._mqtt_payload[dp_key] = self._sanitize_mqtt_input(dp_key, data)

    def _sanitize_mqtt_input(self, dp_key: int, payload: bytes):

        # set defaults for topic config devices
        if dp_key not in self._input_sanitize:
            self._input_sanitize[dp_key] = {"type_value": "bool"}
            self._output_type = "bool"

        input_sanitize = self._input_sanitize[dp_key]
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
        self._set_key(device["deviceid"])
        self._set_localkey(device["localkey"])
        self._set_ip_address(device["ip"])
        if "attributes" in device:
            self.attributes = device["attributes"]
        self.is_valid = True
        self._set_mqtt_topic()

        for data_point in self.attributes["dps"]:
            self.attributes["dps"][data_point] = None
            self.attributes["via"][data_point] = "mqtt"
