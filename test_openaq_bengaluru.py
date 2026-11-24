# test_openaq_bengaluru.py
# ---------------------------------------------------------------------------
# OpenAQ v3 Live-Data Verification for Bengaluru, Karnataka, India
#
# Urban Air Quality Assistant — Milestone 2 Verification Step
#
# Safety & Requirements:
# - Uses OpenAQ v3 (https://api.openaq.org/v3)
# - Reads OPENAQ_API_KEY from environment variables (never printed/logged)
# - Discovers candidate stations in Bengaluru/Bangalore using geographic metadata
# - Prints candidate station names and coordinates
# - Inspects each candidate's sensor metadata
# - Selects ONLY sensors explicitly measuring pm25 in µg/m³ (never assumes index 0)
# - Matches latest measurement to that verified sensor ID
# - Distinguishes measurement timestamp from API fetch time
# - Converts measurement timestamp to UTC and Asia/Kolkata (IST)
# - Calculates reading age and flags freshness against a stated policy threshold
# - Does NOT convert to AQI
# - Does NOT substitute synthetic data or invent station IDs
# - Does NOT label a single station reading as a citywide average
# ---------------------------------------------------------------------------

import os
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import requests

# ── Application Policy ──────────────────────────────────────────────────────
# Freshness threshold: Ambient monitoring stations typically report hourly.
# Data older than 24 hours is flagged as STALE. Data older than 7 days is INACTIVE.
FRESHNESS_THRESHOLD_HOURS = 24.0

OPENAQ_BASE_URL = "https://api.openaq.org/v3"
REQUEST_TIMEOUT_S = 15

# Bengaluru geographic centroid & bounding region
BENGALURU_COORDS = {"lat": 12.9716, "lon": 77.5946}
SEARCH_RADIUS_METERS = 25000  # Max allowed radius in v3 is 25 km
BENGALURU_ALIASES = ("bengaluru", "bangalore")


def get_api_key() -> str:
    """Retrieve OPENAQ_API_KEY without ever printing it."""
    key = os.environ.get("OPENAQ_API_KEY", "").strip()
    if not key:
        raise EnvironmentError(
            "OPENAQ_API_KEY environment variable is not set.\n"
            "Please set it in PowerShell before running this script:\n"
            "  $env:OPENAQ_API_KEY = \"your_api_key_here\""
        )
    return key


def get_headers(api_key: str) -> dict:
    """Construct OpenAQ v3 headers."""
    return {
        "X-API-Key": api_key,
        "Accept": "application/json",
        "User-Agent": "UrbanAirQualityAssistant/1.0",
    }


def format_duration(seconds: float) -> str:
    """Human-readable duration."""
    if seconds < 0:
        return "in the future"
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


def parse_iso_datetime(dt_str: str) -> datetime | None:
    """Parse ISO8601 string to timezone-aware UTC datetime."""
    if not dt_str:
        return None
    try:
        # Handles 'Z' or offset
        clean_str = dt_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def fetch_candidate_stations(headers: dict) -> list[dict]:
    """
    Query OpenAQ v3 for candidate monitoring stations in the Bengaluru area.
    Combines geographic coordinates/radius search and naming filters.
    """
    url = f"{OPENAQ_BASE_URL}/locations"
    
    # 1. Geographic proximity query around Bengaluru (25km radius)
    params = {
        "coordinates": f"{BENGALURU_COORDS['lat']},{BENGALURU_COORDS['lon']}",
        "radius": SEARCH_RADIUS_METERS,
        "limit": 100,
    }

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=REQUEST_TIMEOUT_S)
    except requests.exceptions.Timeout:
        raise RuntimeError(f"Network timeout contacting OpenAQ at {url}")
    except requests.exceptions.ConnectionError as exc:
        raise RuntimeError(f"Network connection failure contacting OpenAQ: {exc}")

    if resp.status_code in (401, 403):
        raise PermissionError(
            f"OpenAQ API authentication failed (HTTP {resp.status_code}). "
            "Please check that your OPENAQ_API_KEY is valid."
        )
    if resp.status_code == 429:
        raise RuntimeError("OpenAQ API rate limit reached (HTTP 429). Please wait before retrying.")
    if resp.status_code != 200:
        raise RuntimeError(f"OpenAQ API error (HTTP {resp.status_code}): {resp.text[:300]}")

    data = resp.json()
    results = data.get("results", [])

    # If coordinate query yielded no results, try country-level search with city name
    if not results:
        alt_params = {"iso": "IN", "limit": 100}
        try:
            alt_resp = requests.get(url, headers=headers, params=alt_params, timeout=REQUEST_TIMEOUT_S)
            if alt_resp.status_code == 200:
                all_in = alt_resp.json().get("results", [])
                results = [
                    loc for loc in all_in
                    if any(alias in (loc.get("name") or "").lower() for alias in BENGALURU_ALIASES)
                    or any(alias in (loc.get("locality") or "").lower() for alias in BENGALURU_ALIASES)
                ]
        except Exception:
            pass

    return results


