import time
import paho.mqtt.client as mqtt
import json
from os import path
from threading import Thread
import logging

import database as database

if True:
    import tuyaface
    from tuyaface.tuyaclient import TuyaClient
else:
    # for local testing tuyaface
    import tuya.tuyaface as tuyaface
    from tuya.tuyaface.tuyaclient import TuyaClient

loglevel=logging.INFO
#loglevel=logging.DEBUG
logging.basicConfig(format='%(asctime)s %(levelname)-8s (%(threadName)s) [%(name)s] %(message)s', level=loglevel)
logger = logging.getLogger(__name__)


def connack_string(state):

    states = [
        'Connection successful',
        'Connection refused - incorrect protocol version',
        'Connection refused - invalid client identifier',
        'Connection refused - server unavailable',
        'Connection refused - bad username or password',
        'Connection refused - not authorised'
    ]
    return states[state]


def payload_bool(payload:str):

    str_payload = str(payload.decode("utf-8"))
    if str_payload == 'True' or str_payload == 'ON' or str_payload == '1':
        return True       
    elif str_payload == 'False' or str_payload == 'OFF' or str_payload == '0':
        return False    
    return payload


def bool_payload(config:dict, boolvalue:bool):

    if boolvalue:
        return config['General']['payload_on']
    return config['General']['payload_off']


def bool_availability(config:dict, boolvalue:bool):

    if boolvalue:
        return config['General']['availability_online']
    return config['General']['availability_offline']


