import datetime
import re
import urllib.parse
from pathlib import Path

import requests
import streamlit as st
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader
from fpdf import FPDF
from fpdf.enums import XPos, YPos
from groq import Groq
from tavily import TavilyClient


# Page setup

st.set_page_config(
    page_title="PlanMyTrip AI",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

BASE_DIR = Path(__file__).resolve().parent

with open(BASE_DIR / "style.css", "r", encoding="utf-8") as f:
    st.markdown(
        f"<style>{f.read()}</style>",
        unsafe_allow_html=True,
    )


# API setup

GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", "")
TAVILY_API_KEY = st.secrets.get("TAVILY_API_KEY", "")

GROQ_MODEL = "openai/gpt-oss-120b"

groq_client = (
    Groq(api_key=GROQ_API_KEY)
    if GROQ_API_KEY
    else None
)

tavily_client = (
    TavilyClient(api_key=TAVILY_API_KEY)
    if TAVILY_API_KEY
    else None
)


# Authentication

AUTH_CONFIG_PATH = "config.yaml"


def load_auth_config():
    with open(AUTH_CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.load(f, Loader=SafeLoader)


def save_auth_config(config):
    with open(AUTH_CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)


auth_config = load_auth_config()

authenticator = stauth.Authenticate(
    auth_config["credentials"],
    auth_config["cookie"]["name"],
    auth_config["cookie"]["key"],
    auth_config["cookie"]["expiry_days"],
)


# Weather

WEATHER_CODES = {
    0: "☀️ Clear sky",
    1: "🌤️ Mostly clear",
    2: "⛅ Partly cloudy",
    3: "☁️ Overcast",
    45: "🌫️ Foggy",
    48: "🌫️ Depositing fog",
    51: "🌦️ Light drizzle",
    53: "🌦️ Moderate drizzle",
    55: "🌦️ Dense drizzle",
    56: "🌦️ Freezing drizzle",
    57: "🌦️ Dense freezing drizzle",
    61: "🌧️ Light rain",
    63: "🌧️ Moderate rain",
    65: "🌧️ Heavy rain",
    66: "🌧️ Freezing rain",
    67: "🌧️ Heavy freezing rain",
    71: "🌨️ Light snow",
    73: "🌨️ Moderate snow",
    75: "🌨️ Heavy snow",
    77: "🌨️ Snow grains",
    80: "🌦️ Rain showers",
    81: "🌦️ Moderate rain showers",
    82: "🌧️ Heavy rain showers",
    85: "🌨️ Light snow showers",
    86: "🌨️ Heavy snow showers",
    95: "⛈️ Thunderstorm",
    96: "⛈️ Thunderstorm with hail",
    99: "⛈️ Heavy thunderstorm with hail",
}


# Destinations

DESTINATIONS = {
    "India": [
        "Hyderabad",
        "Goa",
        "Kerala",
        "Jaipur",
        "Mumbai",
        "Delhi",
        "Manali",
        "Mysore",
        "Bengaluru",
        "Chennai",
        "Kolkata",
        "Agra",
        "Udaipur",
        "Varanasi",
        "Rishikesh",
        "Ooty",
        "Coorg",
        "Andaman and Nicobar Islands",
        "Amritsar",
        "Darjeeling",
        "Shimla",
        "Pondicherry",
        "Munnar",
        "Wayanad",
    ],
    "International": [
        "Paris",
        "Tokyo",
        "Dubai",
        "Rome",
        "London",
        "Singapore",
        "Bangkok",
        "Bali",
        "Seoul",
        "Maldives",
        "New York",
        "Barcelona",
        "Amsterdam",
        "Switzerland",
        "Istanbul",
        "Sydney",
        "Melbourne",
        "Cape Town",
        "Cairo",
        "Toronto",
        "Kuala Lumpur",
        "Hong Kong",
        "Abu Dhabi",
        "Doha",
        "Phuket",
        "Kathmandu",
        "Mauritius",
        "New Zealand",
    ],
}


# Session state

defaults = {
    "view": "landing",
    "picked_destination": "",
    "destination_type": "India",
    "plan_ready": False,
    "chat_log": [],
    "plan_text": "",
    "plan_meta": {},
    "comparison_result": None,
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


# Weather function

def get_weather(place: str):
    try:
        place = place.strip()

        if not place:
            return None

        geo_response = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={
                "name": place,
                "count": 10,
                "language": "en",
                "format": "json",
            },
            timeout=8,
        )

        geo_response.raise_for_status()

        geo = geo_response.json()
        results = geo.get("results", [])

        if not results:
            return None

        place_lower = place.lower()

        def score_location(item):
            score = 0

            name = str(item.get("name", "")).lower()
            country = str(item.get("country", "")).lower()
            country_code = str(item.get("country_code", "")).lower()
            admin1 = str(item.get("admin1", "")).lower()
            feature_code = str(item.get("feature_code", "")).upper()

            if name == place_lower:
                score += 100
            if place_lower in name:
                score += 30
            if place_lower in admin1:
                score += 25
            if country_code == "in":
                score += 15
            if "india" in country:
                score += 15
            if feature_code in {"PPLC", "PPLA", "PPLA2", "PPLA3"}:
                score += 10

            return score

        results.sort(key=score_location, reverse=True)

        hit = results[0]
        lat = hit.get("latitude")
        lon = hit.get("longitude")

        if lat is None or lon is None:
            return None

        weather_response = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "current": (
                    "temperature_2m,"
                    "relative_humidity_2m,"
                    "apparent_temperature,"
                    "precipitation,"
                    "weather_code,"
                    "wind_speed_10m"
                ),
                "hourly": "precipitation_probability",
                "forecast_days": 1,
                "timezone": "auto",
            },
            timeout=8,
        )

        weather_response.raise_for_status()

        wx = weather_response.json()
        current = wx.get("current", {})

        if not current:
            return None

        humidity = current.get("relative_humidity_2m", "—")
        rain_chance = "—"

        hourly = wx.get("hourly", {})
        hourly_times = hourly.get("time", [])
        rain_values = hourly.get("precipitation_probability", [])
        current_time = current.get("time")

        if current_time and hourly_times and rain_values:
            current_dt = datetime.datetime.fromisoformat(current_time)

            closest_index = min(
                range(len(hourly_times)),
                key=lambda i: abs(
                    datetime.datetime.fromisoformat(hourly_times[i]) - current_dt
                ),
            )

            if closest_index < len(rain_values):
                rain_chance = rain_values[closest_index]

        return {
            "place": hit.get("name", place),
            "country": hit.get("country", ""),
            "admin1": hit.get("admin1", ""),
            "temp": current.get("temperature_2m", "—"),
            "wind": current.get("wind_speed_10m", "—"),
            "condition": WEATHER_CODES.get(
                current.get("weather_code"),
                "🌡️ Current conditions",
            ),
            "humidity": humidity,
            "rain_chance": rain_chance,
        }

    except Exception:
        return None


