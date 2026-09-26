from flask import Flask, request, jsonify
from flask_cors import CORS
import requests

from database import (
    init_database,
    save_sensor_reading,
    get_latest_reading,
    get_sensor_history,
    save_area_reading,
    get_area_readings
)

from irrigation import get_irrigation_recommendation


app = Flask(__name__)
CORS(app)

# Initialize SQLite database
init_database()


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():
    return jsonify({
        "status": "online",
        "message": "SoilSense backend is running",
        "version": "1.0"
    })


# =========================================================
# SENSOR API
# =========================================================

@app.route("/api/sensor", methods=["GET"])
def get_sensor():

    data = get_latest_reading()

    if data is None:
        return jsonify({
            "moisture": None,
            "temperature": None,
            "humidity": None,
            "timestamp": None
        })

    return jsonify({
        "id": data["id"],
        "sensor_id": data["sensor_id"],
        "moisture": data["moisture"],
        "temperature": data["temperature"],
        "humidity": data["humidity"],
        "timestamp": data["timestamp"]
    })


@app.route("/api/sensor", methods=["POST"])
def post_sensor():

    data = request.get_json()

    if not data:
        return jsonify({
            "error": "No JSON data received"
        }), 400

    moisture = data.get("moisture")
    temperature = data.get("temperature")
    humidity = data.get("humidity")
    sensor_id = data.get("sensor_id", "main_sensor")

    if moisture is None:
        return jsonify({
            "error": "Moisture value is required"
        }), 400

    try:
        moisture = float(moisture)

        if temperature is not None:
            temperature = float(temperature)

        if humidity is not None:
            humidity = float(humidity)

    except (TypeError, ValueError):
        return jsonify({
            "error": "Sensor values must be numbers"
        }), 400

    if moisture < 0 or moisture > 100:
        return jsonify({
            "error": "Moisture must be between 0 and 100"
        }), 400

    save_sensor_reading(
        moisture=moisture,
        temperature=temperature,
        humidity=humidity,
        sensor_id=sensor_id
    )

    return jsonify({
        "success": True,
        "message": "Sensor reading saved",
        "data": {
            "sensor_id": sensor_id,
            "moisture": moisture,
            "temperature": temperature,
            "humidity": humidity
        }
    })


# =========================================================
# SENSOR HISTORY
# =========================================================

@app.route("/api/sensor/history", methods=["GET"])
def sensor_history():

    try:
        limit = int(request.args.get("limit", 20))
    except ValueError:
        limit = 20

    limit = max(1, min(limit, 100))

    history = get_sensor_history(limit)

    return jsonify({
        "success": True,
        "count": len(history),
        "data": history
    })


# =========================================================
# WEATHER API
# =========================================================

@app.route("/api/weather", methods=["GET"])
def get_weather():

    location = request.args.get("location")

    if not location:
        return jsonify({
            "error": "Location is required"
        }), 400

    try:

        # -----------------------------------------
        # Find latitude and longitude
        # -----------------------------------------

        geo_url = "https://geocoding-api.open-meteo.com/v1/search"

        geo_params = {
            "name": location,
            "count": 1,
            "language": "en",
            "format": "json"
        }

        geo_response = requests.get(
            geo_url,
            params=geo_params,
            timeout=10
        )

        geo_response.raise_for_status()

        geo_data = geo_response.json()

        if "results" not in geo_data or not geo_data["results"]:
            return jsonify({
                "error": "Location not found"
            }), 404

        place = geo_data["results"][0]

        latitude = place["latitude"]
        longitude = place["longitude"]

        # -----------------------------------------
        # Get weather
        # -----------------------------------------

        weather_url = "https://api.open-meteo.com/v1/forecast"

        weather_params = {
            "latitude": latitude,
            "longitude": longitude,
            "current": ",".join([
                "temperature_2m",
                "relative_humidity_2m",
                "precipitation",
                "wind_speed_10m"
            ]),
            "hourly": ",".join([
                "temperature_2m",
                "relative_humidity_2m",
                "precipitation_probability",
                "precipitation",
                "wind_speed_10m"
            ]),
            "forecast_days": 1,
            "timezone": "auto"
        }

        weather_response = requests.get(
            weather_url,
            params=weather_params,
            timeout=10
        )

        weather_response.raise_for_status()

        weather_data = weather_response.json()

        current = weather_data.get("current", {})
        hourly = weather_data.get("hourly", {})

        rain_probability = 0

        probabilities = hourly.get(
            "precipitation_probability",
            []
        )

        if probabilities:
            rain_probability = max(probabilities[:6])

        return jsonify({
            "success": True,

            "location": {
                "name": place.get("name"),
                "country": place.get("country"),
                "latitude": latitude,
                "longitude": longitude
            },

            "current": {
                "temperature": current.get("temperature_2m"),
                "humidity": current.get("relative_humidity_2m"),
                "rainfall": current.get("precipitation"),
                "wind_speed": current.get("wind_speed_10m")
            },

            "forecast": {
                "rain_probability": rain_probability
            }
        })

    except requests.RequestException as e:

        return jsonify({
            "error": "Weather service unavailable",
            "details": str(e)
        }), 503

    except Exception as e:

        return jsonify({
            "error": "Unable to get weather data",
            "details": str(e)
        }), 500


# =========================================================
# AREA / FIELD ANALYSIS
# =========================================================

