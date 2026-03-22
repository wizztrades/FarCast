# 📊 FarCast — Crypto Economic Calendar

An AI-powered economic calendar for crypto traders that predicts the outcome of high-impact US economic events **before they release** — with full reasoning, confidence levels, and crypto market impact assessment.

---

## ✨ Features

| Feature | Details |
|---|---|
| **Smart Filtering** | Shows only high-impact USD events relevant to crypto (NFP, CPI, FOMC, GDP, PCE, etc.) |
| **AI Predictions** | Direction vs forecast (↑ Greater / ↓ Less / → Equal) + Crypto impact (Bullish/Bearish/Neutral) |
| **Confidence Score** | 0–100% confidence with honest uncertainty |
| **Full Reasoning** | Economic analysis, historical pattern analysis, main reasoning, risk factors |
| **Learning Loop** | Tracks every prediction outcome — future predictions for the same event type are informed by past mistakes |
| **Historical Data** | Last 10 releases per event, seeded from FRED on day 1 |
| **Live Data** | Forecast, Previous, and Actual values from ForexFactory's JSON feed |
| **100% Free** | No paid APIs, no paid services |

---

## 🚀 Quick Deploy (fluxcloud.io)

### 1. Fork this repository to your GitHub

### 2. Set up API keys (both free)

**Groq API** (required for AI predictions):
1. Go to [console.groq.com/keys](https://console.groq.com/keys)
2. Create a free account → Generate API key
3. Free tier: 6,000 tokens/min, 500 req/day

**FRED API** (recommended for macro context):
1. Go to [fred.stlouisfed.org/docs/api/api_key.html](https://fred.stlouisfed.org/docs/api/api_key.html)
2. Create a free account → Request API key (instant)
3. Completely free, no limits for reasonable usage

### 3. Deploy on fluxcloud.io

1. Connect your GitHub repo
2. Set environment variables in the fluxcloud dashboard:
   ```
   GROQ_API_KEY=gsk_xxxxxxxxxxxx
   FRED_API_KEY=xxxxxxxxxxxxxxxx
   ```
3. Start command: `streamlit run app.py --server.port=$PORT --server.address=0.0.0.0 --server.headless=true`
4. Done ✅

---

## 🖥️ Local Setup

```bash
# Clone
git clone https://github.com/YOUR_USERNAME/farcast.git
cd farcast

# Install dependencies
pip install -r requirements.txt

# Set up env vars
cp .env.example .env
# Edit .env with your API keys

# Run
streamlit run app.py
```

---

## 🏗️ Architecture

```
farcast/
├── app.py           ← Streamlit UI (main entry point)
├── config.py        ← API keys, constants, FRED series mappings
├── database.py      ← SQLite layer (events, predictions, history, cache)
├── scraper.py       ← ForexFactory JSON feed parser + prediction resolver
├── fred_client.py   ← FRED API client (macro context + historical seeding)
├── predictor.py     ← Groq AI engine with learning feedback loop
├── requirements.txt
├── Procfile         ← For deployment platforms
└── .streamlit/
    └── config.toml  ← Dark theme, Bitcoin orange
```

---

## 🤖 How the AI Works

### Prediction Flow
```
Upcoming Event
    │
    ├── FRED API → Current US macro snapshot (CPI, rates, unemployment, GDP...)
    ├── SQLite   → Last 10 historical results for this event type
    ├── SQLite   → Past prediction accuracy + specific mistakes for this event
    │
    └── Groq llama-3.3-70b
            │
            ├── direction:       greater | less | equal  (actual vs forecast)
            ├── confidence:      0–100%
            ├── crypto_impact:   bullish | bearish | neutral
            ├── economic_analysis
            ├── historical_pattern
            ├── reasoning
            ├── risk_factors
            └── learning_notes   ← active correction from past mistakes
```

### Learning Loop
1. Event releases → actual value scraped from ForexFactory
2. System compares actual direction to predicted direction
3. Prediction marked ✅ correct or ❌ wrong in SQLite
4. Next time same event type is predicted:
   - Accuracy rate fed into prompt
   - Specific wrong predictions + their reasoning included
   - Model explicitly told to correct its patterns

---

## 📈 Supported Events

All high-impact USD events relevant to crypto, including:

- **Labor**: Non-Farm Payrolls, Unemployment Rate, Initial Jobless Claims, JOLTS
- **Inflation**: CPI, Core CPI, PPI, Core PCE, PCE Price Index
- **Fed**: FOMC Rate Decision, Fed Chair Speech, FOMC Minutes
- **Growth**: GDP, Retail Sales, Durable Goods
- **Sentiment**: ISM Manufacturing/Services PMI, Consumer Confidence/Sentiment
- **Trade**: Trade Balance

---

## ⚠️ Disclaimer

This tool provides fundamental analysis as **confluence only**. Economic predictions are inherently uncertain and should never be the sole basis for trading decisions. Past accuracy does not guarantee future results.

---

## 🔑 Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GROQ_API_KEY` | ✅ Yes | Groq API key for AI predictions |
| `FRED_API_KEY` | ⭐ Recommended | FRED API key for macro context |
| `DATABASE_PATH` | ❌ No | SQLite file path (default: `calendar.db`) |
