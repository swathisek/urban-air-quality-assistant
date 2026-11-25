# Urban Air Quality Assistant

A Streamlit app that generates a personalised daily action plan using
air-quality information and household inputs.

The app supports local generation with Ollama and explicitly selected
generation with Google Gemini. It displays exactly three validated advice
cards in a dark-green interface.

## Current Status

- OpenAQ integration is implemented.
- Local plan generation has been tested successfully with Ollama.
- Local plan generation has been tested successfully with Gemini using
  `gemini-3.1-flash-lite`.
- Ollama is the default provider; Gemini requires explicit selection.
- There is no automatic fallback between providers.
- Google Cloud Run deployment is pending.
- Mobile-specific CSS is included, but phone behaviour has not yet been
  verified.

## Features

- Household profile inputs for personalised suggestions.
- A city selector containing Delhi, Bengaluru, Mumbai, Chennai, and Kolkata.
- Live OpenAQ integration for the configured Koramangala, Bengaluru station.
- Pollutant and unit checks for OpenAQ measurements.
- Separate measurement and fetch timestamps.
- Three advice cards with action descriptions and explanations.
- Recognised action identifiers and duplicate-action checks.
- Exposure-reduction and emission-reduction action categories.
- Explicit Ollama or Gemini provider selection.
- User-facing messages for data or generation failures.

The city selector does not imply that verified live station coverage is
available for every listed city. The verified station configuration described
below is for Koramangala, Bengaluru.

## Air-Quality Data and Limitations

The configured OpenAQ source is:

| Field | Value |
|---|---|
| Location | Koramangala, Bengaluru |
| OpenAQ location ID | `6206921` |
| PM2.5 sensor ID | `15203555` |
| Parameter | `pm25` |
| Units | Micrograms per cubic metre |
| Provider | AirGradient |

These measurements are single-station PM2.5 observations. They are not
citywide measurements and are not AQI scores.

Readings can change between requests. Example values observed during testing
are not constants and should not be treated as current conditions.

Check the displayed measurement timestamp when interpreting a reading.

## Requirements

- Python 3.10 or later.
- The packages listed in `requirements.txt`.
- An OpenAQ API key for live OpenAQ requests.
- For Ollama: a running local Ollama server and the configured model.
- For Gemini: a Gemini API key and explicit Gemini provider selection.

Current declared dependencies:

```text
streamlit>=1.35.0
google-genai>=1.0.0
requests>=2.31.0
```

## Local Setup on Windows

### 1. Open the project folder

Open PowerShell in the project directory.

### 2. Install Python dependencies

```powershell
python -m pip install -r requirements.txt
```

Using a dedicated Python environment is recommended.

### 3. Configure live OpenAQ access

Set the key in the same PowerShell session used to start the app:

```powershell
$env:OPENAQ_API_KEY = "YOUR_OPENAQ_API_KEY"
```

Replace the placeholder locally. Do not put real API keys in source files,
screenshots, or Git commits.

### 4. Select a generation provider

#### Option A: Ollama - local default

The current configuration uses:

```text
Model: phi3:latest
Server: http://localhost:11434
```

Ensure Ollama is running and the model is available.

To select Ollama explicitly:

```powershell
$env:LLM_PROVIDER = "ollama"
```

#### Option B: Gemini - explicit opt-in

```powershell
$env:LLM_PROVIDER = "gemini"
$env:GEMINI_MODEL = "gemini-3.1-flash-lite"
$env:GEMINI_API_KEY = "YOUR_GEMINI_API_KEY"
```

Gemini generation with this model has been tested locally. API availability
and quota still apply.

These PowerShell assignments apply to the current session. Restart the app
after changing environment variables.

### 5. Launch the app

```powershell
python -m streamlit run app.py
```

Open the local address printed by Streamlit, complete the household inputs,
select the intended provider, and generate a daily plan.

## Runtime Configuration

`config.py` contains the shared runtime settings.

| Setting | Default |
|---|---|
| `LLM_PROVIDER` | `ollama` |
| `GEMINI_MODEL` | `gemini-3.1-flash-lite` |
| `OLLAMA_MODEL` | `phi3:latest` |
| `OLLAMA_BASE_URL` | `http://localhost:11434` |
| `OLLAMA_TIMEOUT_S` | `60` |

`LLM_PROVIDER` and `GEMINI_MODEL` can be overridden through environment
variables.

Provider selection is explicit. A failed request must not silently switch
to another provider.

## Project Structure

```text
app.py                       Streamlit interface
config.py                    Shared runtime configuration
actions.py                   Action definitions
advice.py                    Advice generation and validation
llm_ollama.py                Ollama integration
data.py                      Demo/sample-data module
data_openaq.py               OpenAQ integration
history_openaq.py            Historical-data module
requirements.txt            Python dependencies
.gitignore                   Git exclusion rules
README.md                    Project documentation

test_gemini.py               Gemini diagnostic script
test_history_openaq.py       Historical-data test script
test_live_ollama.py          Local generation test script
test_openaq_bengaluru.py      Bengaluru OpenAQ test script
test_output_validation.py    Output-validation test script
test_stage1_openaq.py        OpenAQ test script
```

The presence of a test script does not mean that every test has passed in
the current environment.

## Historical Data

A historical-data module is included in the source code.

The current Streamlit interface does not import or render historical trend
charts. This is not yet a completed user-facing feature.

## Validation and Limitations

- The generated plan must contain exactly three advice cards.
- Actions are checked against recognised identifiers.
- Duplicate action identifiers are rejected.
- OpenAQ pollutant and measurement units are checked.
- Personalisation depends on the household inputs supplied.
- Model-generated wording can vary between requests.
- Prompt instructions alone do not guarantee every household constraint;
  independent validation does not yet cover every restriction.
- The app provides general suggestions, not professional medical advice.

## Deployment

The required deployment target is Google Cloud Run.

Deployment has not yet been completed or verified. No public deployment URL
is claimed in this README.

A successful local run is not evidence of a working cloud deployment.

## Security

- Keep API keys outside source code.
- Supply keys through environment variables for local use.
- Do not commit credentials or include them in screenshots.
- Review staged changes before pushing to this public repository.

## Remaining Work

- Prepare and verify the Google Cloud Run deployment.
- Test the deployed app end to end.
- Verify the layout and interactions on a phone.
- Add historical charts to the interface if required.
- Extend independent validation of household-specific restrictions.
- Publish the LinkedIn build-in-public post after verifying its claims.

## Important Notice

This app is an educational air-quality assistance project. Its suggestions
are general information, not medical advice.

A single monitoring station may not represent conditions at a user's home.
Consider the measurement location and timestamp when interpreting results.