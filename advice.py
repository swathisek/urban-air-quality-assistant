# advice.py
# ---------------------------------------------------------
# LLM dispatch and validation layer for Urban Air Quality Assistant.
#
# Responsibilities:
# 1. Build prompt from city + air_data + household with strict
#    safety and evidence constraints.
# 2. Support both OpenAQ live station data and Demo synthetic data.
# 3. Do not assume 'high pollution' or invent AQI.
# 4. Route the call to the specified LLM provider (Ollama by
#    default; Gemini explicitly optional).
#    NEVER silently fallback or switch providers on failure.
# 5. Validate and enforce:
#    - Exactly 3 DISTINCT permitted action IDs.
#    - All required fields non-empty.
#    - No unsupported peak-hour claims (e.g. 6–9 AM/PM).
#    - Cooking ventilation safety constraints applied to both
#      action catalogue and personalized text.
# 6. Return both the 3 validated cards and the exact provider/model
#    metadata used for that successful request.
# ---------------------------------------------------------

import json
import os
import re
import time
from typing import Any

from config import (
    LLM_PROVIDER,
    GEMINI_MODEL,
    OLLAMA_MODEL,
)
from actions import PERMITTED_ACTIONS, ACTIONS_BY_ID, catalogue_for_prompt

_MAX_ATTEMPTS   = 3
_BACKOFF_BASE_S = 2.0
_BACKOFF_CAP_S  = 10.0
_TRANSIENT_CODES = frozenset({429, 500, 502, 503, 504})


# ══════════════════════════════════════════════════════════
# Prompt Builder
# ══════════════════════════════════════════════════════════

def _household_description(household: dict) -> str:
    parts = []
    if household.get("children", 0) > 0:
        parts.append(f"{household['children']} child/children (under 12)")
    if household.get("older_adults", 0) > 0:
        parts.append(f"{household['older_adults']} older adult(s) (60+)")
    if household.get("respiratory_sensitive"):
        parts.append("at least one person with respiratory sensitivity")
    if household.get("has_purifier"):
        parts.append("an air purifier at home")
    return ", ".join(parts) if parts else "no specific vulnerability factors noted"


def _build_prompt(city: str, air_data: dict, household: dict) -> str:
    pm25         = air_data.get("pm25_ugm3", 0.0)
    unit         = air_data.get("unit", "µg/m³")
    timestamp    = air_data.get("measurement_time_ist") or air_data.get("sample_timestamp") or "Unknown"
    source_mode  = air_data.get("source_mode", "demo")
    station_name = air_data.get("station_name", city)
    is_stale     = air_data.get("is_stale", False)
    reading_age  = air_data.get("reading_age_str", "Unknown")
    has_purifier = household.get("has_purifier", False)

    if source_mode == "openaq":
        context_header = "POLLUTION CONTEXT (LIVE OPENAQ v3 OBSERVATION):"
        context_lines = [
            f"  Station    : {station_name}",
            f"  Location   : Single monitoring station in {city} (NOT a citywide average)",
            f"  PM2.5      : {pm25} {unit} (instantaneous concentration — NOT an AQI score)",
            f"  Observed at: {timestamp} (Reading age: {reading_age})",
            f"  Freshness  : {'STALE: Older than 24h threshold. Do NOT claim this reflects current ambient conditions.' if is_stale else 'Current active reading'}",
        ]
    else:
        context_header = "POLLUTION CONTEXT (DEMO DATA — NOT A LIVE READING):"
        context_lines = [
            f"  City       : {city}",
            f"  PM2.5      : {pm25} {unit} (illustrative synthetic value — NOT an AQI score)",
            f"  As of      : {timestamp}",
        ]

    context_block = "\n".join(context_lines)

    available_ids = [
        a["id"] for a in PERMITTED_ACTIONS
        if not (a["id"] == "use_air_purifier" and not has_purifier)
    ]
    available_id_list = ", ".join(f'"{i}"' for i in available_ids)

    prompt = f"""You are an urban air quality assistant for Indian cities.
Select and personalise exactly 3 distinct practical actions for the household below.

=== {context_header} ===
{context_block}

=== HOUSEHOLD PROFILE ===
{_household_description(household)}

=== PERMITTED ACTION CATALOGUE ===
You MUST choose exactly 3 distinct action IDs from this list:
{available_id_list}

Catalogue details:
{catalogue_for_prompt()}

=== YOUR TASK ===
Return a JSON array containing EXACTLY 3 objects with distinct action IDs.
Each object must have these exact keys:
  "action_id"  — one of the permitted IDs listed above (string)
  "why"        — 1–2 sentences explaining why this action helps this specific household (string)

=== STRICT CONSTRAINTS ===
1. Return exactly 3 distinct action IDs. Do not repeat action IDs.
2. Output ONLY the JSON array. No explanations before or after.
3. Proportional Advice: Do NOT assume or state that pollution is 'high', 'severe', or 'dangerous' based on an instantaneous reading ({pm25} {unit}). Frame advice proportionally and conditionally without claiming local conditions are hazardous.
4. Single-station observation: Do NOT claim that a single station reading represents the entire city's air quality.
5. No AQI claims: Do NOT convert the concentration to an AQI score or invent AQI categories (e.g. 'Very Poor').
6. Freshness: {'This reading is STALE (>24h old). Advise checking verified real-time local updates rather than assuming this reading reflects current conditions.' if is_stale else 'Focus on current practical actions based on verified updates.'}
7. Peak-hour constraint: Do NOT make claims about fixed peak hours or specific morning/evening times (e.g. do NOT mention 6–9 AM or 6–9 PM). The reading does not establish hourly patterns. Advise using verified local air quality updates instead.
8. Cooking ventilation: Prefer an exhaust hood or fan that vents outdoors. If suggesting opening windows, explicitly state that windows should only be opened when outdoor air quality and weather permit and it is safe.
9. Blocked items: Do NOT suggest indoor plants or green buffers as air-cleaning measures.
10. Medical boundary: Do NOT invent percentages, micrograms, health statistics, or medical guarantees. Treat all suggestions as general information, not medical advice.
"""
    return prompt