# Budget

def budget_tier(per_day, currency_code):
    thresholds = {
        "INR": (1500, 4000, 10000),
        "USD": (50, 150, 300),
        "EUR": (45, 130, 250),
        "GBP": (40, 110, 220),
    }

    low, mid, high = thresholds.get(currency_code, thresholds["INR"])

    if per_day < low:
        return "tight", "Budget"
    if per_day < mid:
        return "lean", "Budget"
    if per_day < high:
        return "comfortable", "Mid-range"
    return "roomy", "Premium"


# AI

def ask_groq(messages, max_tokens=900, temperature=0.7):
    if not groq_client:
        raise RuntimeError("GROQ_API_KEY is not configured.")

    response = groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
    )

    return response.choices[0].message.content


# Web search

def search_web(query, max_results=3):
    if not tavily_client:
        return ""

    try:
        result = tavily_client.search(
            query=query,
            max_results=max_results,
            search_depth="basic",
        )

        return "\n".join(
            f"- {item.get('title', '')}: {item.get('content', '')[:280]}"
            for item in result.get("results", [])
        )

    except Exception:
        return ""


# Prompts

def build_itinerary_prompt(
    origin, dest, days, budget_str, tier_label,
    dates, travelers, interests, notes, web_context,
):
    interests_text = ", ".join(interests) if interests else "general sightseeing"

    return f"""
You are a practical, detail-oriented travel planner.

Trip:
From {origin or "the traveler's home city"} to {dest}

Duration:
{days} day(s)

Dates:
{dates}

Travelers:
{travelers}

Budget:
{budget_str} total

Budget tier:
{tier_label}

Interests:
{interests_text}

Special notes:
{notes or "none"}

Background research from the web:
{web_context or "No web data available. Use general knowledge and say so if unsure."}

Write the itinerary using this Markdown structure:

## Trip Snapshot

A 2-3 sentence overview of what this trip will feel like.

## Getting There

Realistic transport options from {origin or "home"} to {dest} with rough costs.

## Day-by-Day Plan

One subsection per day from Day 1 to Day {days}.

Each day must include:

### Morning

### Afternoon

### Evening

## Where to Stay

Give 2-3 options that match the {tier_label} tier with approximate price ranges.

## Food to Try

Local dishes and a couple of specific restaurant or area suggestions.

## Budget Breakdown

Give a rough split of the {budget_str} total across transport, stay, food, and activities.

Make the numbers add up sensibly.

## Practical Tips

Local customs, what to pack, transportation advice, and anything a first-time visitor should know.

Keep everything concrete and specific to {dest}.

Do not invent exact prices when uncertain. Use ranges.

Formatting rules:

- Use Markdown only.
- Do not use HTML tags.
- Do not use <br>, <div>, <span>, or other HTML tags.
- Keep every bullet on its own line.
"""


