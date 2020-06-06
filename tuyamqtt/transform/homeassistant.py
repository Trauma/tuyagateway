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
    print(sane_reply["dps"].values())
    convert_reply = sane_reply
    convert_reply["dps"] = {
        k: _legacy_bool_payload(v) for k, v in sane_reply["dps"].items()
    }
    print(convert_reply)
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


def handle_status(config: dict, transformer: dict, device: Device):
    """Convert device data to HA topics and payloads."""
    if not config:
        # print("no config for device, use legacy")
        _legacy_handle_status(device)
        return
    print(
        "handle_status",
        device.get_mqtt_response(output_topic="attributes"),
        config,
        transformer,
    )
