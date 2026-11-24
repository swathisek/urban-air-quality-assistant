# test_output_validation.py
# ---------------------------------------------------------
# Test suite for output validation, safety constraints,
# and provider visibility in Urban Air Quality Assistant.
# ---------------------------------------------------------

import sys
from actions import ACTIONS_BY_ID, PERMITTED_ACTIONS
from advice import (
    _validate_and_build,
    _sanitize_why_text,
    get_provider_info,
)


def run_tests():
    passed = 0
    total = 0

    def test(name, condition, details=""):
        nonlocal passed, total
        total += 1
        if condition:
            print(f"  [PASS] {name}")
            passed += 1
        else:
            print(f"  [FAIL] {name}: {details}")

    print("\n--- Test Suite 1: Exactly Three Distinct Cards ---")
    
    # 1.1: Exactly 3 valid distinct actions should succeed
    items_3 = [
        {"action_id": "stay_indoors_peak", "why": "Keeps indoor air cleaner."},
        {"action_id": "cook_with_exhaust_on", "why": "Vents cooking smoke outside."},
        {"action_id": "reduce_vehicle_idling", "why": "Reduces neighborhood emissions."},
    ]
    try:
        res = _validate_and_build(items_3, "TestProvider")
        test("3 distinct valid cards succeed", len(res) == 3 and len(set(c["action_id"] for c in res)) == 3)
    except Exception as e:
        test("3 distinct valid cards succeed", False, str(e))

    # 1.2: Only 2 cards must raise ValueError
    items_2 = [
        {"action_id": "stay_indoors_peak", "why": "Keeps indoor air cleaner."},
        {"action_id": "cook_with_exhaust_on", "why": "Vents cooking smoke outside."},
    ]
    try:
        _validate_and_build(items_2, "TestProvider")
        test("2 cards rejected (not allowed)", False, "Expected ValueError was not raised")
    except ValueError as e:
        test("2 cards rejected (not allowed)", "exactly 3 distinct permitted actions are required" in str(e))

    # 1.3: Duplicate action IDs must be rejected and raise ValueError if < 3 distinct
    items_dup = [
        {"action_id": "stay_indoors_peak", "why": "Reason 1"},
        {"action_id": "stay_indoors_peak", "why": "Reason 2"},
        {"action_id": "cook_with_exhaust_on", "why": "Reason 3"},
    ]
    try:
        _validate_and_build(items_dup, "TestProvider")
        test("Duplicate action IDs rejected", False, "Expected ValueError on duplicate")
    except ValueError as e:
        test("Duplicate action IDs rejected", "exactly 3 distinct permitted actions are required" in str(e))

    # 1.4: Unrecognized action IDs must be rejected
    items_unrec = [
        {"action_id": "stay_indoors_peak", "why": "Reason 1"},
        {"action_id": "plant_more_trees", "why": "Reason 2"},  # unpermitted
        {"action_id": "cook_with_exhaust_on", "why": "Reason 3"},
    ]
    try:
        _validate_and_build(items_unrec, "TestProvider")
        test("Unrecognized action IDs rejected", False, "Expected rejection of unpermitted ID")
    except ValueError as e:
        test("Unrecognized action IDs rejected", "exactly 3 distinct permitted actions are required" in str(e))

    print("\n--- Test Suite 2: Peak Hour Claims Removed ---")
    
    # 2.1: stay_indoors_peak must not claim fixed 6-9 AM/PM
    action_peak = ACTIONS_BY_ID["stay_indoors_peak"]
    has_peak_numbers = "6–9" in action_peak["default_action"] or "6-9" in action_peak["default_action"]
    test("Action text has no 6-9 peak claims", not has_peak_numbers, f"Found in: {action_peak['default_action']}")
    test("Action advises verified updates", "verified local air-quality updates" in action_peak["default_action"])

    # 2.2: Sanitizer removes model-hallucinated 6-9 peak claims
    model_why = "Avoid going outdoors during 6-9 AM peak hours."
    sanitized = _sanitize_why_text("stay_indoors_peak", model_why)
    test("Sanitizer replaces 6-9 peak hours", "6-9" not in sanitized and "cleaner times based on verified local updates" in sanitized)

    print("\n--- Test Suite 3: Cooking Ventilation Safety Constraints ---")
    
    # 3.1: Catalogue defaults prioritize exhaust hood/fan venting outdoors
    cook_action = ACTIONS_BY_ID["cook_with_exhaust_on"]
    test("Cooking action prefers exhaust hood/fan venting outdoors", "vents outdoors" in cook_action["default_action"])
    test("Cooking action conditions window opening on air quality and safety", "permit and it is safe" in cook_action["default_action"])

    # 3.2: Sanitizer adds window opening safety constraint if model mentions windows without safety
    unsafe_model_why = "You should open all the kitchen windows while frying food."
    sanitized_cook = _sanitize_why_text("cook_with_exhaust_on", unsafe_model_why)
    test("Sanitizer enforces window safety condition", "Ensure outdoor air quality and weather permit and it is safe" in sanitized_cook)

    print("\n--- Test Suite 4: Provider Visibility ---")
    
    ollama_info = get_provider_info("ollama")
    test("Ollama info accurate", ollama_info["provider"] == "ollama" and "phi3" in ollama_info["model"] and "Ollama (phi3:latest)" == ollama_info["provider_label"])

    gemini_info = get_provider_info("gemini")
    test("Gemini info accurate", gemini_info["provider"] == "gemini" and "gemini-4-hydrogen" == gemini_info["model"] and "Gemini (gemini-4-hydrogen)" == gemini_info["provider_label"])

    print(f"\nSummary: {passed}/{total} tests passed.")
    return passed == total


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
