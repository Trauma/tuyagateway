#!/usr/bin/python3
import sys
import configparser
from tuyamqtt.cmdline import ARGS

from tuyamqtt import TuyaMQTT

baseconfig = {
    "General": {
        "topic": "tuya",
        "payload_on": "ON",
        "payload_off": "OFF",
        "availability_online": "online",
        "availability_offline": "offline",
    },
    "MQTT": {"user": None, "pass": None, "host": "127.0.0.1", "port": 1883,},
}

if __name__ == "__main__":

    try:
        config = configparser.ConfigParser()
        if ARGS.config_file:
            config.read([ARGS.config_file])
        else:
            config.read(["./config/tuyamqtt.conf", "/etc/tuyamqtt.conf"])
    except Exception:
        config = baseconfig
        pass

    if ARGS.host:
        config["MQTT"]["host"] = ARGS.host
    if ARGS.port:
        config["MQTT"]["port"] = str(ARGS.port)
    if ARGS.user:
        config["MQTT"]["user"] = ARGS.user
    if ARGS.password:
        config["MQTT"]["password"] = ARGS.password

    server = TuyaMQTT(config)

    try:
        server.main_loop()
    except KeyboardInterrupt:
        print("Ctrl C - Stopping server")
        sys.exit(1)
