"""
fred_client.py — Free FRED API client (St. Louis Fed).
Fetches macroeconomic context and seeds historical event data.
API key required but 100% free: https://fred.stlouisfed.org/docs/api/api_key.html
"""

import logging
import json
import requests
from datetime import datetime, timedelta, timezone
from typing import Optional

from config import FRED_API_KEY, FRED_BASE_URL, CONTEXT_FRED_SERIES, FRED_SERIES_MAP
import database as db

log = logging.getLogger(__name__)

_SESSION = requests.Session()
_SESSION.headers.update({"Accept": "application/json"})


def _fetch_series(series_id: str, limit: int = 12) -> list[dict]:
    """
    Fetch the latest N observations for a FRED series.
    Returns list of {date, value} dicts, newest first.
    """
    if not FRED_API_KEY:
        log.warning("FRED_API_KEY not set — skipping FRED fetch")
        return []

    cache_key = f"fred:{series_id}:{limit}"
    cached = db.cache_get(cache_key)
    if cached:
        return json.loads(cached)

    try:
        resp = _SESSION.get(
            FRED_BASE_URL,
            params={
                "series_id":   series_id,
                "api_key":     FRED_API_KEY,
                "file_type":   "json",
                "sort_order":  "desc",
                "limit":       limit,
                "observation_start": (datetime.now() - timedelta(days=730)).strftime("%Y-%m-%d"),
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        observations = [
            {"date": o["date"], "value": o["value"]}
            for o in data.get("observations", [])
            if o.get("value") not in (".", None, "")
        ]
        db.cache_set(cache_key, json.dumps(observations), ttl_seconds=43200)
        return observations
    except Exception as exc:
        log.error("FRED fetch failed for %s: %s", series_id, exc)
        return []


def get_economic_context() -> dict:
    """
    Build a concise snapshot of the current US macroeconomic situation.
    Returns a dict of indicator name → latest value (string).
    """
    context = {}
    for key, (series_id, label) in CONTEXT_FRED_SERIES.items():
        obs = _fetch_series(series_id, limit=3)
        if obs:
            # Latest value
            latest = obs[0]
            prev   = obs[1] if len(obs) > 1 else None
            val_str = f"{latest['value']}%"
            if prev:
                try:
                    change = float(latest["value"]) - float(prev["value"])
                    direction = "▲" if change > 0 else "▼" if change < 0 else "→"
                    val_str += f" ({direction}{abs(change):.2f} vs prev)"
                except ValueError:
                    pass
            context[label] = {
                "value": latest["value"],
                "date":  latest["date"],
                "display": val_str,
            }
    return context


def get_context_summary_text() -> str:
    """
    Return a human-readable paragraph of current US economic conditions.
    Used directly in the Groq prediction prompt.
    """
    ctx = get_economic_context()
    if not ctx:
        return "FRED economic context unavailable (no API key configured)."

    lines = []
    for label, info in ctx.items():
        lines.append(f"• {label}: {info['display']} (as of {info['date']})")
    return "Current US Macroeconomic Snapshot:\n" + "\n".join(lines)


def seed_historical_for_event(event_name: str) -> int:
    """
    Seed historical_results table with FRED data for a known event type.
    Returns count of records inserted.
    """
    # Find the best matching FRED series
    series_id = None
    for name, sid in FRED_SERIES_MAP.items():
        if any(word.lower() in event_name.lower() for word in name.split()):
            series_id = sid
            break

    if not series_id:
        return 0

    observations = _fetch_series(series_id, limit=12)
    inserted = 0
    for i, obs in enumerate(observations):
        # Use next obs as "previous" value
        previous = observations[i + 1]["value"] if i + 1 < len(observations) else None
        record = {
            "event_name":   event_name,
            "release_date": obs["date"],
            "actual":       obs["value"],
            "forecast":     None,  # FRED doesn't provide forecasts
            "previous":     previous,
            "source":       "fred",
        }
        db.upsert_historical(record)
        inserted += 1
    return inserted


def seed_all_known_events() -> None:
    """
    Pre-seed historical data for all known event types.
    Called once at startup to ensure past data is available from day 1.
    """
    if not FRED_API_KEY:
        return
    for event_name in FRED_SERIES_MAP:
        count = seed_historical_for_event(event_name)
        if count:
            log.info("Seeded %d historical records for '%s'", count, event_name)
