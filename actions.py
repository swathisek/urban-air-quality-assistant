# actions.py
# ---------------------------------------------------------
# Permitted action catalogue for the Urban Air Quality
# Assistant.
#
# WHY THIS FILE EXISTS
# --------------------
# Small language models (and large ones) can hallucinate
# unsupported interventions — including ones that are
# ineffective or potentially misleading (e.g. suggesting
# household plants as proven air-cleaners).
#
# This catalogue gives the LLM a fixed menu. It may only
# select action IDs from this list and personalise the
# "why" text. Any ID not in this catalogue is rejected
# by advice.py before the card is shown to the user.
#
# SAFETY & EVIDENCE CONSTRAINTS:
# - No claims of fixed peak hours (e.g. 6–9 AM/PM); readings
#   do not establish hourly patterns.
# - Cooking ventilation: prefer exhaust hood/fan that vents
#   outdoors. Windows should only be opened when outdoor air
#   quality and weather permit and it is safe.
# - Household plants/green buffers are not supported air
#   cleaners and are blocked.
# - Suggestions remain conditional; an instantaneous PM2.5
#   concentration does not establish high pollution without
#   an established interpretation rule.
# ---------------------------------------------------------

from typing import Literal

Focus = Literal["exposure_reduction", "emission_reduction"]

PERMITTED_ACTIONS: list[dict] = [
    {
        "id": "stay_indoors_peak",
        "label": "Adjust outdoor activity based on air quality",
        "focus": "exposure_reduction",
        "default_action": (
            "Use verified local air-quality updates to choose cleaner times "
            "for outdoor activity; reduce prolonged or strenuous outdoor "
            "activity when local guidance advises it."
        ),
        "guidance_note": (
            "Keep recommendations conditional on verified local updates. "
            "Do NOT claim fixed peak hours (such as 6–9 AM or 6–9 PM) or assume "
            "high pollution without an implemented classification rule."
        ),
    },
    {
        "id": "use_air_purifier",
        "label": "Run your air purifier strategically",
        "focus": "exposure_reduction",
        "default_action": (
            "Run the air purifier in the room where your household spends the most "
            "time, especially overnight and when outdoor PM2.5 is elevated."
        ),
        "guidance_note": (
            "Only suggest if has_purifier is true. Frame as conditional when "
            "indoor particulate levels rise or outdoor PM2.5 is elevated."
        ),
    },
    {
        "id": "wear_mask_outdoors",
        "label": "Consider wearing a mask if guidance advises",
        "focus": "exposure_reduction",
        "default_action": (
            "When going outside during elevated pollution periods, consider "
            "wearing a well-fitted N95 or equivalent mask to reduce inhalation "
            "of fine particles, especially if you have respiratory sensitivities."
        ),
        "guidance_note": (
            "Keep mask advice conditional on elevated pollution periods or "
            "respiratory sensitivity. Do not state masks are required at clean levels."
        ),
    },
    {
        "id": "ventilate_strategically",
        "label": "Time ventilation using verified air quality updates",
        "focus": "exposure_reduction",
        "default_action": (
            "Check verified local air quality before ventilating; open windows "
            "only when outdoor air quality and weather permit and it is safe, "
            "keeping them closed when pollution is elevated."
        ),
        "guidance_note": (
            "Do NOT assume fixed hourly pollution patterns. Advise opening "
            "windows only when local air quality and weather permit and it is safe."
        ),
    },
    {
        "id": "avoid_incense_candles",
        "label": "Avoid burning incense or candles indoors",
        "focus": "exposure_reduction",
        "default_action": (
            "Avoid burning incense sticks, agarbatti, or scented candles indoors — "
            "they release fine particles that add to indoor air pollution."
        ),
        "guidance_note": (
            "Frame as general indoor air hygiene. Mention electric or non-combustion alternatives."
        ),
    },
    {
        "id": "reduce_vehicle_idling",
        "label": "Reduce vehicle idling",
        "focus": "emission_reduction",
        "default_action": (
            "Switch off your vehicle engine whenever you are stopped for more "
            "than 30 seconds — idling engines emit PM2.5 unnecessarily."
        ),
        "guidance_note": (
            "Relevant for households that own or use motor vehicles regularly. "
            "Do not invent exact emission figures."
        ),
    },
    {
        "id": "carpool_or_public_transport",
        "label": "Share a ride or use public transport",
        "focus": "emission_reduction",
        "default_action": (
            "Carpool with a neighbour or take public transport for today's "
            "commute to reduce the number of vehicles on the road."
        ),
        "guidance_note": (
            "Frame as a collective community benefit — fewer vehicles means lower "
            "roadside PM2.5 for everyone. No numerical claims."
        ),
    },
    {
        "id": "avoid_burning_waste",
        "label": "Do not burn waste or dry leaves",
        "focus": "emission_reduction",
        "default_action": (
            "Avoid burning dry leaves, garden waste, or household garbage — "
            "open burning is a significant local source of PM2.5."
        ),
        "guidance_note": (
            "General emission prevention measure. Suggest composting or municipal "
            "collection as alternatives."
        ),
    },
    {
        "id": "cook_with_exhaust_on",
        "label": "Use kitchen exhaust hood or fan that vents outdoors",
        "focus": "exposure_reduction",
        "default_action": (
            "Use an exhaust hood or fan that vents outdoors while cooking. "
            "Open windows only if outdoor air quality and weather permit "
            "and it is safe to do so."
        ),
        "guidance_note": (
            "Prefer an exhaust hood or fan that vents outdoors. If mentioning "
            "opening windows, strictly specify to open them only when outdoor "
            "air quality and weather permit and it is safe."
        ),
    },
    {
        "id": "reduce_high_heat_cooking",
        "label": "Consider steaming or boiling instead of deep frying",
        "focus": "emission_reduction",
        "default_action": (
            "Consider steaming, boiling, or slow cooking where feasible instead "
            "of deep frying or using open flame — these methods release less "
            "combustion smoke indoors."
        ),
        "guidance_note": (
            "Frame as a practical kitchen tip. Do not prescribe medical requirements."
        ),
    },
]

# Quick lookup dictionary: id -> action record
ACTIONS_BY_ID: dict[str, dict] = {a["id"]: a for a in PERMITTED_ACTIONS}

# IDs the LLM may NOT suggest
BLOCKED_ACTION_IDS: frozenset[str] = frozenset({
    "indoor_plants",
    "plants",
    "green_plants",
    "air_purifying_plants",
})


def get_action(action_id: str) -> dict | None:
    """Return the permitted action record for the given ID, or None."""
    return ACTIONS_BY_ID.get(action_id)


def catalogue_for_prompt() -> str:
    """Return a compact plain-text representation of the catalogue for LLM prompts."""
    lines = []
    for a in PERMITTED_ACTIONS:
        lines.append(
            f'  id="{a["id"]}"  focus={a["focus"]}\n'
            f'  label: {a["label"]}\n'
            f'  personalisation guidance: {a["guidance_note"]}'
        )
    return "\n\n".join(lines)
