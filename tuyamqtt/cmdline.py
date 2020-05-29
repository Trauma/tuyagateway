"""Read commandline params."""
import argparse

PARSER = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
PARSER.add_argument(
    "-ll", help="Log level [INFO|WARN|ERROR|DEBUG]", type=str, default="INFO"
)
PARSER.add_argument("-cf", "--config_file", help="config file", type=str)
PARSER.add_argument("-H", "--host", help="MQTT Host", default="127.0.0.1", type=str)
PARSER.add_argument("-P", "--port", help="MQTT Port", default=1883, type=int)
PARSER.add_argument("-U", "--user", help="MQTT User", type=str)
PARSER.add_argument("-p", "--password", help="MQTT Password", type=str)
ARGS = PARSER.parse_args()
