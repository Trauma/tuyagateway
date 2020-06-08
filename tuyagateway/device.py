"""Device data and validation (WIP)."""


def _validate_dp_config(data_point: dict) -> bool:

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


def str_bool(payload: str) -> bool:
    """Convert string to boolean."""
    str_payload = str(payload.decode("utf-8"))
    if str_payload in ["TRUE", "True", "true", "ON", "On", "on", "1"]:
        return True
    return False


# TODO: should be mapped to expected topic output
# could use ha config if we understand the context
# would make the app a 1 trick pony
def bool_str(payload: bool) -> str:
    """Convert boolean to string."""
    if payload:
        return "True"
    return "False"


def convert(input_type: str, output_type: str, data):
    """Select the converter function."""
    if input_type == "str":
        if output_type == "bool":
            return str_bool(data)
    if input_type == "bool":
        if output_type == "str":
            return bool_str(data)
    if output_type == "int":
        return int(data)
    if output_type == "float":
        return float(data)
    return data


class DeviceDataPoint:
    """Tuya I/O datapoint processing."""

    _sanitized_input_data = False
    _sanitized_output_data = False
    _state_data = {"via": "tuya", "changed": False}
    _validated_dp_config = {"type_value": "bool"}
    is_valid = False
    state_changed = False

    def __init__(self, data_point: dict = None):
        """Initialize DeviceDataPoint."""
        if not data_point:
            data_point = {}

        if _validate_dp_config(data_point):
            self._validated_dp_config = data_point
            self.is_valid = True

    def get_state(self, key: str):
        """Get state of datapoint."""
        # TODO:check key
        return self._state_data[key]

    def get_tuya_dp_payload(self):
        """Get the sanitized Tuya command message payload for data point."""
        return self._sanitized_input_data

    def get_mqtt_dp_response(self, oud=None):
        """Get the sanitized MQTT reply message payload for data point."""
        return self._sanitized_output_data

    def _sanitize_data_point(self, payload: bytes):

        input_sanitize = self._validated_dp_config
        if input_sanitize["type_value"] == "bool":
            return bool(payload)
        if input_sanitize["type_value"] == "str":
            if len(payload) > input_sanitize["maximal"]:
                return payload[: input_sanitize["maximal"]]
            return payload
        if input_sanitize["type_value"] == "int":
            tmp_payload = int(payload)
        elif input_sanitize["type_value"] == "float":
            tmp_payload = float(payload)
        return max(
            input_sanitize["minimal"], min(tmp_payload, input_sanitize["maximal"])
        )

    def set_tuya_dp_payload(self, data: dict, via: str):
        """Set the Tuya reply message payload for data point."""

        # TMP
        if self._validated_dp_config["type_value"] == "bool":
            data = bool_str(data)

        sanitized_data = self._sanitize_data_point(data)

        self.state_changed = False
        self._state_data["changed"] = False

        if sanitized_data != self._sanitized_output_data:
            self._state_data = {"via": via, "changed": True}
            self.state_changed = True
            self._sanitized_output_data = sanitized_data
            # overwrite old value for next compare
            self._sanitized_input_data = sanitized_data

    def set_mqtt_dp_request(self, data: bytes, input_topic: str):
        """Set the MQTT command message payload for data point."""
        # TMP
        if self._validated_dp_config["type_value"] == "bool":
            data = str_bool(data)

        self._sanitized_input_data = self._sanitize_data_point(data)


class Device:
    """Tuya I/O processing."""

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
    _validated_dp_config = {}
    _output_type = "bool"
    _sanitized_input_data = {}
    _sanitized_output_data = {}
    _state_data = {}
    _state_changed = False
    discovery = None
    _data_points = {}

    _topic_type_mapping = {
        "availability": "str",
        "command": "str",
        "state": "str",
        "set_position": "int",
        "position": "int",
        "tilt_command": "int",
        "attributes": "str",
    }

    def __init__(self, gismo_dict: dict = None, topic_config=True):
        """Initialize Device."""
        self.topic_config = topic_config
        if not gismo_dict:
            # device from db
            return
        self.discovery = gismo_dict

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

        for dp_key, data_point in gismo_dict["dps"].items():
            # dp_key = int(data_point["key"])
            dp_key_int = int(dp_key)

            if _validate_dp_config(data_point):
                self._validated_dp_config[dp_key_int] = data_point
                self._init_data_point(dp_key_int, data_point)

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
        # if dp_key:
        #     return self._get_tuya_dp_payload(dp_key)
        # return self._sanitized_input_data
        if dp_key:
            return self._data_points[dp_key].get_tuya_dp_payload()
        payload = {}
        for dp_idx, dp_item in self._data_points.items():
            payload[dp_idx] = dp_item.get_tuya_dp_payload()
        return payload

    def _get_tuya_dp_payload(self, dp_key: int):
        """Get the sanitized Tuya command message payload for data point."""
        return self._sanitized_input_data[dp_key]

    def get_mqtt_response(self, dp_key: int = None, output_topic: str = "state"):
        """Get the sanitized MQTT reply message payload."""
        if output_topic != "attributes":
            if dp_key:
                # return self._get_mqtt_dp_response(dp_key, output_topic)
                return self._data_points[dp_key].get_mqtt_dp_response(output_topic)
            return

        if dp_key:
            # return {
            #     "dps": self._get_mqtt_dp_response(dp_key, output_topic),
            #     "via": self._state_data[dp_key]["via"],
            # }
            return {
                "dps": self._data_points[dp_key].get_mqtt_dp_response(output_topic),
                "via": self._data_points[dp_key].get_state("via"),
            }

        attributes_dict = {"via": {}, "dps": {}, "changed": {}}
        for (
            dp_idx,
            data,  # pylint: disable=unused-variable
        ) in self._sanitized_output_data.items():
            # attributes_dict["dps"][dp_idx] = self._get_mqtt_dp_response(
            #     dp_idx, output_topic
            # )#self._data_points[dp_idx].get_mqtt_dp_response(output_topic)
            # attributes_dict["via"][dp_idx] = self._state_data[dp_idx]["via"]#self._data_points[dp_idx]["via"]
            # attributes_dict["changed"][dp_idx] = self._state_data[dp_idx]["changed"]#self._data_points[dp_idx]["changed"]
            attributes_dict["dps"][dp_idx] = self._data_points[
                dp_idx
            ].get_mqtt_dp_response(output_topic)
            attributes_dict["via"][dp_idx] = self._data_points[dp_idx].get_state("via")
            attributes_dict["changed"][dp_idx] = self._data_points[dp_idx].get_state(
                "changed"
            )

        return attributes_dict

    def _get_mqtt_dp_response(self, dp_key: int, output_topic: str):
        """Get the sanitized MQTT reply message payload for data point."""
        return self._sanitized_output_data[dp_key]
        # return convert(
        #     self._validated_dp_config[dp_key]["type_value"],
        #     self._topic_type_mapping[output_topic],
        #     self._sanitized_output_data[dp_key],
        # )

    def set_tuya_payload(self, data: dict, dp_key: int = None, via: str = "tuya"):
        """Set the Tuya reply message payload."""

        if dp_key:
            # self._set_tuya_dp_payload(data, dp_key, via)
            self._data_points[dp_key].set_tuya_dp_payload(data, via)
            return

        if not isinstance(data, dict):
            raise ValueError("dict expected.")
        if "dps" not in data:
            raise Exception("No data point values found.")

        for (dp_idx, dp_data) in data["dps"].items():  # pylint: disable=unused-variable
            # self._set_tuya_dp_payload(dp_data, int(dp_idx), via)
            self._init_data_point(int(dp_idx))
            self._data_points[int(dp_idx)].set_tuya_dp_payload(data, via)

    def _set_tuya_dp_payload(self, data: dict, dp_key: int, via: str):
        """Set the Tuya reply message payload for data point."""

        self._init_data_point(dp_key)

        sanitized_data = self._sanitize_data_point(dp_key, data)

        self._state_data[dp_key]["changed"] = False
        self._state_changed = False

        if sanitized_data != self._sanitized_output_data[dp_key]:
            self._state_data[dp_key] = {"via": via, "changed": True}
            self._state_changed = True
            self._sanitized_output_data[dp_key] = sanitized_data
            # overwrite old value for next compare
            self._sanitized_input_data[dp_key] = sanitized_data

    def set_mqtt_request(self, data, dp_key: int = None, input_topic: str = "command"):
        """Set the MQTT command message payload."""
        if dp_key:
            # self._set_mqtt_dp_request(data, dp_key, input_topic)
            self._data_points[dp_key].set_mqtt_dp_request(data, input_topic)
            return

        if not isinstance(data, dict):
            raise ValueError("dict expected.")
        if "dps" not in data:
            raise Exception("No data point values found.")

        for (dp_idx, dp_data) in data["dps"].items():  # pylint: disable=unused-variable
            # self._set_mqtt_dp_request(dp_data, dp_idx, input_topic)
            self._data_points[dp_idx].set_mqtt_dp_request(data, input_topic)

    def _set_mqtt_dp_request(self, data: bytes, dp_key: int, input_topic: str):
        """Set the MQTT command message payload for data point."""
        self._init_data_point(dp_key)

        self._sanitized_input_data[dp_key] = self._sanitize_data_point(
            dp_key,
            convert(
                self._topic_type_mapping[input_topic],
                self._validated_dp_config[dp_key]["type_value"],
                data,
            ),
        )

    def _sanitize_data_point(self, dp_key: int, payload: bytes):

        input_sanitize = self._validated_dp_config[dp_key]
        if input_sanitize["type_value"] == "bool":
            return bool(payload)
        if input_sanitize["type_value"] == "str":
            if len(payload) > input_sanitize["maximal"]:
                return payload[: input_sanitize["maximal"]]
            return payload
        if input_sanitize["type_value"] == "int":
            tmp_payload = int(payload)
        elif input_sanitize["type_value"] == "float":
            tmp_payload = float(payload)
        return max(
            input_sanitize["minimal"], min(tmp_payload, input_sanitize["maximal"])
        )

    def get_legacy_device(self) -> dict:
        """Support for old structure."""
        # TODO: get attributes from sanitized
        # attributes = {"via": {}, "dps": {}, "changed": {}}
        attributes = self.get_mqtt_response(output_topic="attributes")
        # for dp_key, dp_value in self._sanitized_output_data.items():
        #     attributes["via"][dp_key] = self._state_data[dp_key]["via"]
        #     attributes["dps"][dp_key] = dp_value
        #     attributes["changed"][dp_key] = self._state_data[dp_key]["changed"]

        return {
            "protocol": self.protocol,
            "deviceid": self.key,
            "localkey": self.localkey,
            "ip": self.ip_address,
            "attributes": attributes,
            "topic_config": self.topic_config,
            "pref_status_cmd": self.pref_status_cmd,
        }

    def set_legacy_device(self, device: dict):
        """Support for old structure."""
        attributes = {"via": {}, "dps": {}, "changed": {}}
        self._set_protocol(device["protocol"])
        self._set_key(device["deviceid"])
        self._set_localkey(device["localkey"])
        self._set_ip_address(device["ip"])
        if "attributes" in device:
            attributes = device["attributes"]
        self.is_valid = True
        self._set_mqtt_topic()

        for dp_key in attributes["dps"]:
            self._init_data_point(int(dp_key))

    def _init_data_point(self, dp_key: int, data_point: dict = None):

        if dp_key not in self._sanitized_input_data:
            self._sanitized_input_data[dp_key] = False
        if dp_key not in self._sanitized_output_data:
            self._sanitized_output_data[dp_key] = False
        if dp_key not in self._state_data:
            self._state_data[dp_key] = {"via": "tuya", "changed": False}
        if dp_key not in self._validated_dp_config:
            self._validated_dp_config[dp_key] = {"type_value": "bool"}

        self._data_points[dp_key] = DeviceDataPoint(data_point)
