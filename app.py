# app.py
# ---------------------------------------------------------------------------
# Urban Air Quality Assistant — Streamlit Front-End
#
# Milestone 2:
# - Verified OpenAQ v3 Live Station Data (Koramangala, Bengaluru)
# - Explicit Demo (synthetic) mode
# - Preserved desktop design matching approved reference
# - Responsive mobile presentation (single vertical column, collapsed sidebar)
# - No horizontal scrolling, wrapped metadata, tappable controls
# - Single-station observation transparency (no AQI calculation)
# - Plan invalidation on source or measurement changes
# - Default model: Ollama (phi3:latest), Optional: Gemini (gemini-4-hydrogen)
# ---------------------------------------------------------------------------

import streamlit as st

from config import CITIES, LLM_PROVIDER, OLLAMA_MODEL, GEMINI_MODEL
from data import get_air_quality
from data_openaq import invalidate_openaq_cache
from advice import get_suggestions, get_provider_info

# ── Page Configuration ──────────────────────────────────────────────────────
# 'centered' layout with 'auto' initial sidebar state preserves the approved
# desktop reference while collapsing on mobile (<768px).
st.set_page_config(
    page_title="Urban Air Quality Assistant",
    page_icon="🌿",
    layout="centered",
    initial_sidebar_state="auto",
)

