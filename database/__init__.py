import sqlite3
import json

db = sqlite3.connect('./config/tuyamqtt.db', check_same_thread=False)
cursor = db.cursor()

def disconnect():
    db.close()

def setup():
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS entities (
            id INTEGER PRIMARY KEY, 
            deviceid TEXT unique,
            localkey TEXT, 
            ip TEXT, 
            protocol TEXT, 
            topic TEXT, 
            attributes TEXT, 
            status_poll FLOAT, 
            status_command INTEGER
            hass_discover BOOL,
            name TEXT
        )
    ''')  
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS attributes (
            id INTEGER PRIMARY KEY, 
            entity_id INTEGER,
            dpsitem INTEGER,
            dpsvalue FLOAT,
            dpstype TEXT,
            via TEXT
        )
    ''') 
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY, 
            name TEXT unique, 
            value TEXT
        )
    ''')  
    db.commit()

    #not used yet
    settings = [
        {'name': 'mqtt_host', 'value': '192.168.1.14'},
        {'name': 'mqtt_port', 'value': '1883'},
        {'name': 'discovery_topic', 'value': 'tuya'}
    ]
    insert_settings(settings)
    # get_settings()

def get_settings():

    cursor.execute('''SELECT * FROM settings''')
    all_rows = cursor.fetchall()
    print(all_rows)
    return all_rows

def insert_setting(setting:dict):
    try:
        cursor.execute('''INSERT INTO settings(name, value)
                        VALUES(:name, :value)''',
                        setting)
        db.commit()       
    except Exception as e:
        # print(e)
        db.rollback()
        return False    
    return True

def insert_settings(settings:list):

    if False in set(map(insert_setting, settings)):
        return False 
    return True

#quick and dirty
def get_entities():

    dictOfEntities = {} 
    cursor.execute('''SELECT * FROM entities''')
    all_rows = cursor.fetchall()
    for row in all_rows:
        
        entity = {
            'id': row[0],
            'deviceid': row[1],
            'localkey': row[2],            
            'ip': row[3],
            'protocol': row[4],
            'topic': row[5],
            'attributes': json.loads(row[6]),
            'status_poll': row[7],
            # 'hass_discover': row[8]
        }
        dictOfEntities[row[1]] = entity
    # print(dictOfEntities)
    return dictOfEntities

def attributes_to_json(entity:dict):

    dbentity = dict(entity)
    dbentity['attributes'] = json.dumps(dbentity['attributes'])
    return dbentity

def insert_entity(entity:dict):
    # print('insert_entity')
    try:
        cursor.execute('''INSERT INTO entities(deviceid, localkey, ip, protocol, topic, attributes)
                        VALUES(:deviceid, :localkey, :ip, :protocol, :topic, :attributes)''',
                        attributes_to_json(entity))
        db.commit()
        entity['id'] = cursor.lastrowid
    except Exception as e:
        # print(e)
        db.rollback()
        return False
    
    return True
    #insert attributes
    # db.commit()

def update_entity(entity:dict):
    # print('update_entity',entity)
    # dbentity = attributes_to_json(entity)
    try:
        with db:
            db.execute('''UPDATE entities 
                    SET deviceid = ?, localkey = ?, ip = ?, protocol = ?, topic = ?, attributes = ?
                    WHERE id = ?''',
                    (entity['deviceid'], entity['localkey'], entity['ip'], entity['protocol'], entity['topic'], json.dumps(entity['attributes']), entity['id'])
                    )
    except Exception as e:
        # print(e)
        return False
    return True


def upsert_entity(entity:dict):
    # print(entity)      
    if not insert_entity(entity):
        return update_entity(entity)


def upsert_entities(entities:dict):
 
    if False in set(map(upsert_entity, entities.values())):
        return False 
    return True
    

def delete_entity(entity:dict):

    cursor.execute('''DELETE FROM entities WHERE id = ? ''', (entity['id'],))
    #delete attributes
    db.commit()

"""
from sqlalchemy import create_engine, Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

Base = declarative_base()

engine = create_engine('sqlite:///../config/db.sqlite3', echo=True)
#PRAGMA table_info(tuyamqtt_dps);

class Device(Base):
    __tablename__ = 'tuyamqtt_device'

    id = Column(Integer, primary_key=True)
    name = Column(String(32))
    topic = Column(String(200))
    protocol = Column(String(16))
    deviceid = Column(String(64))
    localkey = Column(String(64))
    ip = Column(String(64))
    hass_discovery = Column(Boolean)   
    dpss = relationship("Dps", back_populates="device")

class Dpstype(Base):
    __tablename__ = 'tuyamqtt_dpstype'

    id = Column(Integer, primary_key=True)
    name = Column(String(64))
    valuetype = Column(String(16))
    range_min = Column(Integer)
    range_max = Column(Integer)
    discoverytype = Column(String(16))
    dps = relationship("Dps", back_populates="dpstype")

class Dps(Base):
    __tablename__ = 'tuyamqtt_dps'

    id = Column(Integer, primary_key=True)
    device_id = Column(Integer, ForeignKey('tuyamqtt_device.id'))
    key = Column(Integer)
    value = Column(String(16))
    via = Column(String(8))
    dpstype_id = Column(Integer, ForeignKey('tuyamqtt_dpstype.id'))

    device = relationship("Device", back_populates= "dpss")
    dpstype = relationship("Dpstype", back_populates="dps")

    def __repr__(self):
        return "<Dps(key='%s', value='%s', via='%s')>" % (
                                self.key, self.value, self.via)


# for row in session.query(Device).all():
#     print(row.name, row.topic)

# for row in session.query(Dpstype).all():
#     print(row.name, row.valuetype)

def _to_dict(row):
    dictret = dict(row.__dict__)
    dictret.pop('_sa_instance_state', None)
    return dictret


def get_devices():

    Session = sessionmaker()
    Session.configure(bind=engine)
    session = Session()

    devices = {}
    for row in session.query(Device).join(Dps, Device.id==Dps.device_id).all():
        device = _to_dict(row)
        device['attributes'] = {'dps':{},'via':{}}      
        for dps in row.dpss:
            # dpsdict =_to_dict(dps)         
            device['attributes']['dps'][dps.key] = dps.value
            device['attributes']['via'][dps.key] = dps.via
        devices[device['deviceid']] = device  
    return devices


print(get_devices())
"""