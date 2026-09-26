from crop_data import get_stage_data


def get_irrigation_recommendation(
    crop,
    stage,
    moisture,
    temperature=None,
    humidity=None,
    rain_probability=0
):
    """
    Generate irrigation recommendation based on
    crop, growth stage, soil moisture and weather.
    """

    # Check crop and stage
    stage_data = get_stage_data(crop, stage)

    if stage_data is None:
        return {
            "status": "unavailable",
            "recommendation": "Crop or crop stage is not supported.",
            "reason": "No crop-specific data available."
        }

    # Convert values safely
    try:
        moisture = float(moisture)
    except (TypeError, ValueError):
        return {
            "status": "error",
            "recommendation": "Invalid soil moisture value.",
            "reason": "Moisture must be a number."
        }

    try:
        rain_probability = float(rain_probability or 0)
    except (TypeError, ValueError):
        rain_probability = 0

    min_moisture = stage_data["min_moisture"]
    optimal_min = stage_data["optimal_min"]
    optimal_max = stage_data["optimal_max"]

    # ------------------------------------------------
    # 1. Soil is too dry
    # ------------------------------------------------
    if moisture < min_moisture:

        # High chance of rain
        if rain_probability >= 60:
            return {
                "status": "wait",
                "recommendation": "Soil moisture is low, but rain is likely. Monitor the field before irrigating.",
                "reason": f"Soil moisture is {moisture}%, below the minimum level of {min_moisture}%, with {rain_probability}% rain probability.",
                "moisture": moisture,
                "minimum_moisture": min_moisture,
                "optimal_range": f"{optimal_min}-{optimal_max}%"
            }

        # Low chance of rain
        return {
            "status": "irrigate",
            "recommendation": "Irrigation is recommended.",
            "reason": f"Soil moisture is {moisture}%, below the minimum level of {min_moisture}%.",
            "moisture": moisture,
            "minimum_moisture": min_moisture,
            "optimal_range": f"{optimal_min}-{optimal_max}%"
        }

    # ------------------------------------------------
    # 2. Soil moisture is within optimal range
    # ------------------------------------------------
    if optimal_min <= moisture <= optimal_max:
        return {
            "status": "good",
            "recommendation": "Soil moisture is at a suitable level. Irrigation is not required now.",
            "reason": f"Soil moisture is within the recommended range of {optimal_min}-{optimal_max}%.",
            "moisture": moisture,
            "minimum_moisture": min_moisture,
            "optimal_range": f"{optimal_min}-{optimal_max}%"
        }

    # ------------------------------------------------
    # 3. Soil moisture is above optimal range
    # ------------------------------------------------
    if moisture > optimal_max:
        return {
            "status": "high",
            "recommendation": "Soil moisture is high. Avoid irrigation for now.",
            "reason": f"Soil moisture is {moisture}%, above the upper recommended level of {optimal_max}%.",
            "moisture": moisture,
            "minimum_moisture": min_moisture,
            "optimal_range": f"{optimal_min}-{optimal_max}%"
        }

    # ------------------------------------------------
    # 4. Between minimum and optimal minimum
    # ------------------------------------------------
    return {
        "status": "monitor",
        "recommendation": "Soil moisture is slightly low. Monitor the field.",
        "reason": f"Soil moisture is {moisture}%, between the minimum and optimal levels.",
        "moisture": moisture,
        "minimum_moisture": min_moisture,
        "optimal_range": f"{optimal_min}-{optimal_max}%"
    }