# ── Dark Forest Green & Responsive Scoped CSS ───────────────────────────────
CUSTOM_CSS = """
<style>
/* Base theme styling matching approved desktop reference */
.stApp {
    background-color: #08140e;
    color: #e6f4ed;
}

[data-testid="stSidebar"] {
    background-color: #0b1a13;
    border-right: 1px solid #1a382b;
}

/* Main card */
.main-card {
    background: linear-gradient(145deg, #10241b, #153024);
    border: 1px solid #234d39;
    border-radius: 14px;
    padding: 20px 22px;
    margin-bottom: 20px;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.35);
    box-sizing: border-box;
    width: 100%;
}

/* Suggestion card */
.suggestion-card {
    background: #11251c;
    border: 1px solid #204533;
    border-radius: 12px;
    padding: 16px 18px;
    margin-bottom: 14px;
    box-sizing: border-box;
    width: 100%;
}

/* Badges matching reference screenshot */
.badge-live {
    display: inline-block;
    background: #123d2a;
    color: #48df92;
    border: 1px solid #24754f;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 0.78rem;
    font-weight: 600;
    white-space: nowrap;
}

.badge-stale {
    display: inline-block;
    background: #3b280f;
    color: #f7a93b;
    border: 1px solid #7a4f1a;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 0.78rem;
    font-weight: 600;
    white-space: nowrap;
}

.badge-demo {
    display: inline-block;
    background: #252838;
    color: #9cb3fc;
    border: 1px solid #434c75;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 0.78rem;
    font-weight: 600;
    white-space: nowrap;
}

.focus-badge {
    display: inline-block;
    background: #153325;
    color: #7de8b3;
    border: 1px solid #286347;
    padding: 3px 10px;
    border-radius: 14px;
    font-size: 0.8rem;
    font-weight: 600;
    white-space: nowrap;
}

/* Primary buttons */
.stButton>button {
    border-radius: 10px;
    font-weight: 600;
    min-height: 42px;
}

/* Desktop layout (>= 769px): preserve approved sidebar width */
@media (min-width: 769px) {
    [data-testid="stSidebar"] {
        min-width: 280px;
        max-width: 320px;
    }
}

/* Mobile responsive presentation (<= 768px, e.g. ~390px phone) */
@media (max-width: 768px) {
    /* Prevent horizontal scrolling */
    html, body, [data-testid="stAppViewContainer"] {
        overflow-x: hidden !important;
    }

    /* Single full-width vertical scrolling column */
    .main .block-container {
        padding-left: 14px !important;
        padding-right: 14px !important;
        padding-top: 14px !important;
        padding-bottom: 28px !important;
        max-width: 100% !important;
        width: 100% !important;
    }

    /* Keep sidebar toggle button visible, prominent and tappable */
    [data-testid="stSidebarCollapsedControl"] {
        display: flex !important;
        visibility: visible !important;
        min-height: 44px !important;
        min-width: 44px !important;
        align-items: center !important;
        justify-content: center !important;
        background-color: rgba(16, 36, 27, 0.92) !important;
        border: 1px solid #234d39 !important;
        border-radius: 8px !important;
        z-index: 1000 !important;
    }

    /* Cards fit available screen width with compact touch padding */
    .main-card {
        padding: 16px 14px !important;
        margin-bottom: 16px !important;
    }

    .suggestion-card {
        padding: 14px 12px !important;
        margin-bottom: 12px !important;
    }

    /* Allow card header to wrap cleanly on narrow screens */
    .card-top-row {
        flex-direction: column !important;
        align-items: flex-start !important;
        gap: 8px !important;
    }

    /* Allow suggestion card title & badge to wrap cleanly */
    .suggestion-header-row {
        flex-direction: column !important;
        align-items: flex-start !important;
        gap: 6px !important;
    }

    /* PM2.5 value font size scales comfortably on 390px */
    .pm25-val-text {
        font-size: 2.8rem !important;
    }

    /* Metadata rows wrap cleanly without clipping */
    .meta-desc {
        font-size: 0.82rem !important;
        line-height: 1.5 !important;
        word-break: break-word !important;
    }

    /* Comfortable touch target on full-width button */
    .stButton>button {
        min-height: 46px !important;
        width: 100% !important;
    }
}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ── Sidebar Configuration ───────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ Data & Controls")

    # 1. Data Source Selection
    source_display_options = [
        "OpenAQ — Koramangala, Bengaluru (Live)",
        "Demo (Synthetic Data)",
    ]
    selected_source_label = st.selectbox(
        "Data Source Mode",
        source_display_options,
        index=0,
        help="Select OpenAQ for verified live station data or Demo for synthetic offline values.",
    )
    is_openaq_mode = "OpenAQ" in selected_source_label
    source_mode = "openaq" if is_openaq_mode else "demo"

    # City selector enabled only in demo mode
    if not is_openaq_mode:
        selected_city = st.selectbox("Demo City", CITIES, index=1)
    else:
        selected_city = "Bengaluru"
        st.caption("📍 Station: Koramangala, Bengaluru (Station ID 6206921)")

    st.divider()

    # 2. Household Profile Inputs
    st.markdown("### 🏠 Household Profile")
    children = st.number_input(
        "Children (under 12)",
        min_value=0, max_value=20, value=1, step=1,
    )
    older_adults = st.number_input(
        "Older adults (60+)",
        min_value=0, max_value=20, value=2, step=1,
    )
    respiratory_sensitive = st.checkbox(
        "Respiratory sensitivity (asthma, allergies)"
    )
    has_purifier = st.checkbox("Owns an air purifier")

    st.divider()

    # 3. Model Provider Selector
    st.markdown("### 🤖 Model Provider")
    provider_options = [
        f"Ollama ({OLLAMA_MODEL}) [Default]",
        f"Gemini ({GEMINI_MODEL}) [Optional]",
    ]
    provider_idx = 0 if LLM_PROVIDER == "ollama" else 1
    selected_provider_choice = st.selectbox(
        "Active LLM",
        provider_options,
        index=provider_idx,
        help="Ollama runs locally on your PC. Gemini uses your GEMINI_API_KEY.",
    )
    selected_provider = "ollama" if "Ollama" in selected_provider_choice else "gemini"

    st.divider()
    st.caption(
        "Suggestions are general information only — not medical advice. "
        "Consult healthcare professionals for personal medical decisions."
    )

# ── Main Header ─────────────────────────────────────────────────────────────
st.title("🌿 Urban Air Quality Assistant")
st.caption("Personalised, practical exposure & emission guidance for Indian cities.")

# ── Data Fetching & Cache Management ────────────────────────────────────────
col_head, col_refresh = st.columns([0.72, 0.28])
with col_head:
    st.markdown("#### 📍 Air Quality Snapshot")
with col_refresh:
    refresh_clicked = st.button("🔄 Refresh Data", use_container_width=True)

if refresh_clicked:
    if is_openaq_mode:
        invalidate_openaq_cache()

# Fetch data safely
air_data = None
fetch_error = None

try:
    air_data = get_air_quality(
        city=selected_city,
        source_mode=source_mode,
        force_refresh=refresh_clicked,
    )
except EnvironmentError as e:
    fetch_error = ("Configuration Error", str(e), "🔑")
except PermissionError as e:
    fetch_error = ("Authentication Error", str(e), "🔒")
except ValueError as e:
    fetch_error = ("Metadata Verification Error", str(e), "⚠️")
except Exception as e:
    fetch_error = ("Network / Data Error", str(e), "⏱️")

# Invalidate previous plan if data signature changes
if air_data:
    current_data_sig = (
        f"{air_data.get('source_mode')}:"
        f"{air_data.get('station_name')}:"
        f"{air_data.get('measurement_time_ist')}:"
        f"{air_data.get('pm25_ugm3')}"
    )
    if st.session_state.get("last_data_sig") != current_data_sig:
        st.session_state["last_data_sig"] = current_data_sig
        st.session_state.pop("generated_plan", None)

# ── Render Snapshot Main Card ───────────────────────────────────────────────
if fetch_error:
    err_title, err_msg, err_icon = fetch_error
    st.error(f"**{err_title}**\n\n{err_msg}", icon=err_icon)
    if is_openaq_mode:
        st.info("Tip: You can switch to **Demo (Synthetic Data)** mode in the sidebar to test offline.", icon="💡")
    st.stop()

if air_data:
    val = air_data["pm25_ugm3"]
    units = air_data["unit"]
    station_name = air_data["station_name"]
    meas_time = air_data.get("measurement_time_ist", "Unknown")
    fetch_time = air_data.get("fetch_time_ist", "Unknown")
    reading_age = air_data.get("reading_age_str", "N/A")
    is_sample = air_data.get("is_sample", False)
    is_stale = air_data.get("is_stale", False)
    provider = air_data.get("provider", "Unknown")
    is_cached = air_data.get("is_cached", False)

    # Status Pill matching approved screenshot
    if is_sample:
        badge_html = '<span class="badge-demo">🧪 DEMO DATA — NOT LIVE</span>'
    elif is_stale:
        badge_html = f'<span class="badge-stale">⚠️ STALE ({reading_age})</span>'
    else:
        badge_html = f'<span class="badge-live">🟢 LIVE ({reading_age})</span>'

    # Notice banner for demo data
    if is_sample:
        st.warning(
            "⚠️  **SAMPLE DATA — NOT LIVE.**  "
            "These values are illustrative placeholders for demonstration. "
            "They do not reflect current sensor readings.",
            icon="🧪",
        )
    elif is_stale:
        st.warning(
            f"⚠️ **STALE MEASUREMENT:** This reading is {reading_age} (older than our 24-hour freshness policy threshold). "
            "It may not reflect current ambient air conditions.",
            icon="⏱️",
        )

    # Snapshot Card
    cached_tag = "(Cached)" if is_cached else "(Fresh fetch)"
    card_html = f"""
    <div class="main-card">
        <div class="card-top-row" style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:8px;">
            <div>
                <span style="font-size:0.75rem; text-transform:uppercase; letter-spacing:0.06em; color:#78a38c; font-weight:600;">
                    LATEST AVAILABLE PM2.5 MEASUREMENT
                </span>
                <div style="font-size:1.25rem; font-weight:700; color:#e6f4ed; margin-top:2px;">
                    {station_name}
                </div>
            </div>
            <div>
                {badge_html}
            </div>
        </div>
        <div style="display:flex; align-items:baseline; margin: 12px 0 10px 0;">
            <span class="pm25-val-text" style="font-size:3.2rem; font-weight:800; color:#49df94; letter-spacing:-0.03em; line-height:1;">
                {val:.1f}
            </span>
            <span style="font-size:1.15rem; font-weight:600; color:#98ccb1; margin-left:6px;">
                {units}
            </span>
        </div>
        <div class="meta-desc" style="font-size:0.82rem; color:#8cb29d; margin-top:6px; line-height:1.5;">
            <div><strong>Measured at:</strong> {meas_time} &nbsp;|&nbsp; <strong>Reading age:</strong> {reading_age}</div>
            <div><strong>API Fetch time:</strong> {fetch_time} {cached_tag}</div>
            <div style="margin-top:6px; font-style:italic; color:#749c86;">
                Single-station observation — not a citywide average. Concentration is NOT an AQI score.
            </div>
        </div>
    </div>
    """
    st.markdown(card_html, unsafe_allow_html=True)

    if not is_sample:
        st.caption(f"Source: OpenAQ v3 (Location ID: {air_data.get('location_id')}, Sensor ID: {air_data.get('sensor_id')}) · Original provider: {provider}")

# ── Plan Generation Section ─────────────────────────────────────────────────
st.divider()
st.subheader("🗓️ Your Personalised Daily Plan")

if "requesting" not in st.session_state:
    st.session_state["requesting"] = False

can_generate = (air_data is not None)
generate_btn = st.button(
    "✨ Generate my daily plan",
    type="primary",
    use_container_width=True,
    disabled=st.session_state["requesting"] or not can_generate,
)

if generate_btn:
    household = {
        "children": int(children),
        "older_adults": int(older_adults),
        "respiratory_sensitive": bool(respiratory_sensitive),
        "has_purifier": bool(has_purifier),
    }

    st.session_state["requesting"] = True
    status_placeholder = st.empty()
    provider_meta = get_provider_info(selected_provider)
    target_provider_label = provider_meta["provider_label"]

    def _on_retry(attempt: int, max_attempts: int, wait_s: float) -> None:
        status_placeholder.info(
            f"⏳ {target_provider_label} is validating suggestions — retrying "
            f"({attempt} of {max_attempts - 1})… Waiting {wait_s:.0f} s.",
            icon="🔄",
        )

    with st.spinner(f"Asking {target_provider_label} for personalised suggestions…"):
        try:
            plan_result = get_suggestions(
                city=selected_city,
                air_data=air_data,
                household=household,
                provider=selected_provider,
                on_retry=_on_retry,
            )
            st.session_state["generated_plan"] = plan_result

        except EnvironmentError as exc:
            st.session_state["requesting"] = False
            status_placeholder.empty()
            st.error(f"**API key missing.**\n\n{exc}", icon="🔑")
            st.stop()

        except PermissionError as exc:
            st.session_state["requesting"] = False
            status_placeholder.empty()
            st.error(f"**API key invalid or unauthorised.**\n\n{exc}", icon="🔒")
            st.stop()

        except RuntimeError as exc:
            st.session_state["requesting"] = False
            status_placeholder.empty()
            st.error(str(exc), icon="⏱️")
            st.stop()

        except ValueError as exc:
            st.session_state["requesting"] = False
            status_placeholder.empty()
            st.error(f"**Validation error:**\n\n{exc}", icon="⚠️")
            st.stop()

    st.session_state["requesting"] = False
    status_placeholder.empty()

# ── Render Saved or Newly Generated Plan ────────────────────────────────────
saved_plan = st.session_state.get("generated_plan")

if saved_plan:
    suggestions = saved_plan["suggestions"]
    actual_provider_label = saved_plan["provider_label"]

    FOCUS_LABELS = {
        "exposure_reduction": ("🛡️", "Exposure Reduction"),
        "emission_reduction": ("🌱", "Emission Reduction"),
    }

    for i, suggestion in enumerate(suggestions, start=1):
        label   = suggestion.get("label",  "Suggestion")
        action  = suggestion.get("action", "No action provided.")
        why     = suggestion.get("why",    "No explanation provided.")
        focus   = suggestion.get("focus",  "").lower()

        badge_icon, focus_label = FOCUS_LABELS.get(
            focus, ("💡", focus.replace("_", " ").title())
        )

        card_content = f"""
        <div class="suggestion-card">
            <div class="suggestion-header-row" style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                <span style="font-size:1.15rem; font-weight:700; color:#e0f5ea;">#{i} {label}</span>
                <span class="focus-badge">{badge_icon} {focus_label}</span>
            </div>
            <div style="font-size:0.92rem; color:#d2ede0; margin-bottom:6px; line-height:1.4;">
                <strong>🎯 Action:</strong> {action}
            </div>
            <div style="font-size:0.87rem; color:#95c1ab; line-height:1.4;">
                <strong>💬 Why it helps:</strong> {why}
            </div>
        </div>
        """
        st.markdown(card_content, unsafe_allow_html=True)

    st.success(
        f"Plan generated using {actual_provider_label}! These are general suggestions — not medical advice.",
        icon="✅",
    )
    st.caption(
        f"Powered by {actual_provider_label} · Single-station observation at {air_data['station_name']} · "
        "Not a substitute for professional healthcare guidance."
    )
else:
    if air_data and not generate_btn:
        st.info(
            "Review your household profile in the sidebar, then click **✨ Generate my daily plan**.",
            icon="👈",
        )
