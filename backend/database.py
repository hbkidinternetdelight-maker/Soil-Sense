import sqlite3
from datetime import datetime

DATABASE_NAME = "soilsense.db"


def get_connection():
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_database():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sensor_readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sensor_id TEXT,
            moisture REAL NOT NULL,
            temperature REAL,
            humidity REAL,
            timestamp TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS area_readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            area TEXT NOT NULL,
            moisture REAL NOT NULL,
            timestamp TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


def save_sensor_reading(
    moisture,
    temperature=None,
    humidity=None,
    sensor_id="main_sensor"
):
    conn = get_connection()
    cursor = conn.cursor()

    timestamp = datetime.now().isoformat()

    cursor.execute("""
        INSERT INTO sensor_readings
        (sensor_id, moisture, temperature, humidity, timestamp)
        VALUES (?, ?, ?, ?, ?)
    """, (
        sensor_id,
        moisture,
        temperature,
        humidity,
        timestamp
    ))

    conn.commit()
    conn.close()


def get_latest_reading():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            sensor_id,
            moisture,
            temperature,
            humidity,
            timestamp
        FROM sensor_readings
        ORDER BY id DESC
        LIMIT 1
    """)

    row = cursor.fetchone()
    conn.close()

    if row is None:
        return None

    return dict(row)


def get_sensor_history(limit=20):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            sensor_id,
            moisture,
            temperature,
            humidity,
            timestamp
        FROM sensor_readings
        ORDER BY id DESC
        LIMIT ?
    """, (limit,))

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def save_area_reading(area, moisture):
    conn = get_connection()
    cursor = conn.cursor()

    timestamp = datetime.now().isoformat()

    cursor.execute("""
        INSERT INTO area_readings
        (area, moisture, timestamp)
        VALUES (?, ?, ?)
    """, (
        area,
        moisture,
        timestamp
    ))

    conn.commit()
    conn.close()


def get_area_readings():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            area,
            moisture,
            timestamp
        FROM area_readings
        WHERE id IN (
            SELECT MAX(id)
            FROM area_readings
            GROUP BY area
        )
        ORDER BY area
    """)

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def clear_database():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM sensor_readings")
    cursor.execute("DELETE FROM area_readings")

    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_database()
    print("SoilSense database initialized successfully.")
