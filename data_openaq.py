# data_openaq.py
# ---------------------------------------------------------------------------
# OpenAQ v3 Data Access Module for Bengaluru (Koramangala Station)
#
# Urban Air Quality Assistant — Milestone 2 Live Data Integration
#
# Responsibilities:
# 1. Fetch live measurements from OpenAQ v3 for location 6206921.
# 2. Verify that sensor 15203555 is strictly 'pm25' measuring in 'µg/m³'.
# 3. Match measurement strictly to sensor 15203555.
# 4. Enforce 5-minute cache TTL with force_refresh bypass support.
# 5. Dynamically calculate reading age against measurement timestamp.
# 6. Distinguish measurement timestamp from API fetch time.
# 7. Provide detailed provenance (OpenAQ, original provider AirGradient).
# 8. Never silently fallback to demo data on errors.
# ---------------------------------------------------------------------------

import os
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import requests

# ── Configuration Constants ────────────────────────────────────────────────
OPENAQ_BASE_URL = "https://api.openaq.org/v3"
KORAMANGALA_LOCATION_ID = 6206921
VERIFIED_PM25_SENSOR_ID = 15203555
EXPECTED_PARAMETER = "pm25"
VALID_PM25_UNITS = frozenset({"µg/m³", "ug/m3", "ug/m³", "µg/m3"})

REQUEST_TIMEOUT_S = 15
CACHE_TTL_SECONDS = 300.0  # 5 minutes TTL
FRESHNESS_THRESHOLD_HOURS = 24.0  # Application freshness threshold policy

# In-memory module cache: { "timestamp": float, "data": dict }
_CACHE: dict = {
    "timestamp": 0.0,
    "data": None,
}


def _get_api_key() -> str:
    """Retrieve OPENAQ_API_KEY from environment without exposing its value."""
    key = os.environ.get("OPENAQ_API_KEY", "").strip()
    if not key:
        raise EnvironmentError(
            "OPENAQ_API_KEY environment variable is not set. "
            "Please configure OPENAQ_API_KEY in your Windows environment variables."
        )
    return key


def _get_headers(api_key: str) -> dict:
    return {
        "X-API-Key": api_key,
        "Accept": "application/json",
        "User-Agent": "UrbanAirQualityAssistant/2.0",
    }


