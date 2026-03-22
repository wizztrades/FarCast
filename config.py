"""
config.py — Central configuration for FarCast.
All secrets are loaded from environment variables or Streamlit secrets.
"""

import os

def _get(key: str, default: str = "") -> str:
    try:
        import streamlit as st
        return st.secrets.get(key, os.getenv(key, default))
    except Exception:
        return os.getenv(key, default)


# ─── API Keys ─────────────────────────────────────────────────────────────────
GROQ_API_KEY: str = _get("GROQ_API_KEY")
FRED_API_KEY: str = _get("FRED_API_KEY")

# ─── Database ─────────────────────────────────────────────────────────────────
DATABASE_PATH: str = _get("DATABASE_PATH", "calendar.db")

# ─── Groq Model ───────────────────────────────────────────────────────────────
GROQ_MODEL: str = "llama-3.3-70b-versatile"
GROQ_MAX_TOKENS: int = 1500
GROQ_TEMPERATURE: float = 0.3

# ─── Calendar Data Source ─────────────────────────────────────────────────────
# Only thisweek.json is a valid endpoint — last/nextweek return 404
FF_CALENDAR_THIS_WEEK = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"

FRED_BASE_URL = "https://api.stlouisfed.org/fred/series/observations"

# ─── Cache TTL (seconds) ──────────────────────────────────────────────────────
EVENTS_CACHE_TTL: int = 1800
PREDICTION_CACHE_TTL: int = 21600
FRED_CACHE_TTL: int = 43200

# ─── Event Filter ─────────────────────────────────────────────────────────────
TARGET_CURRENCIES = {"USD"}

# ── Crypto-specific events ONLY ───────────────────────────────────────────────
# Verified against CryptoCraft and Investing.com crypto calendar.
# Rule: only events that directly move Fed rate expectations or macro liquidity.
# PMI, housing, trade balance, consumer confidence etc. are FOREX movers, not crypto.
CRYPTO_RELEVANT_KEYWORDS = [
    # Fed policy — biggest crypto movers
    "fomc",
    "federal open market",
    "interest rate decision",
    "rate decision",
    "fed chair",
    "powell",
    "federal reserve chair",
    "fomc minutes",
    "fomc meeting minutes",
    "fomc statement",
    "monetary policy statement",
    # Inflation — directly drives Fed rate path
    "cpi",
    "core cpi",
    "consumer price index",
    "pce price index",
    "core pce",
    "personal consumption expenditures",
    # Labor market — key Fed dual mandate input
    "non-farm payroll",
    "nonfarm payroll",
    "non-farm employment",
    "unemployment rate",
    "initial jobless claims",
    "continuing jobless claims",
    "jolts",
    "job openings",
    # GDP — recession / growth signal
    "gdp",
    "gross domestic product",
]

# Events to EXCLUDE even if they match a keyword above (forex movers, not crypto)
CRYPTO_EXCLUDE_KEYWORDS = [
    "flash manufacturing",
    "flash services",
    "flash composite",
    "manufacturing pmi",
    "services pmi",
    "composite pmi",
    "ism manufacturing",
    "ism services",
    "ism non-manufacturing",
    "consumer confidence",
    "consumer sentiment",
    "michigan sentiment",
    "trade balance",
    "current account",
    "building permits",
    "housing starts",
    "existing home",
    "new home sales",
    "pending home sales",
    "retail sales",
    "durable goods",
    "factory orders",
    "industrial production",
    "capacity utilization",
    "business inventories",
    "wholesale inventories",
    "ppi",
    "producer price",
    "import price",
    "export price",
    "challenger job cuts",
    "empire state",
    "philly fed",
    "chicago pmi",
    "richmond fed",
    "dallas fed",
]

# ─── FRED Series → Event Name Mapping ────────────────────────────────────────
FRED_SERIES_MAP = {
    "Non-Farm Payrolls":        "PAYEMS",
    "Unemployment Rate":        "UNRATE",
    "CPI m/m":                  "CPIAUCSL",
    "Core CPI m/m":             "CPILFESL",
    "CPI y/y":                  "CPIAUCSL",
    "GDP q/q":                  "GDP",
    "Core PCE Price Index":     "PCEPILFE",
    "PCE Price Index":          "PCEPI",
    "Initial Jobless Claims":   "ICSA",
    "Fed Funds Rate":           "FEDFUNDS",
}

# ─── Context FRED Series (for AI economic analysis) ──────────────────────────
CONTEXT_FRED_SERIES = {
    "fed_funds_rate":  ("FEDFUNDS",         "Federal Funds Rate (%)"),
    "cpi_yoy":         ("CPIAUCSL",         "CPI YoY Inflation (%)"),
    "unemployment":    ("UNRATE",           "Unemployment Rate (%)"),
    "gdp_growth":      ("A191RL1Q225SBEA",  "Real GDP Growth Rate (%)"),
    "core_pce":        ("PCEPILFE",         "Core PCE Inflation (%)"),
    "10yr_treasury":   ("DGS10",            "10-Year Treasury Yield (%)"),
    "nfp":             ("PAYEMS",           "Total Nonfarm Payrolls (thousands)"),
}
