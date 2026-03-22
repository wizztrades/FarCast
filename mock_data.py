"""
mock_data.py — Realistic demo data for when API keys are not yet configured.
Lets first-time users on fluxcloud see the full UI before adding their own keys.
All values are representative of a typical calendar week (not real-time).
"""

from datetime import datetime, timezone, timedelta

_NOW = datetime.now(timezone.utc)

def _dt(hours_from_now: float) -> str:
    return (_NOW + timedelta(hours=hours_from_now)).isoformat()


MOCK_EVENTS = [
    {
        "id": 1,
        "event_name": "Initial Jobless Claims",
        "event_date": _dt(2),
        "currency": "USD",
        "impact": "High",
        "forecast": "215K",
        "previous": "223K",
        "actual": None,
        "detail_url": None,
        "scraped_at": _NOW.isoformat(),
    },
    {
        "id": 2,
        "event_name": "Non-Farm Payrolls",
        "event_date": _dt(26),
        "currency": "USD",
        "impact": "High",
        "forecast": "185K",
        "previous": "143K",
        "actual": None,
        "detail_url": None,
        "scraped_at": _NOW.isoformat(),
    },
    {
        "id": 3,
        "event_name": "Unemployment Rate",
        "event_date": _dt(26.5),
        "currency": "USD",
        "impact": "High",
        "forecast": "4.1%",
        "previous": "4.0%",
        "actual": None,
        "detail_url": None,
        "scraped_at": _NOW.isoformat(),
    },
    {
        "id": 4,
        "event_name": "CPI m/m",
        "event_date": _dt(98),
        "currency": "USD",
        "impact": "High",
        "forecast": "0.3%",
        "previous": "0.2%",
        "actual": None,
        "detail_url": None,
        "scraped_at": _NOW.isoformat(),
    },
    {
        "id": 5,
        "event_name": "Core CPI m/m",
        "event_date": _dt(98.5),
        "currency": "USD",
        "impact": "High",
        "forecast": "0.3%",
        "previous": "0.4%",
        "actual": None,
        "detail_url": None,
        "scraped_at": _NOW.isoformat(),
    },
    {
        "id": 6,
        "event_name": "FOMC Statement",
        "event_date": _dt(170),
        "currency": "USD",
        "impact": "High",
        "forecast": "4.25%-4.50%",
        "previous": "4.25%-4.50%",
        "actual": None,
        "detail_url": None,
        "scraped_at": _NOW.isoformat(),
    },
    {
        "id": 7,
        "event_name": "Core PCE Price Index m/m",
        "event_date": _dt(194),
        "currency": "USD",
        "impact": "High",
        "forecast": "0.3%",
        "previous": "0.3%",
        "actual": None,
        "detail_url": None,
        "scraped_at": _NOW.isoformat(),
    },
    {
        "id": 8,
        "event_name": "Retail Sales m/m",
        "event_date": _dt(-36),     # past event with actual
        "currency": "USD",
        "impact": "High",
        "forecast": "0.4%",
        "previous": "-0.9%",
        "actual": "0.2%",
        "detail_url": None,
        "scraped_at": _NOW.isoformat(),
    },
    {
        "id": 9,
        "event_name": "ISM Manufacturing PMI",
        "event_date": _dt(-60),
        "currency": "USD",
        "impact": "High",
        "forecast": "49.5",
        "previous": "50.3",
        "actual": "49.0",
        "detail_url": None,
        "scraped_at": _NOW.isoformat(),
    },
]


