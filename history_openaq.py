# history_openaq.py
# ---------------------------------------------------------------------------
# OpenAQ v3 Historical Data Access & Analysis for Bengaluru (Koramangala)
#
# Urban Air Quality Assistant — Milestone 2 Historical Analysis
#
# Requirements & Rules:
# - Targets Location ID: 6206921, Sensor ID: 15203555 (strictly pm25 in µg/m³)
# - Never mixes stations or pollutants.
# - Never creates historical values from the latest reading.
# - Does not substitute synthetic data.
# - Supports ranges: past 24 hours (default), past 7 days (optional).
# - Timezone: Asia/Kolkata (IST) for display.
# - Python-calculated summary statistics: Min, Max, Valid observation count,
#   Data start and end times.
# - Deduplicates records by timestamp, sorts chronologically, preserves 0.0 values.
# - Bounded pagination, 5-minute memory cache, rate-limit awareness.
# - Does NOT compute AQI, forecasts, or health categories.
# - Clearly distinguishes single-station history from a citywide average.
# ---------------------------------------------------------------------------

import os
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import requests
import pandas as pd
import altair as alt

OPENAQ_BASE_URL = "https://api.openaq.org/v3"
KORAMANGALA_LOCATION_ID = 6206921
VERIFIED_PM25_SENSOR_ID = 15203555
EXPECTED_PARAMETER = "pm25"
VALID_PM25_UNITS = frozenset({"µg/m³", "ug/m3", "ug/m³", "µg/m3"})

REQUEST_TIMEOUT_S = 15
CACHE_TTL_SECONDS = 300.0  # 5-minute cache

# In-memory cache keyed by hours: { 24: {"timestamp": float, "data": dict}, 168: {...} }
_HISTORY_CACHE: dict[int, dict] = {}


