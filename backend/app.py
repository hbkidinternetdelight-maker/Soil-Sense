import os
import sqlite3
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS

from crop_data import CROP_DATA
from irrigation import get_irrigation_recommendation

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("SOILSENSE_DB_PATH", os.path.join(BASE_DIR, "soilsense.db"))

app = Flask(__name__)

FRONTEND_URL = os.environ.get(
    "FRONTEND_URL",
    "https://soil-sense-frontend.onrender.com"
)

CORS(app, resources={r"/api/*": {"origins": [FRONTEND_URL]}})


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS sensor_readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            moisture REAL NOT NULL,
            temperature REAL,
            humidity REAL,
            sensor_id TEXT,
            timestamp TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS area_readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            area TEXT NOT NULL,
            moisture REAL NOT NULL,
            timestamp TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


init_db()


@app.get("/")
def home():
    return jsonify({
        "success": True,
        "message": "SoilSense backend is running"
    })


@app.get("/api/sensor")
def get_sensor():
    conn = get_db()
    row = conn.execute("""
        SELECT id, moisture, temperature, humidity, sensor_id, timestamp
        FROM sensor_readings
        ORDER BY id DESC
        LIMIT 1
    """).fetchone()
    conn.close()

    if not row:
        return jsonify({
            "moisture": None,
            "temperature": None,
            "humidity": None,
            "sensor_id": None,
            "timestamp": None
        })

    return jsonify(dict(row))


@app.post("/api/sensor")
def save_sensor():
    data = request.get_json(silent=True) or {}

    try:
        moisture = float(data["moisture"])
    except (KeyError, TypeError, ValueError):
        return jsonify({"success": False, "message": "Valid moisture is required"}), 400

    temperature = data.get("temperature")
    humidity = data.get("humidity")
    sensor_id = data.get("sensor_id", "ESP32_SOILSENSE")

    try:
        temperature = float(temperature) if temperature is not None else None
    except (TypeError, ValueError):
        temperature = None

    try:
        humidity = float(humidity) if humidity is not None else None
    except (TypeError, ValueError):
        humidity = None

    timestamp = datetime.utcnow().isoformat()

    conn = get_db()
    conn.execute("""
        INSERT INTO sensor_readings
        (moisture, temperature, humidity, sensor_id, timestamp)
        VALUES (?, ?, ?, ?, ?)
    """, (moisture, temperature, humidity, sensor_id, timestamp))
    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "message": "Sensor reading saved",
        "data": {
            "moisture": moisture,
            "temperature": temperature,
            "humidity": humidity,
            "sensor_id": sensor_id,
            "timestamp": timestamp
        }
    })


@app.get("/api/sensor/history")
def sensor_history():
    conn = get_db()
    rows = conn.execute("""
        SELECT id, moisture, temperature, humidity, sensor_id, timestamp
        FROM sensor_readings
        ORDER BY id DESC
        LIMIT 100
    """).fetchall()
    conn.close()

    return jsonify([dict(row) for row in rows])


@app.get("/api/weather")
def weather():
    import requests

    location = request.args.get("location", "Pune").strip()

    try:
        geo = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": location, "count": 1, "language": "en", "format": "json"},
            timeout=10
        )
        geo.raise_for_status()
        results = geo.json().get("results", [])

        if not results:
            return jsonify({"success": False, "message": "Location not found"}), 404

        place = results[0]
        lat = place["latitude"]
        lon = place["longitude"]

        forecast = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,relative_humidity_2m,rain,precipitation,wind_speed_10m",
                "hourly": "precipitation_probability,rain,precipitation",
                "forecast_days": 2,
                "timezone": "auto"
            },
            timeout=10
        )
        forecast.raise_for_status()
        data = forecast.json()

        current = data.get("current", {})
        hourly = data.get("hourly", {})
        rain_probabilities = hourly.get("precipitation_probability", [])

        return jsonify({
            "success": True,
            "location": place.get("name", location),
            "latitude": lat,
            "longitude": lon,
            "temperature": current.get("temperature_2m"),
            "humidity": current.get("relative_humidity_2m"),
            "rainfall": current.get("precipitation"),
            "rain_probability": rain_probabilities[0] if rain_probabilities else 0,
            "wind": current.get("wind_speed_10m")
        })

    except requests.RequestException as e:
        return jsonify({"success": False, "message": str(e)}), 502


@app.get("/api/areas")
def get_areas():
    conn = get_db()
    rows = conn.execute("""
        SELECT id, area, moisture, timestamp
        FROM area_readings
        ORDER BY id ASC
    """).fetchall()
    conn.close()

    return jsonify([dict(row) for row in rows])


@app.post("/api/areas")
def save_areas():
    data = request.get_json(silent=True) or {}
    areas = data.get("areas", [])

    if not isinstance(areas, list):
        return jsonify({"success": False, "message": "areas must be a list"}), 400

    conn = get_db()

    for item in areas:
        if not isinstance(item, dict):
            continue

        area = str(item.get("area", "")).strip()
        if not area:
            continue

        try:
            moisture = float(item.get("moisture"))
        except (TypeError, ValueError):
            continue

        timestamp = item.get("timestamp") or datetime.utcnow().isoformat()

        conn.execute("""
            INSERT INTO area_readings (area, moisture, timestamp)
            VALUES (?, ?, ?)
        """, (area, moisture, timestamp))

    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": "Areas saved"})


@app.post("/api/recommendation")
def recommendation():
    data = request.get_json(silent=True) or {}

    crop = str(data.get("crop", "")).lower().strip()
    stage = str(data.get("stage", "")).lower().strip()

    if crop not in CROP_DATA:
        return jsonify({
            "success": False,
            "message": "Crop not supported"
        }), 400

    try:
        moisture = float(data.get("moisture"))
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": "Valid moisture is required"}), 400

    temperature = data.get("temperature")
    humidity = data.get("humidity")
    rain_probability = data.get("rain_probability", 0)

    result = get_irrigation_recommendation(
        crop=crop,
        stage=stage,
        moisture=moisture,
        temperature=temperature,
        humidity=humidity,
        rain_probability=rain_probability
    )

    return jsonify({
        "success": True,
        "crop": crop,
        "result": result
    })


@app.post("/api/advisor")
def advisor():
    data = request.get_json(silent=True) or {}

    crop = str(data.get("crop", "")).lower().strip()
    stage = str(data.get("stage", "")).lower().strip()

    if crop not in CROP_DATA:
        return jsonify({"success": False, "message": "Crop not supported"}), 400

    try:
        moisture = float(data.get("moisture"))
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": "Valid moisture is required"}), 400

    result = get_irrigation_recommendation(
        crop=crop,
        stage=stage,
        moisture=moisture,
        temperature=data.get("temperature"),
        humidity=data.get("humidity"),
        rain_probability=data.get("rain_probability", 0)
    )

    return jsonify({
        "success": True,
        "crop": crop,
        "stage": stage,
        "result": result
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
