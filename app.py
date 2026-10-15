import os
import sqlite3
from datetime import datetime, timezone
from flask import Flask, request, jsonify
from flask_cors import CORS

# ============================================================
# SoilSense Flask Backend
# Supports ESP32 POST /api/sensor and dashboard GET /api/sensor
# ============================================================

app = Flask(__name__)

# Allow the deployed frontend and local development origins.
CORS(
    app,
    resources={
        r"/api/*": {
            "origins": [
                "https://soilsense-frontend-pe0n.onrender.com",
                "http://localhost:3000",
                "http://127.0.0.1:3000",
                "http://localhost:5500",
                "http://127.0.0.1:5500",
                "http://localhost:8000",
                "http://127.0.0.1:8000",
            ]
        }
    },
    supports_credentials=False,
)

DATABASE_PATH = os.environ.get("SOILSENSE_DB_PATH", "soilsense.db")


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def get_db():
    conn = sqlite3.connect(DATABASE_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sensor_readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sensor_id TEXT NOT NULL,
                moisture REAL NOT NULL,
                temperature REAL,
                humidity REAL,
                timestamp TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS area_readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                area TEXT NOT NULL,
                moisture REAL NOT NULL,
                timestamp TEXT NOT NULL
            )
            """
        )
        conn.commit()


init_db()


def row_to_dict(row):
    if row is None:
        return None
    return {
        "id": row["id"],
        "sensor_id": row["sensor_id"],
        "moisture": row["moisture"],
        "temperature": row["temperature"],
        "humidity": row["humidity"],
        "timestamp": row["timestamp"],
    }


@app.get("/")
def home():
    return jsonify({
        "success": True,
        "message": "SoilSense backend is running",
        "endpoints": [
            "GET /api/sensor",
            "POST /api/sensor",
            "GET /api/sensor/history",
            "GET /api/areas",
            "POST /api/areas",
            "POST /api/recommendation",
        ],
    })


@app.get("/health")
def health():
    return jsonify({"success": True, "status": "healthy"})


@app.route("/api/sensor", methods=["GET", "POST", "OPTIONS"])
def sensor():
    # Flask-CORS handles OPTIONS preflight requests.
    if request.method == "OPTIONS":
        return ("", 204)

    if request.method == "POST":
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({
                "success": False,
                "message": "Send a JSON object with sensor_id and moisture",
            }), 400

        sensor_id = str(payload.get("sensor_id") or "ESP32_SOILSENSE").strip()
        if not sensor_id:
            sensor_id = "ESP32_SOILSENSE"

        try:
            moisture = float(payload["moisture"])
        except (KeyError, TypeError, ValueError):
            return jsonify({
                "success": False,
                "message": "moisture must be a number",
            }), 400

        if not 0 <= moisture <= 100:
            return jsonify({
                "success": False,
                "message": "moisture must be between 0 and 100",
            }), 400

        def optional_number(key):
            value = payload.get(key)
            if value is None or value == "":
                return None
            try:
                return float(value)
            except (TypeError, ValueError):
                raise ValueError(f"{key} must be a number or null")

        try:
            temperature = optional_number("temperature")
            humidity = optional_number("humidity")
        except ValueError as exc:
            return jsonify({"success": False, "message": str(exc)}), 400

        timestamp = now_iso()
        with get_db() as conn:
            cursor = conn.execute(
                """
                INSERT INTO sensor_readings
                    (sensor_id, moisture, temperature, humidity, timestamp)
                VALUES (?, ?, ?, ?, ?)
                """,
                (sensor_id, moisture, temperature, humidity, timestamp),
            )
            reading_id = cursor.lastrowid
            conn.commit()

        return jsonify({
            "success": True,
            "message": "Sensor reading saved",
            "data": {
                "id": reading_id,
                "sensor_id": sensor_id,
                "moisture": moisture,
                "temperature": temperature,
                "humidity": humidity,
                "timestamp": timestamp,
            },
        }), 201

    # GET: return latest reading as a flat JSON object for dashboard compatibility.
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM sensor_readings ORDER BY id DESC LIMIT 1"
        ).fetchone()

    if row is None:
        return jsonify({
            "success": True,
            "message": "No sensor readings received yet",
            "data": None,
            "sensor_id": "ESP32_SOILSENSE",
            "moisture": None,
            "temperature": None,
            "humidity": None,
            "timestamp": None,
        })

    reading = row_to_dict(row)
    return jsonify(reading)


@app.get("/api/sensor/history")
def sensor_history():
    try:
        limit = int(request.args.get("limit", "50"))
    except ValueError:
        limit = 50
    limit = max(1, min(limit, 500))

    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM sensor_readings ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()

    return jsonify({
        "success": True,
        "count": len(rows),
        "data": [row_to_dict(row) for row in rows],
    })


@app.route("/api/areas", methods=["GET", "POST", "OPTIONS"])
def areas():
    if request.method == "OPTIONS":
        return ("", 204)

    if request.method == "POST":
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"success": False, "message": "Expected JSON body"}), 400

        area = str(payload.get("area") or payload.get("name") or "").strip()
        try:
            moisture = float(payload["moisture"])
        except (KeyError, TypeError, ValueError):
            return jsonify({
                "success": False,
                "message": "moisture must be a number",
            }), 400

        if not area:
            return jsonify({"success": False, "message": "area/name is required"}), 400
        if not 0 <= moisture <= 100:
            return jsonify({"success": False, "message": "moisture must be 0-100"}), 400

        timestamp = now_iso()
        with get_db() as conn:
            cursor = conn.execute(
                "INSERT INTO area_readings (area, moisture, timestamp) VALUES (?, ?, ?)",
                (area, moisture, timestamp),
            )
            conn.commit()

        return jsonify({
            "success": True,
            "data": {
                "id": cursor.lastrowid,
                "area": area,
                "moisture": moisture,
                "timestamp": timestamp,
            },
        }), 201

    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, area, moisture, timestamp FROM area_readings ORDER BY id DESC"
        ).fetchall()

    return jsonify({
        "success": True,
        "count": len(rows),
        "data": [dict(row) for row in rows],
    })


@app.post("/api/recommendation")
def recommendation():
    payload = request.get_json(silent=True) or {}
    crop = str(payload.get("crop") or "crop").strip()
    stage = str(payload.get("stage") or "vegetative").strip()
    moisture_value = payload.get("moisture")

    try:
        moisture = float(moisture_value)
    except (TypeError, ValueError):
        # If the request doesn't include moisture, use latest sensor value.
        with get_db() as conn:
            row = conn.execute(
                "SELECT moisture FROM sensor_readings ORDER BY id DESC LIMIT 1"
            ).fetchone()
        moisture = float(row["moisture"]) if row else None

    try:
        rain_probability = float(payload.get("rain_probability", 0) or 0)
    except (TypeError, ValueError):
        rain_probability = 0

    if moisture is None:
        advice = "Waiting for a soil-moisture reading. Check the sensor connection."
        condition = "Unknown"
        irrigation = "Unavailable"
    elif moisture < 30:
        condition = "Low"
        if rain_probability >= 60:
            advice = "Soil moisture is low, but rain is likely. Recheck soil moisture soon before irrigating."
            irrigation = "Recheck soon; consider rain forecast"
        else:
            advice = "Soil moisture is low. Irrigation may be needed; check crop and soil conditions."
            irrigation = "Consider irrigation soon"
    elif moisture < 70:
        condition = "Adequate"
        advice = "Moisture is in a moderate range. Keep monitoring and consider crop stage and weather."
        irrigation = "Recheck later"
    else:
        condition = "High"
        advice = "Moisture is high. Avoid adding water until the soil is checked again."
        irrigation = "No irrigation for now"

    return jsonify({
        "success": True,
        "crop": crop,
        "stage": stage,
        "moisture": moisture,
        "soil_condition": condition,
        "rain_probability": rain_probability,
        "irrigation_recommendation": irrigation,
        "recommendation": advice,
        "timestamp": now_iso(),
    })


@app.errorhandler(404)
def not_found(_error):
    return jsonify({"success": False, "message": "Endpoint not found"}), 404


@app.errorhandler(500)
def internal_error(_error):
    app.logger.exception("Unexpected backend error")
    return jsonify({"success": False, "message": "Internal server error"}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)