def _get_api_key() -> str:
    key = os.environ.get("OPENAQ_API_KEY", "").strip()
    if not key:
        raise EnvironmentError(
            "OPENAQ_API_KEY environment variable is not set. "
            "Please configure OPENAQ_API_KEY in your environment."
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


def invalidate_history_cache() -> None:
    """Clear historical data cache."""
    global _HISTORY_CACHE
    _HISTORY_CACHE.clear()


def process_raw_measurements(records: list[dict], range_hours: int) -> dict:
    """
    Deduplicate, validate, sort, and calculate summary statistics for raw records.

    Parameters
    ----------
    records : list[dict]
        Raw OpenAQ measurement items.
    range_hours : int
        Requested time window in hours (e.g. 24 or 168).

    Returns
    -------
    dict
        Structured dict with:
        - "df": pandas.DataFrame with columns ['datetime_utc', 'datetime_ist', 'pm25']
        - "summary": dict of Min, Max, Count, Start time, End time
        - "status": "ok" | "insufficient_data"
        - "message": description
    """
    if not records:
        return {
            "status": "insufficient_data",
            "message": "No historical measurements available from this sensor for the selected time window.",
            "df": pd.DataFrame(),
            "summary": None,
        }

    valid_points = []
    seen_timestamps = set()

    for item in records:
        # 1. Parameter and unit verification
        param_obj = item.get("parameter") or {}
        p_name = (param_obj.get("name") or "").lower()
        p_unit = (param_obj.get("units") or "").lower()

        # If parameter object is populated, ensure it is pm25
        if p_name and p_name not in ("pm25", "pm2.5"):
            continue
        if p_unit and p_unit not in VALID_PM25_UNITS:
            continue

        # 2. Extract value (preserve valid 0.0 values, skip nulls)
        val = item.get("value")
        if val is None or not isinstance(val, (int, float)):
            continue
        val = float(val)

        # 3. Extract timestamp (prefer period.datetimeTo or period.datetimeFrom or datetime.utc)
        period = item.get("period") or {}
        dt_to = period.get("datetimeTo") or {}
        dt_utc_str = dt_to.get("utc") if isinstance(dt_to, dict) else None

        if not dt_utc_str:
            dt_from = period.get("datetimeFrom") or {}
            dt_utc_str = dt_from.get("utc") if isinstance(dt_from, dict) else None

        if not dt_utc_str:
            dt_obj = item.get("datetime") or {}
            dt_utc_str = dt_obj.get("utc") if isinstance(dt_obj, dict) else None

        dt_utc = _parse_iso_utc(dt_utc_str)
        if dt_utc is None:
            continue

        # 4. Deduplicate by exact UTC timestamp
        ts_iso = dt_utc.isoformat()
        if ts_iso in seen_timestamps:
            continue
        seen_timestamps.add(ts_iso)

        dt_ist = dt_utc.astimezone(ZoneInfo("Asia/Kolkata"))
        valid_points.append({
            "datetime_utc": dt_utc,
            "datetime_ist": dt_ist,
            "pm25": val,
        })

    if len(valid_points) < 2:
        return {
            "status": "insufficient_data",
            "message": f"Insufficient historical data ({len(valid_points)} valid observation found; minimum 2 required for trend analysis).",
            "df": pd.DataFrame(),
            "summary": None,
        }

    # Sort chronologically
    valid_points.sort(key=lambda x: x["datetime_utc"])

    df = pd.DataFrame(valid_points)
    min_val = float(df["pm25"].min())
    max_val = float(df["pm25"].max())
    count = len(df)
    start_time_ist = df["datetime_ist"].iloc[0].strftime("%Y-%m-%d %H:%M IST")
    end_time_ist = df["datetime_ist"].iloc[-1].strftime("%Y-%m-%d %H:%M IST")

    summary = {
        "min_val": min_val,
        "max_val": max_val,
        "valid_count": count,
        "start_time_ist": start_time_ist,
        "end_time_ist": end_time_ist,
        "station_name": "Koramangala, Bengaluru",
        "location_id": KORAMANGALA_LOCATION_ID,
        "sensor_id": VERIFIED_PM25_SENSOR_ID,
        "units": "µg/m³",
    }

    return {
        "status": "ok",
        "message": f"Retrieved {count} valid observations over the selected period.",
        "df": df,
        "summary": summary,
    }


def fetch_sensor_history(range_hours: int = 24, force_refresh: bool = False) -> dict:
    """
    Fetch historical PM2.5 measurements for sensor 15203555 from OpenAQ v3.

    Parameters
    ----------
    range_hours : int
        Time window in hours (24 for 1 day, 168 for 7 days).
    force_refresh : bool
        If True, ignores cached result and fetches fresh network data.

    Returns
    -------
    dict
        Processed history containing DataFrame, summary statistics, and status.
    """
    global _HISTORY_CACHE

    now_mono = time.monotonic()
    if not force_refresh and range_hours in _HISTORY_CACHE:
        cache_entry = _HISTORY_CACHE[range_hours]
        if (now_mono - cache_entry["timestamp"]) < CACHE_TTL_SECONDS:
            return cache_entry["data"]

    api_key = _get_api_key()
    headers = _get_headers(api_key)

    now_utc = datetime.now(timezone.utc)
    from_utc = now_utc - timedelta(hours=range_hours)

    from_iso = from_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    to_iso = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")

    url = f"{OPENAQ_BASE_URL}/sensors/{VERIFIED_PM25_SENSOR_ID}/measurements"
    
    all_records: list[dict] = []
    max_pages = 1 if range_hours <= 24 else 3
    limit = 100

    for page in range(1, max_pages + 1):
        params = {
            "datetime_from": from_iso,
            "datetime_to": to_iso,
            "limit": limit,
            "page": page,
        }
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=REQUEST_TIMEOUT_S)
        except requests.exceptions.Timeout:
            raise RuntimeError(f"OpenAQ historical request timed out after {REQUEST_TIMEOUT_S}s.")
        except requests.exceptions.ConnectionError as exc:
            raise RuntimeError(f"Network error querying OpenAQ historical data: {exc}")

        if resp.status_code in (401, 403):
            raise PermissionError(
                f"OpenAQ authentication failed (HTTP {resp.status_code}). "
                "Please verify your OPENAQ_API_KEY environment variable."
            )
        if resp.status_code == 429:
            raise RuntimeError("OpenAQ rate limit reached (HTTP 429). Please wait before refreshing historical data.")
        if resp.status_code != 200:
            raise RuntimeError(f"OpenAQ historical query failed (HTTP {resp.status_code}): {resp.text[:200]}")

        data = resp.json()
        results = data.get("results", [])
        if not results:
            break
        all_records.extend(results)
        if len(results) < limit:
            break

    result = process_raw_measurements(all_records, range_hours)

    _HISTORY_CACHE[range_hours] = {
        "timestamp": now_mono,
        "data": result,
    }

    return result


def build_history_chart(df: pd.DataFrame) -> alt.Chart:
    """Build a mobile-responsive Altair time-series chart with point markers."""
    chart = (
        alt.Chart(df)
        .mark_line(
            color="#49df94",
            point=alt.OverlayMarkDef(color="#49df94", size=50, filled=True),
            strokeWidth=2.2,
        )
        .encode(
            x=alt.X(
                "datetime_ist:T",
                title="Time (Asia/Kolkata)",
                axis=alt.Axis(
                    format="%b %d, %H:%M",
                    labelColor="#8ab8a1",
                    titleColor="#8ab8a1",
                    gridColor="#183627",
                    labelAngle=-25,
                ),
            ),
            y=alt.Y(
                "pm25:Q",
                title="PM2.5 (µg/m³)",
                scale=alt.Scale(zero=False),
                axis=alt.Axis(
                    labelColor="#8ab8a1",
                    titleColor="#8ab8a1",
                    gridColor="#183627",
                ),
            ),
            tooltip=[
                alt.Tooltip("datetime_ist:T", title="Observation Time (IST)", format="%Y-%m-%d %H:%M:%S"),
                alt.Tooltip("pm25:Q", title="PM2.5 (µg/m³)", format=".1f"),
            ],
        )
        .properties(
            background="transparent",
            height=260,
        )
        .configure_view(strokeOpacity=0)
    )
    return chart
