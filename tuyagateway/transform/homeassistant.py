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
