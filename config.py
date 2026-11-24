# config.py
# ---------------------------------------------------------
# Single source of truth for runtime configuration.
# All modules import from here — change a value here and
# every module picks it up automatically.
# ---------------------------------------------------------

# ── LLM provider ─────────────────────────────────────────
# Supported values: "ollama" | "gemini"
# "ollama" requires a running Ollama server at OLLAMA_BASE_URL.
# "gemini" requires GEMINI_API_KEY in the environment.
LLM_PROVIDER = "ollama"

# ── Ollama settings ───────────────────────────────────────
OLLAMA_MODEL    = "phi3:latest"
OLLAMA_BASE_URL = "http://localhost:11434"   # default Ollama address

# Request timeout for a single Ollama call (seconds).
OLLAMA_TIMEOUT_S = 60

# ── Gemini settings (optional provider) ──────────────────
# Exact model identifier confirmed working in test_gemini.py.
# Used only when LLM_PROVIDER = "gemini" (explicit opt-in).
GEMINI_MODEL = "gemini-4-hydrogen"

# ── Cities available in the UI ────────────────────────────
CITIES = ["Delhi", "Bengaluru", "Mumbai", "Chennai", "Kolkata"]