def _parse_iso_utc(dt_str: str | None) -> datetime | None:
    if not dt_str:
        return None
    try:
        clean = dt_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def format_reading_age(seconds: float | None) -> str:
    """Format duration in seconds into a clean human-readable string."""
    if seconds is None:
        return "Unknown"
    if seconds < 0:
        return "just now"
    total_minutes = int(seconds // 60)
    hours = total_minutes // 60
    minutes = total_minutes % 60
    days = hours // 24
    rem_hours = hours % 24

    if days > 0:
        return f"{days}d {rem_hours}h {minutes}m ago"
    if hours > 0:
        return f"{hours}h {minutes}m ago"
    return f"{minutes}m ago"


def recalculate_reading_age(dt_utc: datetime | None) -> tuple[float | None, str, bool]:
    """Dynamically compute reading age in seconds, formatted string, and stale flag."""
    if dt_utc is None:
        return None, "Unknown", True
    now_utc = datetime.now(timezone.utc)
    age_s = (now_utc - dt_utc).total_seconds()
    age_str = format_reading_age(age_s)
    is_stale = (age_s is None) or (age_s > FRESHNESS_THRESHOLD_HOURS * 3600.0)
    return age_s, age_str, is_stale


def invalidate_openaq_cache() -> None:
    """Explicitly invalidate in-memory cache to force next call to hit network."""
    global _CACHE
    _CACHE["timestamp"] = 0.0
    _CACHE["data"] = None


def fetch_koramangala_pm25(force_refresh: bool = False) -> dict:
    """
    Fetch and verify the latest PM2.5 measurement from OpenAQ v3 for
    the Koramangala, Bengaluru station.
    """
    global _CACHE

    now_monotonic = time.monotonic()
    if not force_refresh and _CACHE["data"] is not None:
        age = now_monotonic - _CACHE["timestamp"]
        if age < CACHE_TTL_SECONDS:
            # Recompute reading age from measurement timestamp on cached data
            cached = dict(_CACHE["data"])
            meas_time_utc = cached.get("_meas_time_utc_obj")
            age_s, age_str, is_stale = recalculate_reading_age(meas_time_utc)
            cached["reading_age_seconds"] = age_s
            cached["reading_age_str"] = age_str
            cached["is_stale"] = is_stale
            cached["is_cached"] = True
            cached["cache_age_seconds"] = int(age)
            return cached

    # Network fetch
    api_key = _get_api_key()
    headers = _get_headers(api_key)
    fetch_time_utc = datetime.now(timezone.utc)
    fetch_time_ist = fetch_time_utc.astimezone(ZoneInfo("Asia/Kolkata"))

    # 1. Fetch Location details & Provider
    loc_url = f"{OPENAQ_BASE_URL}/locations/{KORAMANGALA_LOCATION_ID}"
    try:
        loc_resp = requests.get(loc_url, headers=headers, timeout=REQUEST_TIMEOUT_S)
    except requests.exceptions.Timeout:
        raise RuntimeError(f"OpenAQ request timed out after {REQUEST_TIMEOUT_S}s while querying location.")
    except requests.exceptions.ConnectionError as exc:
        raise RuntimeError(f"Could not connect to OpenAQ API: {exc}")

    if loc_resp.status_code in (401, 403):
        raise PermissionError(
            f"OpenAQ authentication failed (HTTP {loc_resp.status_code}). "
            "Please check your OPENAQ_API_KEY environment variable."
        )
    if loc_resp.status_code == 429:
        raise RuntimeError("OpenAQ rate limit reached (HTTP 429). Please wait before refreshing.")
    if loc_resp.status_code != 200:
        raise RuntimeError(f"OpenAQ location request failed (HTTP {loc_resp.status_code}): {loc_resp.text[:200]}")

    loc_json = loc_resp.json()
    loc_results = loc_json.get("results", [])
    if not loc_results:
        raise ValueError(f"OpenAQ returned empty results for location ID {KORAMANGALA_LOCATION_ID}.")
    
    loc_obj = loc_results[0]
    station_name = loc_obj.get("name", "Koramangala, Bengaluru")
    coordinates = loc_obj.get("coordinates") or {"latitude": 12.93702, "longitude": 77.61159}
    
    provider_raw = loc_obj.get("provider") or {}
    provider_name = provider_raw.get("name") if isinstance(provider_raw, dict) else str(provider_raw) or "AirGradient"

    # 2. Fetch Sensor list to strictly verify sensor 15203555
    sensors_url = f"{OPENAQ_BASE_URL}/locations/{KORAMANGALA_LOCATION_ID}/sensors"
    try:
        sensors_resp = requests.get(sensors_url, headers=headers, timeout=REQUEST_TIMEOUT_S)
    except requests.exceptions.Timeout:
        raise RuntimeError("OpenAQ request timed out while querying sensors.")
    except requests.exceptions.ConnectionError as exc:
        raise RuntimeError(f"Connection error while querying sensors: {exc}")

    if sensors_resp.status_code != 200:
        raise RuntimeError(f"Failed to fetch sensors for location {KORAMANGALA_LOCATION_ID} (HTTP {sensors_resp.status_code}).")

    sensors_list = sensors_resp.json().get("results", [])
    
    target_sensor = None
    for s in sensors_list:
        if s.get("id") == VERIFIED_PM25_SENSOR_ID:
            target_sensor = s
            break

    if target_sensor is None:
        raise ValueError(
            f"Sensor ID {VERIFIED_PM25_SENSOR_ID} was not found at station {station_name} (Location {KORAMANGALA_LOCATION_ID}). "
            "Station configuration has changed; refusing to select an arbitrary sensor."
        )

    param_obj = target_sensor.get("parameter") or {}
    param_name = (param_obj.get("name") or "").lower()
    param_units = (param_obj.get("units") or "").lower()

    if param_name not in ("pm25", "pm2.5") or param_units not in VALID_PM25_UNITS:
        raise ValueError(
            f"Sensor metadata mismatch on sensor {VERIFIED_PM25_SENSOR_ID}: "
            f"expected pm25 in µg/m³, but found '{param_name}' in '{param_units}'. "
            "Refusing to substitute a different pollutant."
        )

    # 3. Fetch latest measurement
    latest_url = f"{OPENAQ_BASE_URL}/locations/{KORAMANGALA_LOCATION_ID}/latest"
    try:
        latest_resp = requests.get(latest_url, headers=headers, timeout=REQUEST_TIMEOUT_S)
    except requests.exceptions.Timeout:
        raise RuntimeError("OpenAQ request timed out while fetching latest measurement.")
    except requests.exceptions.ConnectionError as exc:
        raise RuntimeError(f"Connection error while fetching latest measurement: {exc}")

    if latest_resp.status_code != 200:
        raise RuntimeError(f"Failed to fetch latest measurements (HTTP {latest_resp.status_code}).")

    latest_items = latest_resp.json().get("results", [])
    meas_obj = None
    for item in latest_items:
        if item.get("sensorsId") == VERIFIED_PM25_SENSOR_ID:
            meas_obj = item
            break

    val = None
    dt_utc = None

    if meas_obj:
        val = meas_obj.get("value")
        dt_dict = meas_obj.get("datetime") or {}
        utc_str = dt_dict.get("utc") if isinstance(dt_dict, dict) else None
        dt_utc = _parse_iso_utc(utc_str)

    if dt_utc is None and target_sensor.get("datetimeLast"):
        dt_dict = target_sensor.get("datetimeLast")
        utc_str = dt_dict.get("utc") if isinstance(dt_dict, dict) else str(dt_dict)
        dt_utc = _parse_iso_utc(utc_str)

    if val is None:
        raise ValueError(
            f"No valid PM2.5 measurement value returned for sensor {VERIFIED_PM25_SENSOR_ID} at {station_name}."
        )

    age_s, age_str, is_stale = recalculate_reading_age(dt_utc)

    dt_ist = dt_utc.astimezone(ZoneInfo("Asia/Kolkata")) if dt_utc else None
    meas_time_ist_str = dt_ist.strftime("%Y-%m-%d %H:%M:%S IST") if dt_ist else "Unknown"
    meas_time_utc_str = dt_utc.strftime("%Y-%m-%d %H:%M:%S UTC") if dt_utc else "Unknown"

    result = {
        "source_mode": "openaq",
        "city": "Bengaluru",
        "station_name": station_name,
        "location_id": KORAMANGALA_LOCATION_ID,
        "sensor_id": VERIFIED_PM25_SENSOR_ID,
        "pm25_ugm3": float(val),
        "unit": "µg/m³",
        "parameter": "PM2.5",
        "measurement_time_ist": meas_time_ist_str,
        "measurement_time_utc": meas_time_utc_str,
        "fetch_time_ist": fetch_time_ist.strftime("%Y-%m-%d %H:%M:%S IST"),
        "reading_age_seconds": age_s,
        "reading_age_str": age_str,
        "is_stale": is_stale,
        "freshness_threshold_hours": FRESHNESS_THRESHOLD_HOURS,
        "provider": provider_name,
        "is_sample": False,
        "coordinates": coordinates,
        "is_cached": False,
        "cache_age_seconds": 0,
        "_fetch_time_utc_obj": fetch_time_utc,
        "_meas_time_utc_obj": dt_utc,
    }

    _CACHE["timestamp"] = now_monotonic
    _CACHE["data"] = result

    return result
