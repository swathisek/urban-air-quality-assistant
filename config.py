# config.py
# ---------------------------------------------------------
# Shared runtime configuration.
# Environment variables are read when this module is loaded.
# Restart the app after changing environment variables.
# ---------------------------------------------------------

import os

# ── LLM provider ─────────────────────────────────────────
# Supported values: "ollama" | "gemini"
# Ollama remains the default unless explicitly overridden.
# No automatic fallback between providers.
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama").strip().lower()

# ── Ollama settings ───────────────────────────────────────
# Requires a running Ollama server at OLLAMA_BASE_URL.
OLLAMA_MODEL = "phi3:latest"
OLLAMA_BASE_URL = "http://localhost:11434"

# Request timeout for a single Ollama call (seconds).
OLLAMA_TIMEOUT_S = 60

# ── Gemini settings ───────────────────────────────────────
# Requires GEMINI_API_KEY in the environment.
# Optional model override through GEMINI_MODEL.
GEMINI_MODEL = os.getenv(
    "GEMINI_MODEL", "gemini-3.1-flash-lite"
).strip()

# ── Cities available in the UI ────────────────────────────
CITIES = ["Delhi", "Bengaluru", "Mumbai", "Chennai", "Kolkata"]