# ══════════════════════════════════════════════════════════
# Safety Sanitization & Validation
# ══════════════════════════════════════════════════════════

def _sanitize_why_text(action_id: str, why: str, pm25_val: float | None = None) -> str:
    """Enforce safety and evidence constraints on model-personalized wording."""
    cleaned = why.strip()

    # 1. Remove unsupported specific peak-hour claims (e.g. 6-9 AM, 6-9 PM)
    cleaned = re.sub(
        r'\b(?:6\s*[-–]\s*9\s*(?:AM|PM|am|pm)?|peak\s+hours?\s*(?:of\s*)?6\s*[-–]\s*9)\b',
        'cleaner times based on verified local updates',
        cleaned,
        flags=re.IGNORECASE
    )

    # 2. Cooking ventilation constraints
    if action_id == "cook_with_exhaust_on":
        lower = cleaned.lower()
        if "window" in lower:
            has_condition = ("permit" in lower or "safe" in lower or "weather" in lower)
            if not has_condition:
                cleaned += " (Ensure outdoor air quality and weather permit and it is safe before opening windows)."

    # 3. Remove hard-coded 'high PM2.5 / high pollution' assertions
    if pm25_val is not None and pm25_val < 35.0:
        cleaned = re.sub(
            r'\b(?:given\s+the\s+high\s+PM2\.5\s+levels?|given\s+high\s+PM2\.5\s+levels?|due\s+to\s+high\s+pollution(?:\s+levels?)?|given\s+the\s+poor\s+air\s+quality)\b',
            'To protect indoor air quality and minimize particulate exposure',
            cleaned,
            flags=re.IGNORECASE
        )
        cleaned = re.sub(
            r'\b(?:high\s+PM2\.5\s+(?:levels?|concentrations?)|high\s+pollution(?:\s+levels?)?)\b',
            'current PM2.5 concentration',
            cleaned,
            flags=re.IGNORECASE
        )

    return cleaned


def _extract_json_array(raw_text: str) -> str:
    text = raw_text.strip()
    if "```" in text:
        lines = text.splitlines()
        text = "\n".join(
            line for line in lines if not line.strip().startswith("```")
        ).strip()

    start = text.find("[")
    end   = text.rfind("]")
    if start == -1 or end == -1 or end <= start:
        raise ValueError(
            f"No JSON array found in model response.\nRaw output:\n{raw_text[:400]}"
        )
    return text[start : end + 1]


def _validate_and_build(raw_items: list, provider_label: str, pm25_val: float | None = None) -> list[dict]:
    """
    Validate that raw_items contains exactly 3 distinct, permitted action IDs
    with required non-empty fields.
    """
    if not isinstance(raw_items, list):
        raise ValueError(f"{provider_label} did not return a JSON array.")

    valid: list[dict] = []
    seen_ids: set[str] = set()

    for item in raw_items:
        if not isinstance(item, dict):
            continue

        action_id = str(item.get("action_id", "")).strip()
        raw_why   = str(item.get("why", "")).strip()

        if not action_id or action_id not in ACTIONS_BY_ID:
            continue

        # Enforce distinct action IDs
        if action_id in seen_ids:
            continue

        action_record = ACTIONS_BY_ID[action_id]
        why_text = raw_why if raw_why else action_record["default_action"]
        sanitized_why = _sanitize_why_text(action_id, why_text, pm25_val=pm25_val)

        seen_ids.add(action_id)
        valid.append({
            "action_id": action_id,
            "label":     action_record["label"],
            "action":    action_record["default_action"],
            "why":       sanitized_why,
            "focus":     action_record["focus"],
        })

        if len(valid) == 3:
            break

    # Strictly require exactly 3 cards
    if len(valid) != 3:
        raise ValueError(
            f"{provider_label} returned {len(valid)} valid distinct suggestions, "
            f"but exactly 3 distinct permitted actions are required."
        )

    return valid