class TuyaMQTTEntity(Thread):

    delay = 0.1

    def __init__(self, key, entity, parent):        
 
        Thread.__init__(self)
        self.key = key
      
        self.entity = entity
        self.mqtt_topic = entity['topic']

        self.mqtt_topic = f"tuya/{entity['protocol']}/{entity['deviceid']}/{entity['localkey']}/{entity['ip']}"

        self.parent = parent
        self.config = self.parent.config 

        self.mqtt_topic = "%s/%s/%s/%s/%s"%(self.config['General']['topic'],entity['protocol'],entity['deviceid'],entity['localkey'],entity['ip'])
          
        self.mqtt_connected = False
        self.availability = False
        self.client = None


    def mqtt_connect(self): 

        try:
            self.mqtt_client = mqtt.Client()
            self.mqtt_client.enable_logger()
            self.mqtt_client.username_pw_set(self.config['MQTT']['user'], self.config['MQTT']['pass'])
            self.mqtt_client.connect(self.config['MQTT']['host'], int(self.config['MQTT']['port']), 60)
            self.mqtt_client.on_connect = self.on_connect
            self.mqtt_client.loop_start()   
            self.mqtt_client.on_message = self.on_message

        except Exception as ex:
            logger.warning('(%s) Failed to connect to MQTT Broker %s', self.entity['ip'], ex)
            self.mqtt_connected = False


    def on_message(self, client, userdata, message):      

        if message.topic[-7:] != 'command':
            return   

        logging.debug("(%s) topic %s retained %s message received %s", self.entity['ip'], message.topic,message.retain,str(message.payload.decode("utf-8")))

        entityParts = message.topic.split("/")  
        dps_key = str(entityParts[5]) #will give problem with custom topics

        if dps_key not in self.entity['attributes']['dps']:
            self._set_dps(dps_key, None)
        if dps_key not in self.entity['attributes']['via']:
            self._set_via(dps_key, 'mqtt')
        self.set_state(dps_key, payload_bool(message.payload))


    def on_connect(self, client, userdata, flags, rc):

        logger.info("MQTT Connection state: %s for %s" % (connack_string(rc), self.mqtt_topic))
        client.subscribe("%s/#" % self.mqtt_topic)
        self.mqtt_connected = True


    def _set_dps(self, dps_key, dps_value:str):

        self.entity['attributes']['dps'][dps_key] = dps_value
        self.parent.set_entity_dps_item(self.key, dps_key, dps_value) 


    def _set_via(self, dps_key, via:str):

        self.entity['attributes']['via'][dps_key] = via
        self.parent.set_entity_via_item(self.key, dps_key, via) 


    def _set_availability(self, availability:bool):

        if availability != self.availability:
            self.availability = availability
            logger.debug("->publish %s/availability" % self.mqtt_topic)     
            self.mqtt_client.publish("%s/availability" % self.mqtt_topic, bool_availability(self.config, availability))


    def _process_data(self, data:dict, via:str, force_mqtt:bool = False):

        changed = force_mqtt
        
        for dps_key, dps_value in data['dps'].items():
            
            if dps_key not in self.entity['attributes']['dps']:
                self._set_dps(dps_key, None)
            logger.debug("(%s) _process_data %s : %s", self.entity['ip'], dps_key, dps_value)

            if dps_key not in self.entity['attributes']['via']:
                self._set_via(dps_key, 'init')
            if dps_value != self.entity['attributes']['dps'][dps_key] or force_mqtt:
                changed = True
                self._set_dps(dps_key, dps_value) 

                logger.debug("(%s) ->publish %s/%s/state", self.entity['ip'], self.mqtt_topic, dps_key)
                self.mqtt_client.publish(f"{self.mqtt_topic}/{dps_key}/state",  bool_payload(self.config, dps_value))
                
                if via != self.entity['attributes']['via'][dps_key]:                        
                    self._set_via(dps_key, via)
                
                attr_item = {
                    'dps': self.entity['attributes']['dps'][dps_key], 
                    'via': self.entity['attributes']['via'][dps_key],
                    'time': time.time()
                }

                logger.debug("(%s) ->publish %s/%s/attributes", self.entity['ip'], self.mqtt_topic, dps_key)
                self.mqtt_client.publish(f"{self.mqtt_topic}/{dps_key}/attributes",  json.dumps(attr_item))
        
        if changed:
            attr = {
                'dps': self.entity['attributes']['dps'], 
                'via': self.entity['attributes']['via'],
                'time': time.time()
            } 
            
            logger.debug("(%s) ->publish %s/attributes", self.entity['ip'], (self.mqtt_topic))
            self.mqtt_client.publish(f"{self.mqtt_topic}/attributes",  json.dumps(attr))

    def on_status(self, data:dict):

        self._process_data(data, 'tuya')


    def on_connection(self, connected: bool):

        self._set_availability(connected)


    def status(self, via:str = 'tuya', force_mqtt:bool = False):
            
        try:
            data = self.client.status()

            if not data:
                self._set_availability(False)
                return
       
            self._process_data(data, via, force_mqtt)
            self._set_availability(True)

        except Exception as ex:            
            logger.exception('(%s) status request error', self.entity['ip'])

            self._set_availability(False)


    def set_state(self, dps_item, payload):

        try:  
            data = self.client.set_state(payload, dps_item)

            if not data:
                self.status('mqtt', True)
                return

            self._process_data(data, 'mqtt', True)

        except Exception as ex:
            logger.error('(%s) set_state request on topic %s', self.entity['ip'], self.mqtt_topic, exc_info=True)

    def hass_discovery(self, entity):

        if entity['ip'] != '192.168.1.25':
            return

        for item in entity['attributes']['dps'].items():
            self.hass_disc_item(item)


    def hass_disc_item(self, item):
        """
        08:56:40 MQT: kitchen_left_lighting/tele/LWT = Online (retained)
        08:56:40 MQT: kitchen_left_lighting/cmnd/POWER = 
        08:56:40 MQT: kitchen_left_lighting/tele/INFO1 = {"Module":"Sonoff Basic","Version":"8.1.0.2(1e06976-tasmota)","FallbackTopic":"cmnd/kitchen_left_lighting_fb/","GroupTopic":"sonoffs/cmnd/"}
        08:56:40 MQT: kitchen_left_lighting/tele/INFO2 = {"WebServerMode":"Admin","Hostname":"kitchen_left_lighting-7456","IPAddress":"192.168.1.34"}
        08:56:40 MQT: kitchen_left_lighting/tele/INFO3 = {"RestartReason":"Software/System restart"}
        08:56:40 MQT: kitchen_left_lighting/stat/RESULT = {"POWER":"OFF"}
        08:56:40 MQT: kitchen_left_lighting/stat/POWER = OFF
        08:56:41 MQT: homeassistant/light/ABBD20_LI_1/config =  (retained)
        08:56:41 MQT: homeassistant/switch/ABBD20_RL_1/config = {"name":"Kitchen Left Lighting","cmd_t":"~cmnd/POWER","stat_t":"~tele/STATE","val_tpl":"{{value_json.POWER}}","pl_off":"OFF","pl_on":"ON","avty_t":"~tele/LWT","pl_avail":"Online","pl_not_avail":"Offline","uniq_id":"ABBD20_RL_1","device":{"identifiers":["ABBD20"],"connections":[["mac","DC:4F:22:AB:BD:20"]]},"~":"kitchen_left_lighting/"} (retained)
        08:56:41 MQT: homeassistant/light/ABBD20_LI_2/config =  (retained)
        08:56:41 MQT: homeassistant/switch/ABBD20_RL_2/config =  (retained)
        08:56:41 MQT: homeassistant/light/ABBD20_LI_3/config =  (retained)
        08:56:41 MQT: homeassistant/switch/ABBD20_RL_3/config =  (retained)
        08:56:41 MQT: homeassistant/light/ABBD20_LI_4/config =  (retained)
        08:56:41 MQT: homeassistant/switch/ABBD20_RL_4/config =  (retained)
        08:56:41 MQT: homeassistant/light/ABBD20_LI_5/config =  (retained)
        08:56:41 MQT: homeassistant/switch/ABBD20_RL_5/config =  (retained)
        08:56:41 MQT: homeassistant/light/ABBD20_LI_6/config =  (retained)
        08:56:41 MQT: homeassistant/switch/ABBD20_RL_6/config =  (retained)
        08:56:41 MQT: homeassistant/light/ABBD20_LI_7/config =  (retained)
        08:56:41 MQT: homeassistant/switch/ABBD20_RL_7/config =  (retained)
        08:56:41 MQT: homeassistant/light/ABBD20_LI_8/config =  (retained)
        08:56:41 MQT: homeassistant/switch/ABBD20_RL_8/config =  (retained)
        08:56:41 MQT: homeassistant/binary_sensor/ABBD20_BTN_1/config = {"name":"Kitchen Left Lighting Button1","stat_t":"~stat/BUTTON1","avty_t":"~tele/LWT","pl_avail":"Online","pl_not_avail":"Offline","uniq_id":"ABBD20_BTN_1","device":{"identifiers":["ABBD20"],"connections":[["mac","DC:4F:22:AB:BD:20"]]},"~":"kitchen_left_lighting/","value_template":"{{value_json.STATE}}","pl_on":"TOGGLE","off_delay":1} (retained)
        08:56:41 MQT: homeassistant/binary_sensor/ABBD20_BTN_2/config =  (retained)
        08:56:41 MQT: homeassistant/binary_sensor/ABBD20_BTN_3/config =  (retained)
        08:56:41 MQT: homeassistant/binary_sensor/ABBD20_BTN_4/config =  (retained)
        08:56:41 MQT: homeassistant/binary_sensor/ABBD20_SW_1/config =  (retained)
        08:56:41 MQT: homeassistant/binary_sensor/ABBD20_SW_2/config =  (retained)
        08:56:41 MQT: homeassistant/binary_sensor/ABBD20_SW_3/config =  (retained)
        08:56:41 MQT: homeassistant/binary_sensor/ABBD20_SW_4/config =  (retained)
        08:56:41 MQT: homeassistant/binary_sensor/ABBD20_SW_5/config =  (retained)
        08:56:41 MQT: homeassistant/binary_sensor/ABBD20_SW_6/config =  (retained)
        08:56:41 MQT: homeassistant/binary_sensor/ABBD20_SW_7/config =  (retained)
        08:56:41 MQT: homeassistant/binary_sensor/ABBD20_SW_8/config =  (retained)
        08:56:41 MQT: homeassistant/sensor/ABBD20_status/config = {"name":"Kitchen Left Lighting status","stat_t":"~HASS_STATE","avty_t":"~LWT","frc_upd":true,"pl_avail":"Online","pl_not_avail":"Offline","json_attributes_topic":"~HASS_STATE","unit_of_meas":" ","val_tpl":"{{value_json['RSSI']}}","ic":"mdi:information-outline","uniq_id":"ABBD20_status","device":{"identifiers":["ABBD20"],"connections":[["mac","DC:4F:22:AB:BD:20"]],"name":"Kitchen Left Lighting","model":"Sonoff Basic","sw_version":"8.1.0.2(1e06976-tasmota)","manufacturer":"Tasmota"},"~":"kitchen_left_lighting/tele/"} (retained)
        08:56:44 MQT: kitchen_left_lighting/tele/STATE = {"Time":"2020-05-22T08:56:44","Uptime":"0T00:00:12","UptimeSec":1
        """

        print(item)
        device_dps = '%s_%s' % (self.entity['deviceid'], item[0])
        """
        we have no knowledge of what the dps values actualy do at this point
        need an interface so enduser can configure
        """
        hass_topic = 'homeassistant/%s/%s/config' % ('unknown', device_dps)

       
        payload = {
            "name": "name here",
            "cmd_t": "~command",
            "stat_t": "~state",
            "val_tpl":"{{value_json.POWER}}",
            "pl_off": self.config['General']['payload_off'],
            "pl_on": self.config['General']['payload_off'],
            "avty_t":"~availability",
            "pl_avail": self.config['General']['availability_online'],
            "pl_not_avail": self.config['General']['availability_offline'],
            "uniq_id": device_dps,
            "device":{
                "identifiers":[self.entity['deviceid']]
            },
            "~": self.mqtt_topic
        }
        print(hass_topic)
        print(payload)


    def run(self):        
   
        self.client = TuyaClient(self.entity, self.on_status, self.on_connection)
        self.client.start()
        # time_unset_reset = 0  
        # self.hass_discovery(self.entity) 
        # return

        while True:  

            if not self.mqtt_connected:
                self.mqtt_connect()
                time.sleep(1)      

            # if time.time() > time_run_availability:               
            #     time_run_availability = time.time()+15   
            #     logger.debug("->publish %s/availability" % self.mqtt_topic)     
            #     self.mqtt_client.publish("%s/availability" % self.mqtt_topic, bool_availability(self.config, self.availability)) 
                    


            time.sleep(self.delay)      