def fetch_location_sensors(location_id: int, headers: dict) -> list[dict]:
    """Fetch the sensor list and metadata for a specific location."""
    url = f"{OPENAQ_BASE_URL}/locations/{location_id}/sensors"
    try:
        resp = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT_S)
        if resp.status_code == 200:
            return resp.json().get("results", [])
        return []
    except Exception:
        return []


def fetch_latest_measurements(location_id: int, headers: dict) -> list[dict]:
    """Fetch latest measurements for a location."""
    url = f"{OPENAQ_BASE_URL}/locations/{location_id}/latest"
    try:
        resp = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT_S)
        if resp.status_code == 200:
            return resp.json().get("results", [])
        return []
    except Exception:
        return []


def verify_bengaluru():
    fetch_time_utc = datetime.now(timezone.utc)
    fetch_time_ist = fetch_time_utc.astimezone(ZoneInfo("Asia/Kolkata"))

    print("=" * 78)
    print("OPENAQ v3 LIVE DATA VERIFICATION — BENGALURU, KARNATAKA, INDIA")
    print(f"API Fetch Time: {fetch_time_ist.strftime('%Y-%m-%d %H:%M:%S')} IST ({fetch_time_utc.strftime('%Y-%m-%d %H:%M:%S')} UTC)")
    print(f"Freshness Policy Threshold: ≤ {FRESHNESS_THRESHOLD_HOURS} hours for active live status")
    print("=" * 78)

    # 1. API Key check
    api_key = get_api_key()
    headers = get_headers(api_key)

    # 2. Discover Candidate Stations
    print("\n[Step 1] Discovering candidate monitoring stations in Bengaluru region...")
    candidates = fetch_candidate_stations(headers)

    if not candidates:
        print("[-] No candidate stations found in the Bengaluru region matching the criteria.")
        sys.exit(1)

    print(f"[+] Found {len(candidates)} candidate location(s):\n")
    print(f"{'#':<3} {'Location ID':<13} {'Station Name':<42} {'Coordinates (Lat, Lon)'}")
    print("-" * 78)
    for idx, loc in enumerate(candidates, start=1):
        loc_id = loc.get("id", "N/A")
        name = loc.get("name", "Unknown Station")[:40]
        coords = loc.get("coordinates") or {}
        lat = coords.get("latitude")
        lon = coords.get("longitude")
        coord_str = f"{lat:.4f}, {lon:.4f}" if lat is not None and lon is not None else "N/A"
        print(f"{idx:<3} {str(loc_id):<13} {name:<42} {coord_str}")

    # 3. Inspect Each Candidate Station for Valid PM2.5 Sensors & Latest Data
    print("\n[Step 2] Inspecting sensor metadata for explicit PM2.5 in µg/m³...")
    
    verified_candidates = []

    for loc in candidates:
        loc_id = loc.get("id")
        loc_name = loc.get("name", "Unknown Station")
        coords = loc.get("coordinates") or {}
        provider_obj = loc.get("provider") or {}
        provider_name = provider_obj.get("name") if isinstance(provider_obj, dict) else str(provider_obj) or "Unknown Provider"

        # Fetch sensors for this location
        sensors = fetch_location_sensors(loc_id, headers)
        
        # Filter strictly for PM2.5 in µg/m³
        pm25_sensors = []
        for s in sensors:
            param = s.get("parameter") or {}
            p_name = (param.get("name") or "").lower()
            p_units = (param.get("units") or "").lower()
            
            # Check explicit PM2.5 parameter name and valid unit
            if p_name in ("pm25", "pm2.5") and p_units in ("µg/m³", "ug/m3", "ug/m³", "µg/m3"):
                pm25_sensors.append(s)

        if not pm25_sensors:
            continue

        # Fetch latest measurements to get reading
        latest_items = fetch_latest_measurements(loc_id, headers)
        latest_by_sensor_id = {item.get("sensorsId"): item for item in latest_items if item.get("sensorsId")}

        for sensor in pm25_sensors:
            sensor_id = sensor.get("id")
            meas = latest_by_sensor_id.get(sensor_id)

            value = None
            dt_utc = None
            if meas:
                value = meas.get("value")
                dt_obj = meas.get("datetime") or {}
                dt_utc_str = dt_obj.get("utc") if isinstance(dt_obj, dict) else None
                dt_utc = parse_iso_datetime(dt_utc_str)
            
            # If not in /latest, fallback to sensor datetimeLast metadata
            if dt_utc is None and sensor.get("datetimeLast"):
                dt_obj = sensor.get("datetimeLast")
                dt_utc_str = dt_obj.get("utc") if isinstance(dt_obj, dict) else str(dt_obj)
                dt_utc = parse_iso_datetime(dt_utc_str)

            reading_age_s = (fetch_time_utc - dt_utc).total_seconds() if dt_utc else None
            is_fresh = (reading_age_s is not None) and (reading_age_s <= FRESHNESS_THRESHOLD_HOURS * 3600)

            verified_candidates.append({
                "location_id": loc_id,
                "station_name": loc_name,
                "sensor_id": sensor_id,
                "coordinates": coords,
                "provider": provider_name,
                "parameter": "pm25",
                "units": "µg/m³",
                "value": value,
                "datetime_utc": dt_utc,
                "reading_age_s": reading_age_s,
                "is_fresh": is_fresh,
            })

    if not verified_candidates:
        print("[-] None of the candidate stations possessed a verified PM2.5 sensor in µg/m³.")
        sys.exit(1)

    print(f"[+] Found {len(verified_candidates)} verified PM2.5 sensor stream(s).")

    # Sort candidates: prefer ones with fresh readings, then lowest reading age
    def sort_key(c):
        has_val = 0 if c["value"] is not None else 1
        fresh = 0 if c["is_fresh"] else 1
        age = c["reading_age_s"] if c["reading_age_s"] is not None else float("inf")
        return (has_val, fresh, age)

    verified_candidates.sort(key=sort_key)
    selected = verified_candidates[0]

    # 4. Detailed Report on Selected Station & Sensor
    print("\n" + "=" * 78)
    print("VERIFIED MONITORING STATION & SENSOR RESULT")
    print("=" * 78)

    loc_name = selected["station_name"]
    loc_id = selected["location_id"]
    sensor_id = selected["sensor_id"]
    coords = selected["coordinates"]
    lat_str = f"{coords.get('latitude'):.5f}" if coords.get("latitude") is not None else "N/A"
    lon_str = f"{coords.get('longitude'):.5f}" if coords.get("longitude") is not None else "N/A"
    provider = selected["provider"]
    param = selected["parameter"]
    units = selected["units"]
    val = selected["value"]
    dt_utc = selected["datetime_utc"]
    age_s = selected["reading_age_s"]
    is_fresh = selected["is_fresh"]

    if dt_utc:
        dt_ist = dt_utc.astimezone(ZoneInfo("Asia/Kolkata"))
        utc_str = dt_utc.strftime("%Y-%m-%d %H:%M:%S UTC")
        ist_str = dt_ist.strftime("%Y-%m-%d %H:%M:%S IST")
        age_str = format_duration(age_s)
    else:
        utc_str = "Unavailable"
        ist_str = "Unavailable"
        age_str = "Unavailable"

    freshness_status = "FRESH (≤ 24h)" if is_fresh else "STALE / OLD (> 24h threshold)"

    print(f"Station Name        : {loc_name}")
    print(f"Location ID         : {loc_id}")
    print(f"Verified Sensor ID  : {sensor_id}")
    print(f"Sensor Parameter    : {param} (Fine Particulate Matter)")
    print(f"Measurement Units   : {units}")
    print(f"Coordinates         : Lat {lat_str}, Lon {lon_str}")
    print(f"Original Provider   : {provider}")
    print(f"Measurement (UTC)   : {utc_str}")
    print(f"Measurement (IST)   : {ist_str}")
    print(f"API Fetch Time (IST): {fetch_time_ist.strftime('%Y-%m-%d %H:%M:%S IST')}")
    print(f"Calculated Age      : {age_str}")
    print(f"Freshness Status    : {freshness_status}")
    print(f"PM2.5 Concentration : {val if val is not None else 'No recent value'} {units}")
    print("-" * 78)
    print("NOTICE: Single-station observation. NOT a citywide average or AQI score.")
    print("=" * 78)

    # 5. Required Standard Output Format
    print("\n>>> REQUIRED SUMMARY FORMAT:")
    print(
        f"Station: {loc_name} "
        f"Sensor: {sensor_id} "
        f"PM2.5: {val if val is not None else 'N/A'} {units} "
        f"Measured at: {ist_str} "
        f"Reading age: {age_str} "
        f"Provider: {provider}"
    )


if __name__ == "__main__":
    try:
        verify_bengaluru()
    except EnvironmentError as e:
        print(f"\n[CONFIGURATION ERROR] {e}", file=sys.stderr)
        sys.exit(1)
    except PermissionError as e:
        print(f"\n[AUTHENTICATION ERROR] {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] {e}", file=sys.stderr)
        sys.exit(1)
