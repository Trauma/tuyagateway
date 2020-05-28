import argparse

parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument("-ttf", help="Test tuyaface [True|False]", type=bool, default=False)
parser.add_argument(
    "-ll", help="Log level [INFO|WARN|ERROR|DEBUG]", type=str, default="INFO"
)
parser.add_argument("-cf", "--config_file", help="config file", type=str)
parser.add_argument("-H", "--host", help="MQTT Host", default="127.0.0.1", type=str)
parser.add_argument("-P", "--port", help="MQTT Port", default=1883, type=int)
parser.add_argument("-U", "--user", help="MQTT User", type=str)
parser.add_argument("-p", "--password", help="MQTT Password", type=str)
args = parser.parse_args()
print(args)