MOCK_PREDICTIONS = {
    "Initial Jobless Claims": {
        "direction": "less",
        "confidence": 62,
        "crypto_impact": "bullish",
        "economic_analysis": (
            "The US labor market remains resilient with the Fed holding rates at 4.25-4.50%. "
            "Continuing claims have been rising modestly, suggesting some softening at the margins. "
            "Initial claims tend to be a leading indicator and recent weeks have shown mean-reversion "
            "from an elevated print in the prior week."
        ),
        "historical_pattern": (
            "Over the past 10 releases, jobless claims have beaten (come in below) consensus 6 times. "
            "The series shows high week-to-week volatility, with a typical beat/miss range of ±15K. "
            "Spring seasonal adjustments tend to reduce claims temporarily."
        ),
        "reasoning": (
            "The prior week's 223K print was elevated relative to the recent 4-week moving average of ~210K, "
            "suggesting mean reversion is likely. A print below the 215K consensus would signal continued "
            "labor market resilience. Given the current rate-hold environment, fewer claims = lower rate cut "
            "expectations, but the crypto market has been pricing in a risk-on regime regardless."
        ),
        "risk_factors": (
            "Upside surprise in claims (above 230K) would trigger risk-off sentiment and could weigh on "
            "crypto if it coincides with other weak data."
        ),
        "learning_notes": "No past mistakes to correct for this event type — first prediction cycle.",
        "was_correct": None,
    },
    "Non-Farm Payrolls": {
        "direction": "less",
        "confidence": 58,
        "crypto_impact": "bullish",
        "economic_analysis": (
            "The US labor market is in a gradual cooling phase. The Fed has been signaling it needs to see "
            "further softening before cutting rates. Recent ADP data came in at 155K vs 170K expected, "
            "suggesting private payrolls are decelerating. Government hiring has been volatile."
        ),
        "historical_pattern": (
            "NFP has missed consensus in 6 of the last 10 releases when prior month was below 200K. "
            "First-Friday releases in Q1/Q2 historically show downside surprises due to weather-related "
            "seasonal adjustments. Revisions to prior months have been consistently downward."
        ),
        "reasoning": (
            "With ADP missing and the prior month's 143K print well below trend, the probability of a "
            "rebound to 185K appears low. Cooling labor conditions support a miss. Importantly, a miss "
            "here would increase rate cut expectations for the June FOMC — which is historically bullish "
            "for Bitcoin and risk assets as liquidity expectations improve."
        ),
        "risk_factors": (
            "Government payrolls are unpredictable and could boost the headline. A significant beat above "
            "220K would delay rate cuts and trigger risk-off, potentially bearish for crypto."
        ),
        "learning_notes": (
            "Previously over-weighted ADP as a signal. Adjusted to give more weight to the "
            "BLS birth-death model adjustment which tends to add ~30K to spring prints."
        ),
        "was_correct": None,
    },
    "Unemployment Rate": {
        "direction": "equal",
        "confidence": 55,
        "crypto_impact": "neutral",
        "economic_analysis": (
            "The unemployment rate has been sticky around 4.0-4.1% for the past several months, "
            "reflecting a balanced labor market. The Fed considers 4.2% the approximate neutral rate. "
            "The participation rate has been gradually recovering which keeps the headline stable."
        ),
        "historical_pattern": (
            "Unemployment rate tends to move in 0.1% increments and rarely surprises significantly. "
            "In 7 of the last 10 releases it has either met or been within 0.1% of consensus. "
            "Stability in this metric reduces market reaction risk."
        ),
        "reasoning": (
            "The unemployment rate is expected at 4.1% and is likely to print exactly at or within "
            "0.1% of that figure given current labor market dynamics. A stable unemployment rate "
            "alongside a weak NFP print would be a mixed signal — not enough to be strongly bullish "
            "or bearish for crypto, hence neutral impact expected."
        ),
        "risk_factors": (
            "A jump to 4.3%+ would be a significant shock and trigger immediate rate-cut bets, "
            "potentially sharply bullish for crypto."
        ),
        "learning_notes": "No past mistakes to correct — first prediction for this event.",
        "was_correct": None,
    },
    "CPI m/m": {
        "direction": "equal",
        "confidence": 52,
        "crypto_impact": "bullish",
        "economic_analysis": (
            "US inflation has been on a slow but steady downward trend, currently near 2.5-2.8% YoY. "
            "The Fed's 2% target remains elusive but the direction is correct. Energy prices have been "
            "volatile and shelter costs (the stickiest component) are still elevated."
        ),
        "historical_pattern": (
            "CPI m/m has met consensus exactly in 4 of the last 10 releases. "
            "Misses and beats are roughly equal at 3 each, indicating high forecast uncertainty. "
            "Core CPI has been a better predictor of headline in recent months."
        ),
        "reasoning": (
            "With energy prices relatively stable and shelter costs showing early signs of cooling, "
            "the 0.3% consensus appears well-calibrated. An in-line print would be mildly bullish for "
            "crypto as it keeps the Fed on a gradual easing path without creating alarm. "
            "Markets are already pricing in 2 cuts for 2025, so a stable CPI validates that narrative."
        ),
        "risk_factors": (
            "A hot print above 0.4% would reignite inflation fears and trigger risk-off across all "
            "markets including crypto. Tariff pass-through effects remain an upside risk."
        ),
        "learning_notes": "No past mistakes to correct — first prediction for this event.",
        "was_correct": None,
    },
    "FOMC Statement": {
        "direction": "equal",
        "confidence": 85,
        "crypto_impact": "neutral",
        "economic_analysis": (
            "The Fed is widely expected to hold rates at 4.25-4.50% at this meeting with near-100% "
            "market probability. The committee has been in a data-dependent holding pattern since "
            "late 2024. The key market mover will be the statement language and Powell's press conference "
            "tone regarding future cuts."
        ),
        "historical_pattern": (
            "The Fed has held rates unchanged for 3 consecutive meetings. In all cases where hold "
            "probability exceeded 95% heading into the meeting, the actual decision matched. "
            "Market impact depends almost entirely on dot plot revisions and forward guidance."
        ),
        "reasoning": (
            "Rate hold is essentially certain (the 'equal' prediction here refers to rate level meeting "
            "the forecast of no change). The crypto impact will be determined by Powell's tone — if he "
            "opens the door to a June cut, that would be bullish. If he emphasizes data-dependence and "
            "inflation stickiness, neutral to slightly bearish. Base case: neutral crypto impact."
        ),
        "risk_factors": (
            "Any surprise dot plot revision removing expected 2025 cuts would be sharply bearish for "
            "risk assets including crypto."
        ),
        "learning_notes": "No past mistakes to correct — first prediction for this event.",
        "was_correct": None,
    },
    "Core PCE Price Index m/m": {
        "direction": "less",
        "confidence": 60,
        "crypto_impact": "bullish",
        "economic_analysis": (
            "Core PCE is the Fed's preferred inflation measure and has been gradually moderating. "
            "The super-core (services ex-housing) component has been the main sticking point. "
            "Recent PPI data, which feeds into PCE, came in softer than expected."
        ),
        "historical_pattern": (
            "Core PCE tends to track slightly below CPI. In the last 6 months where CPI has been "
            "at or below consensus, Core PCE has undershot in 4 cases. "
            "The index rarely surprises dramatically due to its methodological smoothing."
        ),
        "reasoning": (
            "With upstream PPI data softer and services inflation finally showing moderation, "
            "Core PCE is likely to print at or slightly below the 0.3% consensus. "
            "A below-consensus print is the most directly bullish data point for crypto as it "
            "directly advances the Fed toward its 2% target and supports rate cut expectations."
        ),
        "risk_factors": (
            "Healthcare costs and portfolio management fees (which feed into PCE but not CPI) "
            "could push the number above consensus unexpectedly."
        ),
        "learning_notes": "No past mistakes to correct — first prediction for this event.",
        "was_correct": None,
    },
}


