#!/usr/bin/python3
import sys
import configparser
from tuyamqtt.cmdline import args

from tuyamqtt import TuyaMQTT

baseconfig= {
    'General': {
        'topic': 'tuya',
        'payload_on': 'ON',
        'payload_off': 'OFF',
        'availability_online': 'online',
        'availability_offline': 'offline',
    },
    'MQTT': {
        'user': None,
        'pass': None,
        'host': '127.0.0.1',
        'port': 1883,
    }
}

if __name__ == '__main__':    
    
    try:
        config = configparser.ConfigParser()
        if args.config_file:
            config.read([args.config_file])
        else:
            config.read(['./config/tuyamqtt.conf', '/etc/tuyamqtt.conf'])
    except Exception:
        config = baseconfig
        pass

    if args.host:
        config['MQTT']['host'] = args.host
    if args.port:
        config['MQTT']['port'] = args.port
    if args.user:
        config['MQTT']['user'] = args.user
    if args.password:
        config['MQTT']['password'] = args.password
    

    server = TuyaMQTT(config)

    try:
        server.main_loop()
    except KeyboardInterrupt:
        print('Ctrl C - Stopping server')
        sys.exit(1)
