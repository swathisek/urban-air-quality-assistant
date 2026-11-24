# 🌫️ Urban Air Quality Assistant

A Streamlit web app that gives residents of Indian cities a **personalised daily action plan**
based on local air quality and their household profile.

> **Milestone 1 — Demo mode.** Pollution values are synthetic sample data.
> Live OpenAQ integration is planned for Milestone 2.

---

## Features (Milestone 1)

| Feature | Status |
|---|---|
| City selector (Delhi, Bengaluru, Mumbai, Chennai, Kolkata) | ✅ |
| Demo data mode (PM2.5 sample values, clearly labelled) | ✅ |
| Household profile inputs | ✅ |
| Gemini-powered personalised suggestions | ✅ |
| Exposure vs. emission reduction labelling | ✅ |
| Readable error messages for missing keys / API failures | ✅ |

---

## Prerequisites

- Python 3.10 or later
- A Python virtual environment (venv or similar)
- Two Windows environment variables set **before** launching the app:
  - `GEMINI_API_KEY` — your Google Gemini API key
  - `OPENAQ_API_KEY` — your OpenAQ API key (used in Milestone 2)

### Setting environment variables (Windows)

```powershell
# Set for the current PowerShell session only:
$env:GEMINI_API_KEY = "your-key-here"
$env:OPENAQ_API_KEY = "your-key-here"
```

Or set them permanently via:
**Start → Search "environment variables" → Edit the system environment variables → Environment Variables**

---

## Setup & Launch

### 1. Open PowerShell and navigate to the project folder

```powershell
cd "C:\Users\Chidi\Desktop\semester 4\googleantigravity_urban_air_quality"
```

### 2. Activate your virtual environment

```powershell
# If your venv is named 'venv':
.\venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```powershell
pip install -r requirements.txt
```

### 4. Run the app

```powershell
streamlit run app.py
```

The app will open automatically at `http://localhost:8501`.

---

## Project Structure

```
googleantigravity_urban_air_quality/
│
├── app.py              # Streamlit front-end
├── advice.py           # Gemini API integration (suggestions)
├── data.py             # Sample air quality data (swappable in Milestone 2)
├── config.py           # Gemini model identifier & city list (single config)
├── requirements.txt    # Python dependencies
├── .gitignore          # Excludes .env, venv/, __pycache__/, etc.
├── README.md           # This file
│
└── test_gemini.py      # Original Gemini API test (do not modify)
```

---

## Important Notices

- **Not medical advice.** All suggestions are general information only.
- **Sample data.** PM2.5 values in Milestone 1 are illustrative placeholders,
  not live sensor readings. They are **not** AQI scores.
- **API keys.** Keys are read from environment variables and are never stored
  in code or printed to logs.

---

## Roadmap

| Milestone | Description |
|---|---|
| 1 ✅ | Demo mode, Gemini suggestions, household profile |
| 2 | Live PM2.5 data from OpenAQ API |
| 3 | Historical trend chart |
| 4 | (TBD) |
