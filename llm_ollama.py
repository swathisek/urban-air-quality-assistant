# llm_ollama.py
# ---------------------------------------------------------
# Ollama backend for the Urban Air Quality Assistant.
#
# Calls the Ollama REST API directly using the standard
# library (urllib) so no extra dependency is needed beyond
# `requests`, which is already a Streamlit transitive dep.
#
# Supported endpoint: POST /api/generate  (Ollama ≥ 0.1.x)
# Returns the full response text as a plain string.
#
# API keys: none required. Ollama is local-only by default.
# ---------------------------------------------------------

import json
import requests

from config import OLLAMA_BASE_URL, OLLAMA_MODEL, OLLAMA_TIMEOUT_S


def _ollama_generate(prompt: str) -> str:
    """
    POST a prompt to the local Ollama /api/generate endpoint
    and return the complete response text.

    Parameters
    ----------
    prompt : str
        The full prompt string to send.

    Returns
    -------
    str
        The model's response text (stripped).

    Raises
    ------
    RuntimeError
        If Ollama is unreachable, the model is missing, or the
        response cannot be parsed.
    """
    url = f"{OLLAMA_BASE_URL.rstrip('/')}/api/generate"
    payload = {
        "model":  OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,          # collect full response in one shot
        "options": {
            "temperature": 0.3,   # lower = more consistent JSON output
            "num_predict": 512,   # hard token cap — keeps response bounded
        },
    }

    try:
        response = requests.post(
            url,
            json=payload,
            timeout=OLLAMA_TIMEOUT_S,
        )
    except requests.exceptions.ConnectionError:
        raise RuntimeError(
            f"Could not connect to Ollama at {OLLAMA_BASE_URL}. "
            "Make sure Ollama is running (`ollama serve`) and try again."
        )
    except requests.exceptions.Timeout:
        raise RuntimeError(
            f"Ollama did not respond within {OLLAMA_TIMEOUT_S} seconds. "
            "The model may be loading — wait a moment and try again."
        )

    if response.status_code == 404:
        raise RuntimeError(
            f"Ollama model '{OLLAMA_MODEL}' was not found. "
            f"Run: ollama pull {OLLAMA_MODEL}"
        )

    if response.status_code != 200:
        raise RuntimeError(
            f"Ollama returned HTTP {response.status_code}: {response.text[:300]}"
        )

    try:
        data = response.json()
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Could not parse Ollama's response as JSON: {exc}\n"
            f"Raw text: {response.text[:300]}"
        ) from exc

    text = data.get("response", "").strip()
    if not text:
        raise RuntimeError(
            "Ollama returned an empty response. "
            "The model may have run out of context — try again."
        )

    return text


def call_ollama(prompt: str) -> str:
    """
    Public entry point: call Ollama and return the response text.

    Parameters
    ----------
    prompt : str
        Full prompt string.

    Returns
    -------
    str
        Model response text.

    Raises
    ------
    RuntimeError
        Propagated from _ollama_generate with user-friendly messages.
    """
    return _ollama_generate(prompt)
