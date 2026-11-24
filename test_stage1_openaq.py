# test_stage1_openaq.py
# ---------------------------------------------------------------------------
# Test Suite for Stage 1 OpenAQ Live Integration & Validation
# ---------------------------------------------------------------------------

import os
import sys
import time
from unittest.mock import patch, MagicMock
import requests

from data_openaq import (
    fetch_koramangala_pm25,
    invalidate_openaq_cache,
    format_reading_age,
    KORAMANGALA_LOCATION_ID,
    VERIFIED_PM25_SENSOR_ID,
)
from data import get_air_quality, get_demo_air_quality


def run_tests():
    total = 0
    passed = 0

    def test(name, condition, details=""):
        nonlocal total, passed
        total += 1
        if condition:
            print(f"  [PASS] {name}")
            passed += 1
        else:
            print(f"  [FAIL] {name}: {details}")

    print("\n--- Test Suite 1: Live OpenAQ Fetch & Verification ---")
    invalidate_openaq_cache()
    try:
        live_res = fetch_koramangala_pm25(force_refresh=True)
        test("Live fetch returns location 6206921", live_res["location_id"] == KORAMANGALA_LOCATION_ID)
        test("Live fetch verifies sensor 15203555", live_res["sensor_id"] == VERIFIED_PM25_SENSOR_ID)
        test("Parameter is PM2.5 in µg/m³", live_res["parameter"] == "PM2.5" and live_res["unit"] == "µg/m³")
        test("Actual float concentration returned", isinstance(live_res["pm25_ugm3"], float))
        test("Provider is AirGradient", live_res["provider"] == "AirGradient")
        test("Measurement time distinct from fetch time", live_res["measurement_time_ist"] != live_res["fetch_time_ist"])
        test("Reading age calculated", "ago" in live_res["reading_age_str"] or "m" in live_res["reading_age_str"])
    except Exception as e:
        test("Live fetch successful", False, str(e))

    print("\n--- Test Suite 2: 5-Minute Cache TTL & Force Refresh ---")
    try:
        # First call should populate cache
        first = fetch_koramangala_pm25(force_refresh=False)
        # Second call without force_refresh should return cached object
        second = fetch_koramangala_pm25(force_refresh=False)
        test("Second call returns cached object", second.get("is_cached") is True)
        
        # Call with force_refresh should bypass cache
        third = fetch_koramangala_pm25(force_refresh=True)
        test("force_refresh=True bypasses cache", third.get("is_cached") is False)
    except Exception as e:
        test("Cache TTL verification", False, str(e))

    print("\n--- Test Suite 3: Mocked Error & Edge-Case Handling ---")
    invalidate_openaq_cache()

    # 3.1: Timeout Handling
    with patch("requests.get", side_effect=requests.exceptions.Timeout("Timeout")):
        try:
            fetch_koramangala_pm25(force_refresh=True)
            test("Timeout handled with RuntimeError", False, "Expected RuntimeError")
        except RuntimeError as e:
            test("Timeout handled with RuntimeError", "timed out" in str(e).lower())

    # 3.2: 401 Authentication Failure
    mock_401 = MagicMock()
    mock_401.status_code = 401
    mock_401.text = "Unauthorized"
    with patch("requests.get", return_value=mock_401):
        try:
            fetch_koramangala_pm25(force_refresh=True)
            test("401 handled with PermissionError", False, "Expected PermissionError")
        except PermissionError as e:
            test("401 handled with PermissionError", "authentication failed" in str(e).lower())

    # 3.3: 429 Rate Limit
    mock_429 = MagicMock()
    mock_429.status_code = 429
    mock_429.text = "Rate limit"
    with patch("requests.get", return_value=mock_429):
        try:
            fetch_koramangala_pm25(force_refresh=True)
            test("429 handled with rate limit message", False, "Expected RuntimeError")
        except RuntimeError as e:
            test("429 handled with rate limit message", "rate limit" in str(e).lower())

    # 3.4: Sensor Metadata Mismatch (different sensor ID or wrong units)
    mock_loc = MagicMock(status_code=200)
    mock_loc.json.return_value = {"results": [{"name": "Koramangala", "provider": {"name": "AirGradient"}}]}

    mock_wrong_sensor = MagicMock(status_code=200)
    # Sensor has id 99999 instead of 15203555
    mock_wrong_sensor.json.return_value = {"results": [{"id": 99999, "parameter": {"name": "pm25", "units": "µg/m³"}}]}

    with patch("requests.get", side_effect=[mock_loc, mock_wrong_sensor]):
        try:
            fetch_koramangala_pm25(force_refresh=True)
            test("Missing target sensor ID rejected", False, "Expected ValueError on missing sensor")
        except ValueError as e:
            test("Missing target sensor ID rejected", "not found" in str(e).lower())

    # 3.5: Wrong parameter on sensor 15203555
    mock_wrong_param = MagicMock(status_code=200)
    mock_wrong_param.json.return_value = {"results": [{"id": VERIFIED_PM25_SENSOR_ID, "parameter": {"name": "no2", "units": "ppm"}}]}
    with patch("requests.get", side_effect=[mock_loc, mock_wrong_param]):
        try:
            fetch_koramangala_pm25(force_refresh=True)
            test("Wrong pollutant metadata rejected", False, "Expected ValueError on wrong pollutant")
        except ValueError as e:
            test("Wrong pollutant metadata rejected", "mismatch" in str(e).lower())

    print("\n--- Test Suite 4: Unified Dispatcher & Plan Invalidation Data Signature ---")
    demo_data = get_air_quality(city="Bengaluru", source_mode="demo")
    test("Demo mode returns is_sample=True", demo_data["is_sample"] is True)

    sig_demo = f"{demo_data['source_mode']}:{demo_data['station_name']}:{demo_data['measurement_time_ist']}:{demo_data['pm25_ugm3']}"
    invalidate_openaq_cache()
    live_data = get_air_quality(source_mode="openaq")
    sig_live = f"{live_data['source_mode']}:{live_data['station_name']}:{live_data['measurement_time_ist']}:{live_data['pm25_ugm3']}"
    test("Data signature changes between Demo and OpenAQ modes", sig_demo != sig_live)

    print(f"\nSummary: {passed}/{total} tests passed.")
    return passed == total


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