def _parse_and_validate(raw_text: str, provider_label: str, pm25_val: float | None = None) -> list[dict]:
    json_str = _extract_json_array(raw_text)
    try:
        items = json.loads(json_str)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Could not parse JSON from {provider_label}: {exc}") from exc

    return _validate_and_build(items, provider_label, pm25_val=pm25_val)


# ══════════════════════════════════════════════════════════
# Provider Executions
# ══════════════════════════════════════════════════════════

def _execute_ollama_call(prompt: str) -> str:
    from llm_ollama import call_ollama
    return call_ollama(prompt)


def _execute_gemini_call(prompt: str) -> str:
    from google import genai
    from google.genai.errors import ClientError, ServerError

    if not os.environ.get("GEMINI_API_KEY"):
        raise EnvironmentError(
            "GEMINI_API_KEY environment variable is not set. "
            "Please set it in your Windows environment variables and restart the app."
        )

    client = genai.Client()
    try:
        interaction = client.interactions.create(
            model=GEMINI_MODEL,
            input=prompt,
        )
        return interaction.output_text
    except ClientError as exc:
        if exc.code in (401, 403):
            raise PermissionError(
                f"The Gemini API rejected the request (HTTP {exc.code}). "
                "Your GEMINI_API_KEY may be invalid or lack required permissions."
            ) from exc
        raise
    except ServerError:
        raise


# ══════════════════════════════════════════════════════════
# Public Interface
# ══════════════════════════════════════════════════════════

def get_provider_info(provider: str | None = None) -> dict[str, str]:
    target_provider = provider or LLM_PROVIDER
    if target_provider == "ollama":
        return {
            "provider": "ollama",
            "model": OLLAMA_MODEL,
            "provider_label": f"Ollama ({OLLAMA_MODEL})",
        }
    elif target_provider == "gemini":
        return {
            "provider": "gemini",
            "model": GEMINI_MODEL,
            "provider_label": f"Gemini ({GEMINI_MODEL})",
        }
    else:
        return {
            "provider": target_provider,
            "model": "unknown",
            "provider_label": target_provider,
        }


def get_suggestions(
    city: str,
    air_data: dict,
    household: dict,
    *,
    provider: str | None = None,
    on_retry=None,
) -> dict[str, Any]:
    """
    Generate and return exactly 3 validated suggestions along with
    the provider and model metadata that actually produced them.
    """
    target_provider = provider or LLM_PROVIDER
    if target_provider not in ("ollama", "gemini"):
        raise RuntimeError(f"Unsupported LLM provider '{target_provider}'.")

    provider_info = get_provider_info(target_provider)
    provider_label = provider_info["provider_label"]

    prompt = _build_prompt(city, air_data, household)
    pm25_val = air_data.get("pm25_ugm3")

    last_error: Exception | None = None

    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            if target_provider == "ollama":
                raw_text = _execute_ollama_call(prompt)
            else:
                raw_text = _execute_gemini_call(prompt)

            suggestions = _parse_and_validate(raw_text, provider_label, pm25_val=pm25_val)
            return {
                "suggestions": suggestions,
                "provider": provider_info["provider"],
                "model": provider_info["model"],
                "provider_label": provider_info["provider_label"],
            }

        except PermissionError:
            # Auth errors must NEVER be retried
            raise

        except Exception as exc:
            last_error = exc

            if attempt < _MAX_ATTEMPTS:
                wait_s = min(_BACKOFF_BASE_S * (2 ** (attempt - 1)), _BACKOFF_CAP_S)
                if callable(on_retry):
                    on_retry(attempt, _MAX_ATTEMPTS, wait_s)
                time.sleep(wait_s)

    # If all attempts exhausted, raise clear error without switching providers
    err_str = str(last_error)
    if "503" in err_str or "service_unavailable" in err_str:
        raise RuntimeError(f"{provider_label} is temporarily busy. Please try again shortly.")
    raise RuntimeError(
        f"Failed to generate a valid 3-card plan from {provider_label} after {_MAX_ATTEMPTS} attempts: {last_error}"
    ) from last_error