class TuyaMQTT:


    delay = 0.1
    config = []
    dictOfEntities = {}


    def __init__(self, config):

        self.config = config

        # self.entities_file = config['General']['entity_file']
        self.mqtt_topic = config['General']['topic']
        self.mqtt_connected = False

        self.database = database
        self.database.setup()            


    def mqtt_connect(self): 

        try:
            self.mqtt_client = mqtt.Client()
            self.mqtt_client.enable_logger()
            self.mqtt_client.username_pw_set(self.config['MQTT']['user'], self.config['MQTT']['pass'])
            self.mqtt_client.connect(self.config['MQTT']['host'], int(self.config['MQTT']['port']), 60)
            self.mqtt_client.on_connect = self.on_connect
            self.mqtt_client.loop_start()   
            self.mqtt_client.on_message = self.on_message
        except Exception:
            logger.info('Failed to connect to MQTT Broker')
            self.mqtt_connected = False
   

    def on_connect(self, client, userdata, flags, rc):

        logger.info("MQTT Connection state: %s for topic %s",connack_string(rc), self.mqtt_topic)
        client.subscribe("{self.mqtt_topic}/#")
        self.mqtt_connected = True


    def write_entity(self):

        self.database.upsert_entities(self.dictOfEntities)


    def read_entity(self):

        self.dictOfEntities = self.database.get_entities()


    def add_entity_dict(self, entityRaw, retain):
        
        entityParts = entityRaw.split("/")

        key = entityParts[2]

        if key in self.dictOfEntities:
            return False
        
        entity = {
            'protocol': entityParts[1],
            'deviceid': entityParts[2],
            'localkey': entityParts[3],
            'ip': entityParts[4],
            'topic': key,            
            'attributes': {
                'dps': {},
                'via': {}
            },
            'status_poll': 5.0,
            'hass_discover': False
        }

        self.dictOfEntities[key] = entity
        # self.write_entity()
        self.database.insert_entity(entity)
        return key
        

    def get_entity(self, key):

        return self.dictOfEntities[key]


    def set_entity_dps_item(self, key, dps, value):

        self.dictOfEntities[key]['attributes']['dps'][dps] = value   
        self.database.update_entity(self.dictOfEntities[key])


    def set_entity_via_item(self, key, dps, value):

        self.dictOfEntities[key]['attributes']['via'][dps] = value
        self.database.update_entity(self.dictOfEntities[key])
    

    def on_message(self, client, userdata, message):                   

        if message.topic[-7:] != 'command':
            return   
        
        key = self.add_entity_dict(message.topic, message.retain)

        if key:
            logger.info("message received %s topic %s retained %s ", str(message.payload.decode("utf-8")), message.topic, message.retain)
            entity = self.get_entity(key)
            
            myThreadOb1 = TuyaMQTTEntity(key, entity, self)     
            myThreadOb1.setName(key)    
            myThreadOb1.start()


    def main_loop(self):

        """
        primary loop to send / receive from tuya devices
        """
        self.read_entity()
     
        tpool = []
        for key,entity in self.dictOfEntities.items():
            myThreadOb1 = TuyaMQTTEntity(key, entity, self)     
            myThreadOb1.setName(key)    
            myThreadOb1.start()
            tpool.append(myThreadOb1)
 
        time_run_save = 0
        
        while True: 

            if not self.mqtt_connected:
                self.mqtt_connect()
                time.sleep(2)
                continue                      
          
            if time.time() > time_run_save:
                self.write_entity()
                time_run_save = time.time()+300

            time.sleep(self.delay)           

