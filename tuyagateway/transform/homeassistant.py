"""Transformer for Home assistant."""
import json
from ..device import Device


def _legacy_bool_payload(boolvalue: bool):
    """Convert boolean to payload value."""
    if boolvalue:
        return "On"
    return "Off"


def _legacy_bool_availability(boolvalue: bool):
    """Convert boolean to payload value."""
    if boolvalue:
        return "Online"
    return "Offline"


def _legacy_handle_status(device: Device):

    sane_reply = device.get_mqtt_response(output_topic="attributes")

    if True not in sane_reply["changed"].values():
        return
    # TODO: convert values
    # print(sane_reply["dps"].values())
    convert_reply = sane_reply
    convert_reply["dps"] = {
        k: _legacy_bool_payload(v) for k, v in sane_reply["dps"].items()
    }
    # print(convert_reply)
    _mqtt_publish(device.mqtt_topic, "attributes", json.dumps(convert_reply))

    for dp_key, dp_value in convert_reply["changed"].items():
        if not dp_value:
            continue

        data_point_topic = f"{device.mqtt_topic}/{dp_key}"
        convert_dp = sane_dp = device.get_mqtt_response(
            dp_key, output_topic="attributes"
        )
        convert_dp["dps"] = _legacy_bool_payload(sane_dp["dps"])
        _mqtt_publish(
            data_point_topic, "attributes", json.dumps(convert_dp),
        )
        _mqtt_publish(
            data_point_topic,
            "state",
            _legacy_bool_payload(
                device.get_mqtt_response(dp_key, output_topic="state")
            ),
        )


def _mqtt_publish(topic, subtopic, payload):
    """Fake MQTT publish."""
    print(topic, subtopic, payload)


def handle_status(config: dict, transformer: dict, device: Device, ha_conf: dict):
    """Convert device data to HA topics and payloads."""
    if not config:
        # print("no config for device, use legacy")
        _legacy_handle_status(device)
        return
    # print(
    #     "device",
    #     device.get_mqtt_response(output_topic="attributes"),
    # )
    # print(
    #     "device_config",
    #     config,
    # )
    # print(
    #     "transformer",
    #     transformer,
    # )
    # print("ha_conf", ha_conf)
    device_data = device.get_mqtt_response(output_topic="attributes")
    for dp_key, dp_data in device_data["dps"].items():
        dp_key_str = str(dp_key)
        if dp_key_str in config["dps"]:
            dp_ha_conf = ha_conf[dp_key_str]
            result_topic = config["dps"][dp_key_str]["device_topic"]
            print(dp_key, dp_data, result_topic)
            print(
                "topic",
                transformer[dp_key_str]["topics"][result_topic][
                    "default_value"
                ].replace("~", dp_ha_conf["~"]),
            )
            for val in transformer[dp_key_str]["topics"][result_topic][
                "values"
            ].items():
                if val["tuya_value"] == dp_data:
                    print("payload", val["default_value"])


class TransformDataPoint:
    """Transform DataPoint."""

    data_point = None
    data_point_config = None
    transform_config = None
    homeassistant_config = None
    _is_valid = False

    def __init__(self, data_point: dict):
        """Initialize TransformDataPoint."""
        self.data_point = data_point

    def set_homeassistant_config(self, config):
        """Set the Home Assistant datapoint config."""
        # TODO: check sane/valid
        self.homeassistant_config = config

    def set_transform_config(self, config):
        """Set the Home Assistant variable model for datapoint."""
        # TODO: check sane/valid
        self.transform_config = config

    def is_valid(self) -> bool:
        """Check if all configurations are valid and sane."""
        self._is_valid = False
        # TODO: check sane/valid homeassistant_config
        # TODO: check sane/valid transform_config
        # TODO: check is_valid device
        return True

    def _full_topic(self, item: dict):

        return item["defualt_name"].replace("~", self.homeassistant_config["~"])

    def get_subscribe_topics(self) -> dict:
        """Get the topics to subscribe to for the datapoint."""
        topics = {}
        for key, item in self.homeassistant_config.items():
            if key in ["cmd_t"]:
                topics[key] = self._full_topic(item)
        return topics

    def get_publish_topics(self) -> dict:
        """Get the topics to publish to for the datapoint."""
        topics = {}
        for key, item in self.homeassistant_config.items():
            if key in ["stat_t", "av_t"]:
                topics[key] = self._full_topic(item)
        return topics


class Transform:
    """Transform Home Assistant I/O data."""

    device = None
    device_config = None
    transform_config = None
    homeassistant_config = None
    data_points = {}

    def __init__(self, device: Device):
        """Initialize transform."""
        self.device = device
        self.device_config = self.device.get_config()

        print(self.device_config)

        if (
            not self.device_config
            or self.device_config["topic_config"]
            or not self.device_config["is_valid"]
        ):
            print("exit transform", self.device_config)
            return
        for dp_key, dp_value in self.device_config["dps"].items():
            self.data_points[dp_key] = TransformDataPoint(dp_value)

    # def set_homeassistant_config(self, config):
    #     # TODO: check sane/valid
    #     self.homeassistant_config = config
    #     for dp_key, dp_value in self.homeassistant_config["dps"].items():
    #         self.data_points[dp_key].set_homeassistant_config(dp_value)

    # def set_transform_config(self, config):
    #     # TODO: check sane/valid
    #     self.transform_config = config
    #     for dp_key, dp_value in self.transform_config["dps"].items():
    #         self.data_points[dp_key].transform_config(dp_value)

    # def is_valid(self) -> bool:
    #     # TODO: check sane/valid homeassistant_config
    #     # TODO: check sane/valid transform_config
    #     # TODO: check is_valid device
    #     return True

    # def get_subscribe_topics(self) -> dict:
    #     """Find topics to subscribe to."""
    #     topics = {}
    #     for dp_key, dp_value in self.homeassistant_config["dps"].items():
    #         topics[dp_key] = self.data_points[dp_key].get_subscribe_topics()
    #     return topics

    # def get_publish_topics(self) -> dict:
    #     """Find topics to publish."""
    #     topics = {}
    #     for dp_key, dp_value in self.homeassistant_config["dps"].items():
    #         topics[dp_key] = self.data_points[dp_key].get_publish_topics()
    #     # TODO: filter doubles?
    #     return topics

    # def transform_subscribe_payload(self, command: str, payload):
    #     return None

    # def transform_publish_payload(self, command: str, payload):
    #     return None

    # def get_publish_items(self):
    #     """"""
    #     return {}
