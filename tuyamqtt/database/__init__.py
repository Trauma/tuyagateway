"""Database for TuyaMQTT."""
import sqlite3
import json


DATABASE = sqlite3.connect("tuyamqtt.db", check_same_thread=False)
CURSOR = DATABASE.cursor()


def disconnect():
    """Close the database."""
    DATABASE.close()


def setup():
    """Initialize the database."""
    CURSOR.execute(
        """
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
    """
    )
    CURSOR.execute(
        """
        CREATE TABLE IF NOT EXISTS attributes (
            id INTEGER PRIMARY KEY,
            entity_id INTEGER,
            dpsitem INTEGER,
            dpsvalue FLOAT,
            dpstype TEXT,
            via TEXT
        )
    """
    )

    DATABASE.commit()


# quick and dirty


def get_entities():
    """Get items from DATABASE."""
    dict_entities = {}
    CURSOR.execute("""SELECT * FROM entities""")
    all_rows = CURSOR.fetchall()
    for row in all_rows:

        entity = {
            "id": row[0],
            "deviceid": row[1],
            "localkey": row[2],
            "ip": row[3],
            "protocol": row[4],
            "attributes": json.loads(row[6]),
            "topic_config": True,
        }
        dict_entities[row[1]] = entity
    return dict_entities


def attributes_to_json(entity: dict):
    """Create json formatted string."""
    database_entity = dict(entity)
    database_entity["attributes"] = json.dumps(database_entity["attributes"])
    return database_entity


def insert_entity(entity: dict):
    """Insert an item."""
    if not entity["topic_config"]:
        return False

    try:
        CURSOR.execute(
            """INSERT INTO entities(deviceid, localkey, ip, protocol, attributes)
                        VALUES(:deviceid, :localkey, :ip, :protocol, :attributes)""",
            attributes_to_json(entity),
        )
        DATABASE.commit()
        entity["id"] = CURSOR.lastrowid
    except Exception:
        DATABASE.rollback()
        return False

    return True


def update_entity(entity: dict):
    """Update item."""
    if not entity["topic_config"]:
        return False

    try:
        with DATABASE:
            DATABASE.execute(
                """UPDATE entities
                    SET deviceid = ?, localkey = ?, ip = ?, protocol = ?,  attributes = ?
                    WHERE id = ?""",
                (
                    entity["deviceid"],
                    entity["localkey"],
                    entity["ip"],
                    entity["protocol"],
                    json.dumps(entity["attributes"]),
                    entity["id"],
                ),
            )
    except Exception:
        return False
    return True


def upsert_entity(entity: dict):
    """Upsert item into DATABASE."""
    if not entity["topic_config"]:
        return False

    if not insert_entity(entity):
        return update_entity(entity)


def upsert_entities(entities: dict):
    """Upsert items into DATABASE."""
    if False in set(map(upsert_entity, entities.values())):
        return False
    return True


def delete_entity(entity: dict):
    """Remove item from DATABASE."""
    if "id" not in entity:
        return

    CURSOR.execute("""DELETE FROM entities WHERE id = ? """, (entity["id"],))
    # delete attributes
    DATABASE.commit()
