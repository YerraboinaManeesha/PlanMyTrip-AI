# 🧭 PlanMyTrip AI

An AI-assisted travel planning app — built with Streamlit, Groq (Llama 3.1), Tavily web search, and Open-Meteo live weather.

## Features

- **Trip planner** — enter origin, destination, dates, budget, and interests to get a full day-by-day itinerary
- **Live weather** for your destination (Open-Meteo, no API key needed)
- **Local insights** — AI-generated vibe, best time to visit, customs, and practical heads-up, grounded in live web search (clearly labeled as AI-generated, not an official rating)
- **Budget dashboard** — visual breakdown of estimated spend by category
- **AI chatbot with trip memory** — ask follow-up questions about your specific plan; it remembers the itinerary and the conversation
- **Compare two destinations** side-by-side (weather, budget fit, vibe)
- **Export** — download the itinerary as a PDF, or share a summary on WhatsApp
- **Booking shortcuts** — quick links to Skyscanner, IRCTC, RedBus, Booking.com

## Tech stack

| Piece | Purpose |
|---|---|
| Streamlit | UI framework |
| Groq API (Llama 3.1 8B) | Itinerary generation + chatbot |
| Tavily API | Live web search for local insights |
| Open-Meteo | Free live weather (no key required) |
| Plotly | Budget chart |
| fpdf2 | PDF export |

## Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Add your API keys
Copy the example secrets file and fill in your real keys:
```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```
Then edit `.streamlit/secrets.toml`:
```toml
GROQ_API_KEY = "your_groq_api_key_here"
TAVILY_API_KEY = "your_tavily_api_key_here"
```
Get a free Groq key at console.groq.com, and a free Tavily key at tavily.com.

### 3. Run locally
```bash
streamlit run app.py
```
Open http://localhost:8501

## Deploy on Streamlit Community Cloud (free)

1. Push this folder to a GitHub repo (make sure `.streamlit/secrets.toml` is in `.gitignore` — never commit real keys)
2. Go to share.streamlit.io → "New app" → select your repo, set main file to `app.py`
3. Under "Advanced settings" → paste your secrets (same format as `secrets.toml`)
4. Deploy

## Notes on the "local insights" feature

This is intentionally **not** framed as a precision safety score. It's an LLM summary generated from a handful of live search results — useful as a starting point, but travelers should still check current official travel advisories for their destination.

## Project structure
```
planmytrip-ai/
├── app.py                        # Main Streamlit app
├── requirements.txt
├── .streamlit/
│   └── secrets.toml.example      # Copy to secrets.toml and fill in keys
└── README.md
```

---
Built by Maneesha Yerraboina.