def build_local_insight_prompt(dest, web_context):
    return f"""
Based on this web research about {dest}:

{web_context or "No web data available."}

Give a short, honest local-insights summary for a first-time visitor.

Respond in exactly this format:

VIBE: [one short phrase describing the general atmosphere]

BEST_TIME: [best months to visit and why, one line]

CUSTOMS: [1-2 local etiquette or cultural notes]

GETTING_AROUND: [how tourists typically get around]

HEADS_UP: [one practical thing to be aware of]

Be specific to {dest}.

If the research does not cover something, say so briefly rather than guessing.
"""


def parse_insight_fields(reply):
    fields = {}
    for line in reply.strip().split("\n"):
        if ":" in line:
            key, value = line.split(":", 1)
            fields[key.strip()] = value.strip()
    return fields


# Markdown cleanup

def clean_markdown(text):
    if not text:
        return ""

    text = text.replace("<br>", "\n")
    text = text.replace("<br/>", "\n")
    text = text.replace("<br />", "\n")

    text = re.sub(r"<div[^>]*>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"</div>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<span[^>]*>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"</span>", "", text, flags=re.IGNORECASE)

    return text.strip()


# PDF

def pdf_safe_text(text):
    if not text:
        return ""

    replacements = {
        "₹": "Rs.", "€": "EUR", "£": "GBP", "¥": "JPY",
        "–": "-", "—": "-", "•": "-",
        "'": "'", "'": "'", """: '"', """: '"',
        "→": "->", "←": "<-", "·": "-",
        "\u00a0": " ",
        "☀️": "", "🌤️": "", "⛅": "", "☁️": "", "🌫️": "",
        "🌦️": "", "🌧️": "", "🌨️": "", "⛈️": "",
        "✈️": "", "❤️": "", "🤖": "",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"(?<!\*)\*(?!\*)", "", text)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = text.replace("|", " ")

    cleaned_lines = []
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped and re.fullmatch(r"[\s|:-]+", stripped):
            continue
        cleaned_lines.append(line)
    text = "\n".join(cleaned_lines)

    text = re.sub(r"[^\x00-\x7F]+", " ", text)
    text = re.sub(r"[ \t]+", " ", text)

    return text.strip()


