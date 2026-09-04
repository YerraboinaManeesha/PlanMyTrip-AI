# ✈️ PlanMyTrip AI

**PlanMyTrip AI** is an AI-powered travel planning application that helps users create personalized travel itineraries based on their destination, travel dates, number of travelers, budget, interests, and preferences.

The application combines **Groq AI**, **Tavily web search**, and **Open-Meteo weather data** to provide practical and personalized travel recommendations.

## 🌐 Live Demo

[PlanMyTrip AI](https://planmytrip-ai.streamlit.app/)


## ✨ Features

* 🔐 User Login & Sign Up
* 🗺️ Personalized Trip Planning
* 🤖 AI-Generated Travel Itineraries
* 🌤️ Weather Information
* 📍 Local Travel Insights
* 💰 Budget Estimation
* 💬 AI Travel Assistant
* 📄 Download Trip Plans as PDF
* 📱 Share Trip Plans via WhatsApp
* 🔗 Useful Travel & Booking Links
* 💵 Multiple Currency Support
* 🎯 Personalized Interests & Preferences

## 🧠 Application Flow

```text
User enters trip details
        ↓
Destination + Dates + Travelers + Budget
        ↓
Interests + Preferences
        ↓
Tavily Web Search + Weather Data
        ↓
Groq AI
        ↓
Personalized Travel Plan
        ↓
Itinerary + Recommendations + Budget
        ↓
PDF / WhatsApp / Travel Links
```

## 🛠️ Tech Stack

| Technology | Purpose                 |
| ---------- | ----------------------- |
| Python     | Core programming        |
| Streamlit  | Web application & UI    |
| Groq       | AI itinerary generation |
| Tavily     | Web search              |
| Open-Meteo | Weather information     |
| Requests   | API requests            |
| PyYAML     | Configuration           |
| FPDF2      | PDF generation          |
| HTML/CSS   | UI styling              |

## 📂 Project Structure

```text
PlanMyTrip-AI/
│
├── app.py
├── style.css
├── config.yaml
├── requirements.txt
├── README.md
│
└── .streamlit/
    └── secrets.toml.example
```

## 🔐 API Keys

Create a `.streamlit/secrets.toml` file and add:

```toml
GROQ_API_KEY = "your_groq_api_key"
TAVILY_API_KEY = "your_tavily_api_key"
```

**Never upload your actual API keys to GitHub.**

## ⚙️ Run Locally

```bash
git clone https://github.com/YerraboinaManeesha/PlanMyTrip-AI.git
cd PlanMyTrip-AI
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

## 🚀 Deployment

The application is deployed using **Streamlit Community Cloud**.

**Live App:**
https://planmytrip-ai.streamlit.app/

## 🎯 Future Improvements

* 🗺️ Interactive maps
* 🏨 Hotel booking integration
* ✈️ Flight information
* 🌦️ Enhanced weather forecasts
* 💱 Live currency conversion
* 🧳 Trip history
* ❤️ Save favorite destinations
* 📱 Improved mobile experience

## 👩‍💻 Author

**Maneesha Yerraboina**

MSc Computer Science Graduate | Aspiring Web Developer
