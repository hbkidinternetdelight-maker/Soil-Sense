from crop_data import CROP_DATA

def get_irrigation_recommendation(crop, stage, moisture, temperature=None, humidity=None, rain_probability=0):
    crop_info = CROP_DATA.get(crop, {})
    stage_info = crop_info.get(stage) or next(iter(crop_info.values()), {})
    minimum = float(stage_info.get("minimum_moisture", 40))
    optimal = stage_info.get("optimal_range", "50-70%")

    try:
        rain = float(rain_probability or 0)
    except (TypeError, ValueError):
        rain = 0

    if moisture < minimum:
        if rain >= 60:
            status = "Delay for now — rain expected"
        else:
            status = "Irrigation recommended"
    elif moisture <= minimum + 10:
        status = "Monitor soil moisture"
    elif moisture <= 80:
        status = "Irrigation not required"
    else:
        status = "Avoid irrigation"

    return {
        "minimum_moisture": minimum,
        "optimal_range": optimal,
        "moisture": moisture,
        "rain_probability": rain,
        "status": status
    }