def make_pdf(title, dest, meta, body_markdown):
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_text_color(0, 0, 0)

    pdf.set_font("helvetica", "B", 18)
    pdf.cell(0, 10, "PlanMyTrip AI", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_font("helvetica", "B", 14)
    pdf.multi_cell(0, 8, pdf_safe_text(title), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(3)

    pdf.set_font("helvetica", "B", 11)
    pdf.cell(0, 7, "Trip Details", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_font("helvetica", "", 10)
    trip_details = [
        f"Destination: {meta.get('dest', '')}",
        f"From: {meta.get('origin', '') or 'Not specified'}",
        f"Dates: {meta.get('dates', '')}",
        f"Duration: {meta.get('days', '')} day(s)",
        f"Travelers: {meta.get('travelers', '')}",
        f"Budget: {meta.get('budget', '')}",
        f"Budget Tier: {meta.get('tier', '')}",
    ]
    for detail in trip_details:
        pdf.multi_cell(0, 6, pdf_safe_text(detail), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(5)

    clean = clean_markdown(body_markdown)
    clean = pdf_safe_text(clean)

    for raw_line in clean.split("\n"):
        line = raw_line.strip()

        if not line:
            pdf.ln(3)
            continue

        if line.startswith("# "):
            heading = line[2:].strip()
            if not heading:
                continue
            pdf.ln(2)
            pdf.set_font("helvetica", "B", 14)
            pdf.set_text_color(0, 0, 0)
            pdf.multi_cell(0, 8, heading, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        elif line.startswith("## "):
            heading = line[3:].strip()
            if not heading:
                continue
            pdf.ln(2)
            pdf.set_font("helvetica", "B", 12)
            pdf.set_text_color(0, 0, 0)
            pdf.multi_cell(0, 7, heading, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        elif line.startswith("### "):
            heading = line[4:].strip()
            if not heading:
                continue
            pdf.ln(1)
            pdf.set_font("helvetica", "B", 11)
            pdf.set_text_color(0, 0, 0)
            pdf.multi_cell(0, 6, heading, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        elif line.startswith("- "):
            content = line[2:].strip()
            pdf.set_font("helvetica", "", 10)
            pdf.set_text_color(0, 0, 0)
            pdf.multi_cell(0, 6, "- " + content, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        elif re.match(r"^\d+\.\s+", line):
            pdf.set_font("helvetica", "", 10)
            pdf.set_text_color(0, 0, 0)
            pdf.multi_cell(0, 6, line, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        else:
            pdf.set_font("helvetica", "", 10)
            pdf.set_text_color(0, 0, 0)
            pdf.multi_cell(0, 6, line, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    output = pdf.output()
    return bytes(output)


# Weather card

def render_weather_card(weather):
    weather_place = str(weather.get("place", ""))
    weather_country = str(weather.get("country", ""))
    weather_temp = weather.get("temp", "—")
    weather_wind = weather.get("wind", "—")
    weather_condition = str(weather.get("condition", "🌡️ Current conditions"))
    weather_humidity = weather.get("humidity", "—")
    weather_rain = weather.get("rain_chance", "—")

    location_text = weather_place
    if weather_country:
        location_text += f", {weather_country}"

    st.markdown(
        f'<div class="tw-card">'
        f'<span class="tw-pill">LIVE WEATHER</span>'
        f'<div class="tw-weather-title">{location_text}</div>'
        f'<div class="tw-weather-main">🌡️ {weather_temp}°C</div>'
        f'<div class="tw-weather-condition">{weather_condition}</div>'
        f'<div class="tw-weather-details">'
        f'💨 {weather_wind} km/h &nbsp;·&nbsp; '
        f'💧 {weather_humidity}% humidity &nbsp;·&nbsp; '
        f'🌧️ {weather_rain}% rain</div>'
        f'</div>',
        unsafe_allow_html=True,
    )



# LANDING PAGE


def render_landing():

    nav_left, nav_right = st.columns([5, 1])
    with nav_left:
        st.markdown("""
<div class="navbar" id="home">
    <div class="brand">✈️ PlanMyTrip <span>AI</span></div>
    <div class="nav-links">
        <a href="#home">Home</a>
        <a href="#features">Features</a>
        <a href="#how-it-works">How It Works</a>
    </div>
</div>
""", unsafe_allow_html=True)
    with nav_right:
        st.markdown('<div class="nav-get-started-spacer"></div>', unsafe_allow_html=True)
        if st.button("Get Started", key="nav_get_started", type="primary", use_container_width=True):
            if st.session_state.get("authentication_status"):
                st.session_state.view = "planner"
            else:
                st.session_state.view = "auth"
            st.rerun()

    st.markdown("""
<div class="hero">
    <div class="hero-badge">
        ✦ AI-POWERED TRAVEL PLANNING
    </div>
    <h1>
        Your next journey,<br>
        <span>planned intelligently.</span>
    </h1>
    <p>
        Create personalized travel itineraries based on your destination,
        budget, interests, and preferences — all in one place.
    </p>
</div>
""", unsafe_allow_html=True)

    hero_btn_cols = st.columns([2, 1, 2])
    with hero_btn_cols[1]:
        if st.button("Start Planning ✨", key="cta_start", type="primary", use_container_width=True):
            if st.session_state.get("authentication_status"):
                st.session_state.view = "planner"
            else:
                st.session_state.view = "auth"
            st.rerun()

    st.markdown("""
<div class="section" id="features">
    <div class="section-title">
        Everything you need to travel smarter
    </div>
    <div class="section-subtitle">
        PlanMyTrip AI combines intelligent planning, live information,
        and practical travel tools to make trip planning simple.
    </div>
</div>
""", unsafe_allow_html=True)

    with st.container(key="feature_row_1"):
        f1, f2, f3 = st.columns(3)
        with f1:
            st.markdown("""
    <div class="feature-card">
        <div class="feature-icon">🧠</div>
        <h3>AI-Powered Itineraries</h3>
        <p>
            Get a day-by-day travel plan tailored to your destination,
            duration, budget, interests, and travel style.
        </p>
    </div>
    """, unsafe_allow_html=True)

        with f2:
            st.markdown("""
    <div class="feature-card">
        <div class="feature-icon">🌤️</div>
        <h3>Live Weather</h3>
        <p>
            Check current weather conditions for your destination
            before making your travel plans.
        </p>
    </div>
    """, unsafe_allow_html=True)

        with f3:
            st.markdown("""
    <div class="feature-card">
        <div class="feature-icon">🔎</div>
        <h3>Local Insights</h3>
        <p>
            Discover useful information about local customs,
            the best time to visit, and getting around.
        </p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    with st.container(key="feature_row_2"):
        f4, f5, f6 = st.columns(3)
        with f4:
            st.markdown("""
    <div class="feature-card">
        <div class="feature-icon">💰</div>
        <h3>Smart Budget Planning</h3>
        <p>
            Understand how your travel budget can be divided across
            accommodation, food, transport, and activities.
        </p>
    </div>
    """, unsafe_allow_html=True)

        with f5:
            st.markdown("""
    <div class="feature-card">
        <div class="feature-icon">💬</div>
        <h3>Ask Your AI Planner</h3>
        <p>
            Ask follow-up questions about your trip and get
            personalized answers based on your itinerary.
        </p>
    </div>
    """, unsafe_allow_html=True)

        with f6:
            st.markdown("""
    <div class="feature-card">
        <div class="feature-icon">📄</div>
        <h3>Save & Share</h3>
        <p>
            Download your itinerary as a PDF or easily share
            your travel plan with others.
        </p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
<div class="section" id="how-it-works">
    <div class="section-title">
        How it works
    </div>
    <div class="section-subtitle">
        Plan your next adventure in just a few simple steps.
    </div>
</div>
""", unsafe_allow_html=True)

    s1, s2, s3, s4 = st.columns(4)
    steps = [
        ("1", "Choose a destination", "Tell us where you want to go."),
        ("2", "Set your preferences", "Add your dates, budget, travelers, and interests."),
        ("3", "Generate your plan", "Let AI build your personalized itinerary."),
        ("4", "Travel with confidence", "Use your plan, check insights, and enjoy your trip."),
    ]

    for col, (number, title, description) in zip([s1, s2, s3, s4], steps):
        with col:
            st.markdown(f"""
        <div class="step-card">
            <div class="step-number">{number}</div>
            <h3>{title}</h3>
            <p>{description}</p>
        </div>
        """, unsafe_allow_html=True)

    with st.container(border=True, key="highlight_box"):
        st.markdown("""
<div class="highlight-inner">
    <h2>
        Ready to plan your next adventure?
    </h2>
    <p>
        Let AI handle the planning while you focus on
        experiencing the journey.
    </p>
</div>
""", unsafe_allow_html=True)

        cta_btn_cols = st.columns([2, 1, 2])
        with cta_btn_cols[1]:
            if st.button("Plan My Trip ✈️", key="cta_bottom", type="primary", use_container_width=True):
                if st.session_state.get("authentication_status"):
                    st.session_state.view = "planner"
                else:
                    st.session_state.view = "auth"
                st.rerun()

    st.markdown("""
<div class="footer">
    ✈️ PlanMyTrip AI · Plan smarter · Spend wiser · Travel well
    <br><br>
    Built by Maneesha Yerraboina
</div>
""", unsafe_allow_html=True)



# AUTH (LOGIN / SIGN UP)


def render_auth():

    back_cols = st.columns([1, 5])
    with back_cols[0]:
        if st.button("← Back to Home", key="auth_back"):
            st.session_state.view = "landing"
            st.rerun()

    st.markdown(
        '<div class="tw-hero">'
        '<h1>✈️ PlanMyTrip <span class="hero-ai">AI</span></h1>'
        '<p>Log in or create an account to start planning</p>'
        '</div>',
        unsafe_allow_html=True,
    )

    auth_cols = st.columns([1, 2, 1])
    with auth_cols[1]:

        with st.container(border=True, key="auth_card"):

            tab_login, tab_signup = st.tabs(["Log In", "Sign Up"])

            with tab_login:
                try:
                    authenticator.login(
                        location="main",
                        key="login_widget",
                        fields={"Username": "Email", "Password": "Password", "Login": "Log In"},
                    )
                except Exception as exc:
                    st.error(f"Login error: {exc}")

                status = st.session_state.get("authentication_status")

                if status is True:
                    st.session_state.view = "planner"
                    st.rerun()
                elif status is False:
                    st.error("Username or password is incorrect.")
                elif status is None:
                    st.caption("Enter your username and password to log in.")

                st.markdown(
                    '<div class="auth-footnote">'
                    'By continuing, you agree to PlanMyTrip AI\'s Terms of Service '
                    'and Privacy Policy.'
                    '</div>',
                    unsafe_allow_html=True,
                )

            with tab_signup:
                agree = st.checkbox(
                    "I agree to the Terms of Service and Privacy Policy",
                    key="signup_agree",
                )

                if agree:
                    try:
                        email, username, name = authenticator.register_user(
                            location="main",
                            captcha=False,
                            merge_username_email=True,
                            key="signup_widget",
                        )
                        if email:
                            save_auth_config(auth_config)
                            st.success("Account created! Switch to the Log In tab to sign in.")
                    except Exception as exc:
                        st.error(str(exc))
                else:
                    st.caption("Please agree to the terms above to create an account.")



# PLANNER


def render_planner():

    if not st.session_state.get("authentication_status"):
        st.session_state.view = "auth"
        st.rerun()
        return

    if st.button("← Back to Home", key="planner_back"):
        st.session_state.view = "landing"
        st.rerun()

    display_name = (st.session_state.get("name") or "").strip()
    first_initial = display_name[0].upper() if display_name else "?"

    with st.popover(first_initial, key="profile_popover"):
        st.markdown(f"**{display_name or 'User'}**")
        st.divider()
        authenticator.logout("Logout", "main", key="logout_widget")

    if not st.session_state.get("authentication_status"):
        st.session_state.view = "landing"
        st.rerun()
        return


    st.markdown(
        '<div class="tw-hero">'
        '<h1>✈️ PlanMyTrip <span class="hero-ai">AI</span></h1>'
        '<p>PLAN SMARTER · SPEND WISER · TRAVEL WELL</p>'
        '</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="tw-section-label">Choose where you want to travel</div>',
        unsafe_allow_html=True,
    )

    destination_type = st.radio(
        "Destination type",
        ["India", "International"],
        index=(0 if st.session_state.destination_type == "India" else 1),
        horizontal=True,
        label_visibility="collapsed",
        key="destination_type_selector",
    )

    if destination_type != st.session_state.destination_type:
        st.session_state.destination_type = destination_type
        st.session_state.picked_destination = ""
        st.rerun()

    destination_list = DESTINATIONS.get(destination_type, [])

    selected_destination = st.selectbox(
        "Select destination",
        ["Select a destination"] + destination_list,
        index=(
            0
            if st.session_state.picked_destination not in destination_list
            else destination_list.index(st.session_state.picked_destination) + 1
        ),
        key="destination_selector",
    )

    if selected_destination != "Select a destination":
        st.session_state.picked_destination = selected_destination

    st.markdown(
        '<div class="tw-section-label">Your route</div>',
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns([5, 1, 5])

    with c1:
        origin = st.text_input("From", placeholder="e.g. Hyderabad")

    with c2:
        st.markdown('<div class="route-arrow">→</div>', unsafe_allow_html=True)

    with c3:
        dest = st.text_input(
            "To",
            value=st.session_state.picked_destination,
            placeholder="e.g. Goa",
        )
        st.session_state.picked_destination = dest

    st.markdown(
        '<div class="tw-section-label">Trip details</div>',
        unsafe_allow_html=True,
    )

    left, right = st.columns(2)

    with left:
        duration = st.number_input("Duration (days)", min_value=1, max_value=30, value=4, step=1)

        today = datetime.date.today()
        start_date = st.date_input(
            "Start date",
            value=today + datetime.timedelta(days=7),
            min_value=today,
        )
        end_date = start_date + datetime.timedelta(days=duration)
        st.caption(f"Ends: {end_date.strftime('%d %b %Y')}")

        travelers = st.number_input("Travelers", min_value=1, max_value=20, value=2, step=1)

    with right:
        currency = st.selectbox("Currency", ["INR ₹", "USD $", "EUR €", "GBP £"])
        curr_code = currency.split()[0]

        amount = st.text_input("Total budget", placeholder="e.g. 25000")

        st.markdown(
            '<div class="tw-interest-label"><span>❤️</span> What are you interested in?</div>',
            unsafe_allow_html=True,
        )

        interests = st.multiselect(
            "Select your interests",
            [
                "History & culture", "Food", "Nature", "Nightlife", "Shopping",
                "Adventure", "Relaxation", "Photography", "Family-friendly",
            ],
            default=["Food", "History & culture"],
            label_visibility="collapsed",
        )

    notes = st.text_area(
        "Anything else? (dietary needs, mobility, pace preference...)",
        height=70,
    )

    if dest and len(dest.strip()) > 1:

        wcol, icol = st.columns(2)

        with wcol:
            weather = get_weather(dest)
            if weather:
                render_weather_card(weather)
            else:
                st.info("Weather information is currently unavailable for this destination.")

        with icol:
            with st.expander(
                "🔎 Local insights (AI-generated from live search)",
                expanded=False,
            ):
                st.caption(
                    "Generated by an AI model from recent web search results. "
                    "Always double-check current advisories."
                )

                if st.button("Get local insights", key="insight_btn"):
                    if not (groq_client and tavily_client):
                        st.error("Needs both GROQ_API_KEY and TAVILY_API_KEY configured.")
                    else:
                        with st.spinner("Researching..."):
                            context = search_web(
                                f"{dest} travel guide etiquette best time to visit 2026"
                            )
                            try:
                                reply = ask_groq(
                                    [{"role": "user", "content": build_local_insight_prompt(dest, context)}],
                                    max_tokens=350,
                                    temperature=0.4,
                                )
                                fields = parse_insight_fields(reply)

                                st.markdown(
                                    f"**Vibe:** {fields.get('VIBE', '—')}\n\n"
                                    f"**Best time:** {fields.get('BEST_TIME', '—')}\n\n"
                                    f"**Customs:** {fields.get('CUSTOMS', '—')}\n\n"
                                    f"**Getting around:** {fields.get('GETTING_AROUND', '—')}\n\n"
                                    f"**Heads up:** {fields.get('HEADS_UP', '—')}"
                                )
                            except Exception as exc:
                                st.error(f"Unable to generate local insights: {exc}")

    tier_key = "lean"
    tier_label = "Budget"

    if amount:
        try:
            amt = float(amount.replace(",", ""))
            per_day = amt / max(duration, 1)
            tier_key, tier_label = budget_tier(per_day, curr_code)

            symbols = {"INR": "₹", "USD": "$", "EUR": "€", "GBP": "£"}
            symbol = symbols.get(curr_code, "")

            if tier_key == "tight":
                st.markdown(
                    f'<div class="tw-budget-warn">⚠️ This budget is quite tight for '
                    f'{duration} day(s) — about {symbol}{per_day:,.0f}/day. '
                    f'The plan will lean heavily on free/cheap options.</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f'<div class="tw-budget-good">✅ {tier_label} tier — '
                    f'roughly {symbol}{per_day:,.0f}/day.</div>',
                    unsafe_allow_html=True,
                )
        except ValueError:
            st.warning("Enter the budget as a plain number.")

    st.markdown("---")

    generate = st.button("✨ Generate My Trip Plan", type="primary", use_container_width=True)

    if generate:
        if not dest:
            st.error("Please enter a destination.")
        elif not amount:
            st.error("Please enter a budget amount.")
        elif not groq_client:
            st.error("GROQ_API_KEY is not configured — add it to .streamlit/secrets.toml.")
        else:
            with st.spinner("Researching and building your itinerary..."):
                web_context = search_web(f"{dest} budget travel guide hotels food transport 2026")
                budget_str = f"{curr_code} {amount}"
                dates_str = (
                    f"{start_date.strftime('%d %b %Y')} to {end_date.strftime('%d %b %Y')}"
                )

                prompt = build_itinerary_prompt(
                    origin, dest, duration, budget_str, tier_label,
                    dates_str, travelers, interests, notes, web_context,
                )

                try:
                    plan = ask_groq(
                        [
                            {
                                "role": "system",
                                "content": (
                                    "You are an expert, honest travel planner "
                                    "who never invents fake precision."
                                ),
                            },
                            {"role": "user", "content": prompt},
                        ],
                        max_tokens=2200,
                    )

                    st.session_state.plan_text = clean_markdown(plan)
                    st.session_state.plan_meta = {
                        "dest": dest,
                        "origin": origin,
                        "days": duration,
                        "travelers": travelers,
                        "budget": budget_str,
                        "dates": dates_str,
                        "currency": curr_code,
                        "amount": amount,
                        "tier": tier_label,
                    }
                    st.session_state.plan_ready = True
                    st.session_state.chat_log = []
                    st.rerun()

                except Exception as exc:
                    st.error(f"Something went wrong generating the plan: {exc}")

    if st.session_state.plan_ready:

        meta = st.session_state.plan_meta
        plan = st.session_state.plan_text

        st.markdown("---")
        st.success(f"Your {meta['days']}-day plan for {meta['dest']} is ready!")

        tab_plan, tab_budget, tab_chat, tab_share = st.tabs(
            ["📋 Itinerary", "📊 Budget Dashboard", "💬 Ask PlanMyTrip", "📤 Save & Share"]
        )

        with tab_plan:
            st.markdown(
                '<div class="tw-section-label">Your itinerary</div>',
                unsafe_allow_html=True,
            )
            st.markdown(clean_markdown(plan).replace("**", "").replace("*", ""))

        with tab_budget:
            try:
                import plotly.graph_objects as go

                total = float(meta["amount"].replace(",", ""))
                splits = {
                    "Stay": 0.32, "Food": 0.24, "Transport": 0.22,
                    "Activities": 0.15, "Misc/shopping": 0.07,
                }
                values = [round(total * pct) for pct in splits.values()]

                fig = go.Figure(data=[go.Pie(
                    labels=list(splits.keys()),
                    values=values,
                    hole=0.45,
                    marker=dict(colors=["#e96f4f", "#f2a35e", "#f4c98d", "#3a2c22", "#c9b8ab"]),
                )])
                fig.update_layout(
                    title=f"Estimated split of {meta['budget']}",
                    paper_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#3a2c22"),
                )
                st.plotly_chart(fig, use_container_width=True)
                st.caption("This is a rough planning estimate, not a quote — actual costs vary.")

                s1, s2, s3 = st.columns(3)
                s1.metric("Days", meta["days"])
                s2.metric("Travelers", meta["travelers"])
                s3.metric("Tier", meta["tier"])

            except Exception:
                st.info("Enter a valid numeric budget to see the chart.")

        with tab_chat:
            st.caption(
                "Ask anything about this specific trip — PlanMyTrip remembers "
                "the plan and your conversation."
            )

            quick_questions = [
                "Is this trip family-friendly?",
                "Suggest cheaper stay options",
                "What should I pack?",
                "How can I save more money?",
            ]

            qcols = st.columns(4)
            for index, question in enumerate(quick_questions):
                with qcols[index]:
                    if st.button(question, key=f"quick_{index}", use_container_width=True):
                        st.session_state.chat_log.append({"role": "user", "content": question})
                        with st.spinner("Thinking..."):
                            try:
                                reply = ask_groq(
                                    [
                                        {
                                            "role": "system",
                                            "content": (
                                                f"You're PlanMyTrip AI's assistant. The traveler is "
                                                f"planning {meta['days']} days in {meta['dest']} "
                                                f"Budget: {meta['budget']}. Full plan:\n{plan[:3000]}\n"
                                                f"Answer concisely and specifically. Use Markdown "
                                                f"when useful. Do not use HTML tags."
                                            ),
                                        },
                                        *st.session_state.chat_log,
                                    ],
                                    max_tokens=500,
                                )
                                st.session_state.chat_log.append(
                                    {"role": "assistant", "content": clean_markdown(reply)}
                                )
                            except Exception as exc:
                                st.error(f"Unable to answer: {exc}")
                        st.rerun()

            for message in st.session_state.chat_log:
                if message["role"] == "user":
                    st.markdown(
                        f'<div class="tw-chat-user">{message["content"]}</div>',
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        f'<div class="tw-chat-ai">🤖 {message["content"]}</div>',
                        unsafe_allow_html=True,
                    )

            user_message = st.chat_input("Ask anything about your trip...")

            if user_message:
                st.session_state.chat_log.append({"role": "user", "content": user_message})
                with st.spinner("Thinking..."):
                    try:
                        reply = ask_groq(
                            [
                                {
                                    "role": "system",
                                    "content": (
                                        f"You're PlanMyTrip AI's assistant for a {meta['days']}-day "
                                        f"trip to {meta['dest']}. Budget {meta['budget']}. "
                                        f"Full plan:\n{plan[:3000]}\nAnswer clearly and concisely. "
                                        f"Use Markdown when useful. Do not use HTML tags."
                                    ),
                                },
                                *st.session_state.chat_log,
                            ],
                            max_tokens=500,
                        )
                        st.session_state.chat_log.append(
                            {"role": "assistant", "content": clean_markdown(reply)}
                        )
                    except Exception as exc:
                        st.error(f"Unable to answer: {exc}")
                st.rerun()

            if st.button("Clear conversation", key="clear_chat"):
                st.session_state.chat_log = []
                st.rerun()

        with tab_share:
            col_a, col_b = st.columns(2)

            with col_a:
                try:
                    pdf_bytes = make_pdf(
                        f"{meta['days']}-day trip to {meta['dest']}",
                        meta["dest"],
                        meta,
                        plan,
                    )
                    safe_dest = re.sub(r"[^A-Za-z0-9_-]+", "_", meta["dest"]).strip("_")

                    st.download_button(
                        "📄 Download PDF",
                        data=pdf_bytes,
                        file_name=f"PlanMyTrip_{safe_dest}.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                        key="download_trip_pdf",
                    )
                except Exception as exc:
                    st.error(f"Unable to create PDF: {exc}")

            with col_b:
                share_text = (
                    f"My {meta['days']}-day trip to {meta['dest']}! "
                    f"Budget: {meta['budget']}.\n\n{plan[:500]}..."
                )
                wa_link = "https://wa.me/?text=" + urllib.parse.quote(share_text)
                st.link_button("📱 Share on WhatsApp", wa_link, use_container_width=True)

            st.markdown("---")
            dest_enc = urllib.parse.quote(meta["dest"])
            st.markdown(
                '<div class="tw-section-label">Book your journey</div>',
                unsafe_allow_html=True,
            )

            book_links = [
                ("✈️ Skyscanner", "https://www.skyscanner.co.in/"),
                ("🚂 IRCTC", "https://www.irctc.co.in/nget/train-search"),
                ("🚌 RedBus", "https://www.redbus.in/"),
                ("🏨 Booking.com", "https://www.booking.com/"),
            ]

            bcols = st.columns(4)
            for col, (label, url) in zip(bcols, book_links):
                with col:
                    st.link_button(label, url, use_container_width=True)



# ROUTE


if st.session_state.view == "landing":
    render_landing()
elif st.session_state.view == "auth":
    render_auth()
else:
    render_planner()