MOCK_HISTORICAL = {
    "Initial Jobless Claims": [
        {"release_date": "2026-03-13", "actual": "223K", "forecast": "225K", "previous": "221K"},
        {"release_date": "2026-03-06", "actual": "221K", "forecast": "218K", "previous": "215K"},
        {"release_date": "2026-02-27", "actual": "215K", "forecast": "220K", "previous": "219K"},
        {"release_date": "2026-02-20", "actual": "219K", "forecast": "216K", "previous": "213K"},
        {"release_date": "2026-02-13", "actual": "213K", "forecast": "215K", "previous": "210K"},
        {"release_date": "2026-02-06", "actual": "210K", "forecast": "208K", "previous": "207K"},
        {"release_date": "2026-01-30", "actual": "207K", "forecast": "210K", "previous": "211K"},
        {"release_date": "2026-01-23", "actual": "211K", "forecast": "220K", "previous": "216K"},
        {"release_date": "2026-01-16", "actual": "216K", "forecast": "214K", "previous": "218K"},
        {"release_date": "2026-01-09", "actual": "218K", "forecast": "215K", "previous": "201K"},
    ],
    "Non-Farm Payrolls": [
        {"release_date": "2026-03-06", "actual": "143K", "forecast": "170K", "previous": "256K"},
        {"release_date": "2026-02-07", "actual": "256K", "forecast": "175K", "previous": "307K"},
        {"release_date": "2026-01-10", "actual": "307K", "forecast": "154K", "previous": "212K"},
        {"release_date": "2025-12-06", "actual": "212K", "forecast": "195K", "previous": "36K"},
        {"release_date": "2025-11-01", "actual": "36K",  "forecast": "115K", "previous": "233K"},
        {"release_date": "2025-10-04", "actual": "233K", "forecast": "150K", "previous": "78K"},
        {"release_date": "2025-09-06", "actual": "78K",  "forecast": "160K", "previous": "114K"},
        {"release_date": "2025-08-01", "actual": "114K", "forecast": "175K", "previous": "179K"},
        {"release_date": "2025-07-05", "actual": "179K", "forecast": "185K", "previous": "218K"},
        {"release_date": "2025-06-06", "actual": "218K", "forecast": "190K", "previous": "165K"},
    ],
    "CPI m/m": [
        {"release_date": "2026-03-12", "actual": "0.2%", "forecast": "0.3%", "previous": "0.5%"},
        {"release_date": "2026-02-12", "actual": "0.5%", "forecast": "0.3%", "previous": "0.4%"},
        {"release_date": "2026-01-15", "actual": "0.4%", "forecast": "0.3%", "previous": "0.3%"},
        {"release_date": "2025-12-11", "actual": "0.3%", "forecast": "0.3%", "previous": "0.2%"},
        {"release_date": "2025-11-13", "actual": "0.2%", "forecast": "0.2%", "previous": "0.2%"},
        {"release_date": "2025-10-10", "actual": "0.2%", "forecast": "0.1%", "previous": "0.3%"},
        {"release_date": "2025-09-11", "actual": "0.3%", "forecast": "0.2%", "previous": "0.2%"},
        {"release_date": "2025-08-13", "actual": "0.2%", "forecast": "0.2%", "previous": "0.1%"},
        {"release_date": "2025-07-11", "actual": "0.1%", "forecast": "0.2%", "previous": "0.2%"},
        {"release_date": "2025-06-11", "actual": "0.2%", "forecast": "0.3%", "previous": "0.4%"},
    ],
    "FOMC Statement": [
        {"release_date": "2026-01-29", "actual": "4.25%-4.50%", "forecast": "4.25%-4.50%", "previous": "4.25%-4.50%"},
        {"release_date": "2025-12-18", "actual": "4.25%-4.50%", "forecast": "4.25%-4.50%", "previous": "4.50%-4.75%"},
        {"release_date": "2025-11-07", "actual": "4.50%-4.75%", "forecast": "4.50%-4.75%", "previous": "4.75%-5.00%"},
        {"release_date": "2025-09-18", "actual": "4.75%-5.00%", "forecast": "5.00%-5.25%", "previous": "5.25%-5.50%"},
        {"release_date": "2025-07-30", "actual": "5.25%-5.50%", "forecast": "5.25%-5.50%", "previous": "5.25%-5.50%"},
    ],
}


def get_mock_events() -> list[dict]:
    return MOCK_EVENTS


def get_mock_prediction(event_name: str) -> dict | None:
    for key, pred in MOCK_PREDICTIONS.items():
        if key.lower() in event_name.lower() or event_name.lower() in key.lower():
            return {**pred, "event_name": event_name, "event_date": "", "raw_response": None}
    return None


def get_mock_historical(event_name: str) -> list[dict]:
    for key, hist in MOCK_HISTORICAL.items():
        if key.lower() in event_name.lower() or event_name.lower() in key.lower():
            return hist
    return []
