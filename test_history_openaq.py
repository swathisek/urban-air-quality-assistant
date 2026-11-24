# test_history_openaq.py
# ---------------------------------------------------------------------------
# Unit and Integration Tests for Historical Data Access & Analysis
# ---------------------------------------------------------------------------

import os
import unittest
from datetime import datetime, timezone
import pandas as pd
import altair as alt

from history_openaq import (
    process_raw_measurements,
    fetch_sensor_history,
    build_history_chart,
    invalidate_history_cache,
    KORAMANGALA_LOCATION_ID,
    VERIFIED_PM25_SENSOR_ID,
)


class TestProcessRawMeasurements(unittest.TestCase):
    def test_empty_records(self):
        result = process_raw_measurements([], 24)
        self.assertEqual(result["status"], "insufficient_data")
        self.assertTrue(result["df"].empty)
        self.assertIsNone(result["summary"])

    def test_single_record_insufficient(self):
        records = [
            {
                "parameter": {"name": "pm25", "units": "µg/m³"},
                "value": 15.2,
                "period": {"datetimeTo": {"utc": "2026-11-24T10:00:00Z"}},
            }
        ]
        result = process_raw_measurements(records, 24)
        self.assertEqual(result["status"], "insufficient_data")
        self.assertIn("minimum 2 required", result["message"])

    def test_deduplication_and_sorting(self):
        records = [
            # Later timestamp first
            {
                "parameter": {"name": "pm25", "units": "µg/m³"},
                "value": 20.0,
                "period": {"datetimeTo": {"utc": "2026-11-24T12:00:00Z"}},
            },
            # Duplicate timestamp with different value (first seen kept)
            {
                "parameter": {"name": "pm25", "units": "µg/m³"},
                "value": 99.0,
                "period": {"datetimeTo": {"utc": "2026-11-24T12:00:00Z"}},
            },
            # Earlier timestamp second
            {
                "parameter": {"name": "pm25", "units": "µg/m³"},
                "value": 10.0,
                "period": {"datetimeTo": {"utc": "2026-11-24T08:00:00Z"}},
            },
        ]
        result = process_raw_measurements(records, 24)
        self.assertEqual(result["status"], "ok")
        df = result["df"]
        self.assertEqual(len(df), 2)
        # Verify chronological order
        self.assertEqual(df.iloc[0]["pm25"], 10.0)
        self.assertEqual(df.iloc[1]["pm25"], 20.0)

    def test_preserves_zero_value(self):
        records = [
            {
                "parameter": {"name": "pm25", "units": "µg/m³"},
                "value": 0.0,
                "period": {"datetimeTo": {"utc": "2026-11-24T08:00:00Z"}},
            },
            {
                "parameter": {"name": "pm25", "units": "µg/m³"},
                "value": 5.5,
                "period": {"datetimeTo": {"utc": "2026-11-24T09:00:00Z"}},
            },
        ]
        result = process_raw_measurements(records, 24)
        self.assertEqual(result["status"], "ok")
        df = result["df"]
        self.assertEqual(len(df), 2)
        self.assertEqual(df.iloc[0]["pm25"], 0.0)
        summary = result["summary"]
        self.assertEqual(summary["min_val"], 0.0)
        self.assertEqual(summary["max_val"], 5.5)

    def test_ignores_non_pm25_or_invalid_units(self):
        records = [
            {
                "parameter": {"name": "co", "units": "ppm"},
                "value": 1.2,
                "period": {"datetimeTo": {"utc": "2026-11-24T08:00:00Z"}},
            },
            {
                "parameter": {"name": "pm25", "units": "µg/m³"},
                "value": 12.0,
                "period": {"datetimeTo": {"utc": "2026-11-24T09:00:00Z"}},
            },
            {
                "parameter": {"name": "pm25", "units": "µg/m³"},
                "value": 14.0,
                "period": {"datetimeTo": {"utc": "2026-11-24T10:00:00Z"}},
            },
        ]
        result = process_raw_measurements(records, 24)
        self.assertEqual(result["status"], "ok")
        df = result["df"]
        self.assertEqual(len(df), 2)
        self.assertEqual(df.iloc[0]["pm25"], 12.0)
        self.assertEqual(df.iloc[1]["pm25"], 14.0)

    def test_summary_statistics_calculation(self):
        records = [
            {
                "parameter": {"name": "pm25", "units": "µg/m³"},
                "value": 8.0,
                "period": {"datetimeTo": {"utc": "2026-11-24T06:00:00Z"}},
            },
            {
                "parameter": {"name": "pm25", "units": "µg/m³"},
                "value": 18.5,
                "period": {"datetimeTo": {"utc": "2026-11-24T07:00:00Z"}},
            },
            {
                "parameter": {"name": "pm25", "units": "µg/m³"},
                "value": 4.2,
                "period": {"datetimeTo": {"utc": "2026-11-24T08:00:00Z"}},
            },
        ]
        result = process_raw_measurements(records, 24)
        summary = result["summary"]
        self.assertEqual(summary["valid_count"], 3)
        self.assertEqual(summary["min_val"], 4.2)
        self.assertEqual(summary["max_val"], 18.5)
        self.assertIn("IST", summary["start_time_ist"])
        self.assertIn("IST", summary["end_time_ist"])
        self.assertEqual(summary["location_id"], KORAMANGALA_LOCATION_ID)
        self.assertEqual(summary["sensor_id"], VERIFIED_PM25_SENSOR_ID)

    def test_build_history_chart(self):
        records = [
            {
                "parameter": {"name": "pm25", "units": "µg/m³"},
                "value": 10.0,
                "period": {"datetimeTo": {"utc": "2026-11-24T08:00:00Z"}},
            },
            {
                "parameter": {"name": "pm25", "units": "µg/m³"},
                "value": 15.0,
                "period": {"datetimeTo": {"utc": "2026-11-24T09:00:00Z"}},
            },
        ]
        result = process_raw_measurements(records, 24)
        chart = build_history_chart(result["df"])
        self.assertIsInstance(chart, alt.Chart)
        spec = chart.to_dict()
        self.assertEqual(spec["mark"]["type"], "line")


class TestLiveOpenAQHistory(unittest.TestCase):
    @unittest.skipUnless(os.environ.get("OPENAQ_API_KEY"), "OPENAQ_API_KEY not set")
    def test_live_history_fetch_24h(self):
        invalidate_history_cache()
        res = fetch_sensor_history(range_hours=24, force_refresh=True)
        self.assertIn(res["status"], ("ok", "insufficient_data"))
        if res["status"] == "ok":
            df = res["df"]
            self.assertFalse(df.empty)
            self.assertIn("datetime_ist", df.columns)
            self.assertIn("pm25", df.columns)
            self.assertGreaterEqual(res["summary"]["valid_count"], 2)
            self.assertGreaterEqual(res["summary"]["max_val"], res["summary"]["min_val"])
            # Test chart generation with real data
            chart = build_history_chart(df)
            self.assertIsInstance(chart, alt.Chart)


if __name__ == "__main__":
    unittest.main()