@app.route("/api/areas", methods=["GET"])
def get_areas():

    areas = get_area_readings()

    if not areas:
        return jsonify({
            "success": True,
            "count": 0,
            "average_moisture": None,
            "areas": []
        })

    moisture_values = [
        float(area["moisture"])
        for area in areas
    ]

    average = sum(moisture_values) / len(moisture_values)

    for area in areas:

        moisture = float(area["moisture"])

        if moisture < average - 10:
            status = "dry"

        elif moisture > average + 10:
            status = "wet"

        else:
            status = "normal"

        area["status"] = status

    return jsonify({
        "success": True,
        "count": len(areas),
        "average_moisture": round(average, 2),
        "areas": areas
    })


@app.route("/api/areas", methods=["POST"])
def post_area():

    data = request.get_json()

    if not data:
        return jsonify({
            "error": "No JSON data received"
        }), 400

    area = data.get("area")
    moisture = data.get("moisture")

    if area is None or moisture is None:
        return jsonify({
            "error": "Area and moisture are required"
        }), 400

    try:
        moisture = float(moisture)
    except (TypeError, ValueError):

        return jsonify({
            "error": "Moisture must be a number"
        }), 400

    if moisture < 0 or moisture > 100:

        return jsonify({
            "error": "Moisture must be between 0 and 100"
        }), 400

    save_area_reading(
        area=area,
        moisture=moisture
    )

    return jsonify({
        "success": True,
        "message": "Area reading saved",
        "data": {
            "area": area,
            "moisture": moisture
        }
    })


# =========================================================
# IRRIGATION RECOMMENDATION
# =========================================================

@app.route("/api/recommendation", methods=["POST"])
def recommendation():

    data = request.get_json()

    if not data:
        return jsonify({
            "error": "No JSON data received"
        }), 400

    crop = data.get("crop")
    stage = data.get("stage")
    moisture = data.get("moisture")
    temperature = data.get("temperature")
    humidity = data.get("humidity")
    rain_probability = data.get("rain_probability", 0)

    if crop is None:
        return jsonify({
            "error": "Crop is required"
        }), 400

    if stage is None:
        return jsonify({
            "error": "Crop stage is required"
        }), 400

    if moisture is None:
        return jsonify({
            "error": "Moisture is required"
        }), 400

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
        "stage": stage,
        "result": result
    })


# =========================================================
# COMBINED ADVISOR API
# =========================================================

@app.route("/api/advisor", methods=["POST"])
def advisor():

    data = request.get_json()

    if not data:
        return jsonify({
            "error": "No JSON data received"
        }), 400

    location = data.get("location")
    crop = data.get("crop")
    stage = data.get("stage")
    moisture = data.get("moisture")

    if not crop or not stage or moisture is None:
        return jsonify({
            "error": "Location, crop, stage and moisture are required"
        }), 400

    # -----------------------------------------
    # Weather
    # -----------------------------------------

    weather = None

    if location:

        try:

            geo_url = "https://geocoding-api.open-meteo.com/v1/search"

            geo_params = {
                "name": location,
                "count": 1,
                "language": "en",
                "format": "json"
            }

            geo_response = requests.get(
                geo_url,
                params=geo_params,
                timeout=10
            )

            geo_response.raise_for_status()

            geo_data = geo_response.json()

            if geo_data.get("results"):

                place = geo_data["results"][0]

                latitude = place["latitude"]
                longitude = place["longitude"]

                weather_url = "https://api.open-meteo.com/v1/forecast"

                weather_params = {
                    "latitude": latitude,
                    "longitude": longitude,
                    "current": ",".join([
                        "temperature_2m",
                        "relative_humidity_2m",
                        "precipitation",
                        "wind_speed_10m"
                    ]),
                    "hourly": "precipitation_probability",
                    "forecast_days": 1,
                    "timezone": "auto"
                }

                weather_response = requests.get(
                    weather_url,
                    params=weather_params,
                    timeout=10
                )

                weather_response.raise_for_status()

                weather_data = weather_response.json()

                current = weather_data.get("current", {})
                hourly = weather_data.get("hourly", {})

                probabilities = hourly.get(
                    "precipitation_probability",
                    []
                )

                rain_probability = 0

                if probabilities:
                    rain_probability = max(probabilities[:6])

                weather = {
                    "temperature": current.get("temperature_2m"),
                    "humidity": current.get(
                        "relative_humidity_2m"
                    ),
                    "rainfall": current.get(
                        "precipitation"
                    ),
                    "wind_speed": current.get(
                        "wind_speed_10m"
                    ),
                    "rain_probability": rain_probability
                }

        except Exception:
            weather = None

    # -----------------------------------------
    # Recommendation
    # -----------------------------------------

    if weather:

        temperature = weather["temperature"]
        humidity = weather["humidity"]
        rain_probability = weather["rain_probability"]

    else:

        temperature = None
        humidity = None
        rain_probability = 0

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

        "input": {
            "location": location,
            "crop": crop,
            "stage": stage,
            "moisture": moisture
        },

        "weather": weather,

        "recommendation": result
    })


# =========================================================
# RUN SERVER
# =========================================================

if __name__ == "__main__":
    print("===================================")
    print("       SoilSense Backend")
    print("===================================")
    print("Server running on:")
    print("http://127.0.0.1:5000")
    print("===================================")

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )