"""Device data and validation."""


def _validate_config(data_point: dict) -> bool:

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


class DeviceDataPoint:
    """Tuya I/O datapoint processing."""

    def __init__(self, data_point: dict = None):
        """Initialize DeviceDataPoint."""
        self._sanitized_input_data = None
        self._sanitized_output_data = None
        self._state_data = {"via": "tuya", "changed": False}
        self._validated_config = {"type_value": "bool"}
        self._is_valid = False
        if data_point is None:
            data_point = {}

        if _validate_config(data_point):
            self._validated_config = data_point
            self._is_valid = True

    def is_valid(self) -> bool:
        """Return true if the configuration validated."""
        return self._is_valid

    def get_state(self, key: str = None):
        """Get state of datapoint."""
        if key:
            if key in self._state_data:
                return self._state_data[key]
            return
        return self._state_data

    def get_device_payload(self):
        """Get the sanitized Tuya command message payload for data point."""
        return self._sanitized_input_data

    def get_gateway_payload(self):
        """Get the sanitized MQTT reply message payload for data point."""
        return self._sanitized_output_data

    def _sanitize_data_point(self, payload):

        input_sanitize = self._validated_config
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

    def set_device_payload(self, data: dict, via: str):
        """Set the Tuya reply message payload for data point."""

        sanitized_data = self._sanitize_data_point(data)
        self._state_data["changed"] = False

        if sanitized_data != self._sanitized_output_data:
            self._state_data = {"via": via, "changed": True}

            self._sanitized_output_data = sanitized_data
            # overwrite old value for next compare
            self._sanitized_input_data = sanitized_data

    def set_gateway_payload(self, gw_payload):
        """Set the MQTT command message payload for data point."""
        self._sanitized_input_data = self._sanitize_data_point(gw_payload)


class Device:
    """Tuya I/O processing."""

    def __init__(self, device_dict: dict = None):
        """Initialize Device."""
        self._localkey = None
        self._protocol = "3.3"
        self._pref_status_cmd = 10
        self._is_valid = False
        self._key = None
        self._ip_address = None
        self._device_config = {}
        self._data_points = {}

        if not device_dict:
            return
        self._device_config = device_dict
        self._set_gc_config(device_dict)

    def get_ip_address(self) -> str:
        """Get the IP address of the device."""
        return self._ip_address

    def get_key(self) -> str:
        """Get the key of the device."""
        return self._key

    def get_config(self) -> dict:
        """Get the configuration of the device."""
        return self._device_config

    def is_valid(self) -> bool:
        """Return true if the configuration validated."""
        return self._is_valid

    def data_point(self, idx: int) -> DeviceDataPoint:
        """Return DeviceDataPoint."""
        if idx in self._data_points:
            return self._data_points[idx]

    def _set_key(self, deviceid: str):
        """Set the deviceid for the device."""
        self._key = deviceid

    def _set_protocol(self, protocol: str):
        """Set the protocol for the device."""
        if protocol in ["3.1", "3.3"]:
            self._protocol = protocol
            return
        raise Exception("Unsupported protocol.")

    def _set_localkey(self, localkey: str):
        """Set the localkey for the device."""
        self._localkey = localkey

    def _set_ip_address(self, ip_address: str):
        """Set the ip address for the device."""
        # TODO: check format
        self._ip_address = ip_address

    def _set_gc_config(self, device_dict: dict):
        # validate device
        if "localkey" not in device_dict:
            return
        self._set_localkey(device_dict["localkey"])
        if "deviceid" not in device_dict:
            return
        self._set_key(device_dict["deviceid"])
        if "ip" not in device_dict:
            return
        self._set_ip_address(device_dict["ip"])

        if "protocol" in device_dict:
            self._set_protocol(device_dict["protocol"])
        if "pref_status_cmd" in device_dict:
            self._set_pref_status_cmd(device_dict["pref_status_cmd"])

        for data_point in device_dict["dps"]:
            if _validate_config(data_point):
                self._init_data_point(data_point["key"], data_point)

        self._is_valid = True

    def _set_pref_status_cmd(self, pref_status_cmd: int):
        if pref_status_cmd in [10, 13]:
            self._pref_status_cmd = pref_status_cmd

    def get_device_payload(self) -> dict:
        """Get the sanitized Tuya command message payload."""
        payload = {}
        for dp_idx, dp_item in self._data_points.items():
            payload[str(dp_idx)] = dp_item.get_device_payload()
        return payload

    def set_device_payload(self, data: dict, via: str = "tuya"):
        """Set the Tuya reply message payload."""
        if "dps" not in data:
            raise Exception("No data point values found.")

        for (dp_idx, dp_data) in data["dps"].items():
            self._init_data_point(int(dp_idx))
            self._data_points[int(dp_idx)].set_device_payload(
                data["dps"][str(dp_idx)], via
            )

    def set_gateway_payload(self, gw_payload: dict):
        """Set the command message payload."""
        for (dp_idx, dp_gw_payload) in gw_payload.items():
            self._init_data_point(int(dp_idx))
            self._data_points[dp_idx].set_gateway_payload(dp_gw_payload)

    def get_gateway_payload(self) -> dict:
        """Get the payload of the device in gw format."""
        gw_payload = {}
        for (dp_idx, item,) in self._data_points.items():
            gw_payload[dp_idx] = item.get_gateway_payload()
        return gw_payload

    def get_device_state(self) -> dict:
        """Get the state of the device."""
        device_state = {}
        for (dp_idx, item,) in self._data_points.items():
            device_state[dp_idx] = item.get_state()
        return device_state

    def get_tuyaface_config(self) -> dict:
        """Return dict for TuyaFace configuration."""
        attributes_dict = {"via": {}, "dps": {}, "changed": {}}
        for (dp_idx, item,) in self._data_points.items():
            attributes_dict["dps"][dp_idx] = item.get_gateway_payload()
            attributes_dict["via"][dp_idx] = item.get_state("via")
            attributes_dict["changed"][dp_idx] = item.get_state("changed")

        return {
            "protocol": self._protocol,
            "deviceid": self._key,
            "localkey": self._localkey,
            "ip": self._ip_address,
            "attributes": attributes_dict,
            "pref_status_cmd": self._pref_status_cmd,
        }

    def _init_data_point(self, dp_key: int, data_point: dict = None):
        if dp_key in self._data_points:
            return
        self._data_points[dp_key] = DeviceDataPoint(data_point)
