# data.py
# ---------------------------------------------------------
# Unified Air Quality Data Access Module
#
# Urban Air Quality Assistant
# Supports:
# 1. Demo Mode (synthetic placeholder data for Delhi, Bengaluru,
#    Mumbai, Chennai, Kolkata).
# 2. OpenAQ Mode (live verified measurements from Koramangala,
#    Bengaluru station via data_openaq.py).
#
# PM2.5 is reported in micrograms per cubic metre (µg/m³).
# It is NOT an AQI score.
# ---------------------------------------------------------

from datetime import datetime

# ------------------------------------------------------------------
# SAMPLE DATA — NOT LIVE (Used strictly when in Demo mode)
# ------------------------------------------------------------------
SAMPLE_AIR_QUALITY: dict[str, dict] = {
    "Delhi": {
        "city": "Delhi",
        "station_name": "Central Delhi (Demo Station)",
        "pm25_ugm3": 142.5,
        "unit": "µg/m³",
        "parameter": "PM2.5",
        "measurement_time_ist": "2026-11-24 06:00:00 IST",
        "fetch_time_ist": "2026-11-24 06:00:00 IST",
        "reading_age_str": "Demo data",
        "location_note": "Central Delhi (illustrative)",
        "is_sample": True,
        "source_mode": "demo",
        "provider": "Synthetic Demo",
        "is_stale": False,
    },
    "Bengaluru": {
        "city": "Bengaluru",
        "station_name": "Central Bengaluru (Demo Station)",
        "pm25_ugm3": 48.3,
        "unit": "µg/m³",
        "parameter": "PM2.5",
        "measurement_time_ist": "2026-11-24 06:00:00 IST",
        "fetch_time_ist": "2026-11-24 06:00:00 IST",
        "reading_age_str": "Demo data",
        "location_note": "Central Bengaluru (illustrative)",
        "is_sample": True,
        "source_mode": "demo",
        "provider": "Synthetic Demo",
        "is_stale": False,
    },
    "Mumbai": {
        "city": "Mumbai",
        "station_name": "Central Mumbai (Demo Station)",
        "pm25_ugm3": 87.1,
        "unit": "µg/m³",
        "parameter": "PM2.5",
        "measurement_time_ist": "2026-11-24 06:00:00 IST",
        "fetch_time_ist": "2026-11-24 06:00:00 IST",
        "reading_age_str": "Demo data",
        "location_note": "Central Mumbai (illustrative)",
        "is_sample": True,
        "source_mode": "demo",
        "provider": "Synthetic Demo",
        "is_stale": False,
    },
    "Chennai": {
        "city": "Chennai",
        "station_name": "Central Chennai (Demo Station)",
        "pm25_ugm3": 61.4,
        "unit": "µg/m³",
        "parameter": "PM2.5",
        "measurement_time_ist": "2026-11-24 06:00:00 IST",
        "fetch_time_ist": "2026-11-24 06:00:00 IST",
        "reading_age_str": "Demo data",
        "location_note": "Central Chennai (illustrative)",
        "is_sample": True,
        "source_mode": "demo",
        "provider": "Synthetic Demo",
        "is_stale": False,
    },
    "Kolkata": {
        "city": "Kolkata",
        "station_name": "Central Kolkata (Demo Station)",
        "pm25_ugm3": 110.8,
        "unit": "µg/m³",
        "parameter": "PM2.5",
        "measurement_time_ist": "2026-11-24 06:00:00 IST",
        "fetch_time_ist": "2026-11-24 06:00:00 IST",
        "reading_age_str": "Demo data",
        "location_note": "Central Kolkata (illustrative)",
        "is_sample": True,
        "source_mode": "demo",
        "provider": "Synthetic Demo",
        "is_stale": False,
    },
}


def get_demo_air_quality(city: str) -> dict:
    """Return synthetic sample record for the given city."""
    if city not in SAMPLE_AIR_QUALITY:
        available = ", ".join(SAMPLE_AIR_QUALITY.keys())
        raise KeyError(f"City '{city}' not found in demo data. Available: {available}")
    return dict(SAMPLE_AIR_QUALITY[city])


def get_air_quality(
    city: str = "Bengaluru",
    source_mode: str = "demo",
    force_refresh: bool = False,
) -> dict:
    """
    Unified entry point for retrieving air quality data.

    Parameters
    ----------
    city : str
        City name (used in demo mode).
    source_mode : str
        'demo' or 'openaq'.
    force_refresh : bool
        If True and source_mode == 'openaq', forces network request bypassing cache.
    """
    if source_mode == "openaq":
        from data_openaq import fetch_koramangala_pm25
        return fetch_koramangala_pm25(force_refresh=force_refresh)
    else:
        return get_demo_air_quality(city)
