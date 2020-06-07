#!/usr/bin/python3
import sys

from tuyagateway.configure import CONFIG

from tuyagateway import TuyaMQTT


if __name__ == "__main__":

    server = TuyaMQTT(CONFIG)
    try:
        server.main_loop()
    except KeyboardInterrupt:
        print("Ctrl C - Stopping server")
        sys.exit(1)
