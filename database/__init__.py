import sqlite3
import json

"""
Database will be removed when mqttdevices works properly
Target v2.0.0
"""

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

    db.commit()

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


def attributes_to_json(entity: dict):

    dbentity = dict(entity)
    dbentity['attributes'] = json.dumps(dbentity['attributes'])
    return dbentity


def insert_entity(entity: dict):

    if 'tuya_discovery' in entity:
        return False

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
    # insert attributes
    # db.commit()


def update_entity(entity: dict):

    if 'tuya_discovery' in entity:
        return False

    try:
        with db:
            db.execute('''UPDATE entities 
                    SET deviceid = ?, localkey = ?, ip = ?, protocol = ?, topic = ?, attributes = ?
                    WHERE id = ?''',
                       (entity['deviceid'], entity['localkey'], entity['ip'], entity['protocol'],
                        entity['topic'], json.dumps(entity['attributes']), entity['id'])
                       )
    except Exception as e:
        # print(e)
        return False
    return True


def upsert_entity(entity: dict):

    if 'tuya_discovery' in entity:
        return False

    if not insert_entity(entity):
        return update_entity(entity)


def upsert_entities(entities: dict):

    if False in set(map(upsert_entity, entities.values())):
        return False
    return True


def delete_entity(entity: dict):

    if 'id' not in entity:
        return

    cursor.execute('''DELETE FROM entities WHERE id = ? ''', (entity['id'],))
    # delete attributes
    db.commit()
