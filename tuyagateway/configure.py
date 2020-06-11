"""Read commandline params."""
import argparse
import configparser
import logging

DEFAULTS = {
    "General": {
        "topic": "tuya",
        "payload_on": "ON",
        "payload_off": "OFF",
        "availability_online": "online",
        "availability_offline": "offline",
    },
    "MQTT": {"user": None, "pass": None, "host": "127.0.0.1", "port": 1883},
}

CONFIG = DEFAULTS

try:
    CONFIG = configparser.ConfigParser()
    CONFIG.read(
        [
            "./etc/tuyagateway.conf",
            "/usr/local/etc/tuyagateway.conf",
            "/etc/tuyagateway.conf",
        ]
    )
except Exception:
    CONFIG = DEFAULTS


CURRENT = {"General": dict(CONFIG["General"]), "MQTT": dict(CONFIG["MQTT"])}

PARSER = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
PARSER.add_argument(
    "-ll", help="Log level [INFO|WARN|ERROR|DEBUG]", type=str, default="INFO"
)
PARSER.add_argument("-cf", "--config_file", help="config file", type=str)
PARSER.add_argument(
    "-H", "--host", help="MQTT Host", default=CONFIG["MQTT"]["host"], type=str
)
PARSER.add_argument(
    "-P", "--port", help="MQTT Port", default=CONFIG["MQTT"]["port"], type=int
)
PARSER.add_argument("-U", "--user", help="MQTT User", type=str)
PARSER.add_argument("-p", "--password", help="MQTT Password", type=str)
ARGS = PARSER.parse_args()

if ARGS.config_file:
    try:
        CONFIG = configparser.ConfigParser()
        CONFIG.read([ARGS.config_file])
    except Exception:
        pass

if "MQTT" not in CONFIG:
    CONFIG = CURRENT

if ARGS.host != CURRENT["MQTT"]["host"]:
    CONFIG["MQTT"]["host"] = ARGS.host
if ARGS.port != CURRENT["MQTT"]["port"]:
    CONFIG["MQTT"]["port"] = str(ARGS.port)
if ARGS.user != CURRENT["MQTT"]["user"] and ARGS.user:
    CONFIG["MQTT"]["user"] = ARGS.user
if ARGS.password != CURRENT["MQTT"]["pass"] and ARGS.password:
    CONFIG["MQTT"]["pass"] = ARGS.password


LOGLEVEL = logging.INFO
if ARGS.ll == "INFO":
    LOGLEVEL = logging.INFO
elif ARGS.ll == "WARN":
    LOGLEVEL = logging.WARN
elif ARGS.ll == "ERROR":
    LOGLEVEL = logging.ERROR
elif ARGS.ll == "DEBUG":
    LOGLEVEL = logging.DEBUG

logging.basicConfig(
    format="%(asctime)s %(levelname)-8s (%(threadName)s) [%(name)s] %(message)s",
    level=LOGLEVEL,
)
logger = logging.getLogger(__name__)
