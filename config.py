# config.py
# ---------------------------------------------------------
# Shared runtime configuration.
# Reads Streamlit secrets first, then environment variables.
# Restart the app after changing configuration.
# ---------------------------------------------------------

import os

try:
    import streamlit as st

    _SECRETS = st.secrets
except Exception:
    _SECRETS = {}


def _get_setting(name: str, default: str = "") -> str:
    try:
        value = _SECRETS.get(name, "")
    except Exception:
        value = ""
    if not value:
        value = os.getenv(name, "")
    return str(value).strip()


# Supported values: "ollama" | "gemini"
# Ollama remains the default unless explicitly overridden.
# No automatic fallback between providers.
LLM_PROVIDER = _get_setting("LLM_PROVIDER", "ollama").lower()

# Ollama settings
OLLAMA_MODEL = "phi3:latest"
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_TIMEOUT_S = 60

# Gemini settings
GEMINI_MODEL = _get_setting("GEMINI_MODEL", "gemini-3.1-flash-lite")
# Cities available in the UI
CITIES = ["Delhi", "Bengaluru", "Mumbai", "Chennai", "Kolkata"]