"""
scraper.py — Fetches economic calendar events from the ForexFactory-compatible
JSON feed at nfs.faireconomy.media and stores them in the local database.

Also handles resolving past predictions when actual values become available.
"""

import json
import logging
import re
from datetime import datetime, timezone
from typing import Optional

import requests

from config import (
    FF_CALENDAR_THIS_WEEK,
    CRYPTO_RELEVANT_KEYWORDS,
    CRYPTO_EXCLUDE_KEYWORDS,
    TARGET_CURRENCIES,
    EVENTS_CACHE_TTL,
)
import database as db

log = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.forexfactory.com/",
}

_SESSION = requests.Session()
_SESSION.headers.update(_HEADERS)


# ─── Fetch ────────────────────────────────────────────────────────────────────

def _fetch_ff_json(url: str) -> list[dict]:
    """Fetch and parse a ForexFactory-compatible JSON calendar endpoint."""
    cache_key = f"ff_json:{url}"
    cached = db.cache_get(cache_key)
    if cached:
        log.debug("Cache hit: %s", url)
        return json.loads(cached)

    try:
        resp = _SESSION.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        db.cache_set(cache_key, json.dumps(data), ttl_seconds=EVENTS_CACHE_TTL)
        log.info("Fetched %d events from %s", len(data), url)
        return data
    except requests.exceptions.RequestException as exc:
        log.error("Failed to fetch %s: %s", url, exc)
        return []
    except Exception as exc:
        log.error("Unexpected error fetching %s: %s", url, exc)
        return []


# ─── Filter ───────────────────────────────────────────────────────────────────

def _is_crypto_relevant(event: dict) -> bool:
    """
    Return True if this event is high-impact USD and crypto-relevant.
    The FF JSON has: country, impact, title fields.
    """
    # Currency filter
    currency = (event.get("country") or event.get("currency") or "").upper()
    if currency not in TARGET_CURRENCIES:
        return False

    # Impact filter — only "High"
    impact = (event.get("impact") or "").strip().lower()
    if impact != "high":
        return False

    # Keyword filter — must match include list AND not match exclude list
    title = (event.get("title") or event.get("name") or "").lower()
    if not any(kw in title for kw in CRYPTO_RELEVANT_KEYWORDS):
        return False
    # Exclude forex-only events that don't move crypto
    if any(kw in title for kw in CRYPTO_EXCLUDE_KEYWORDS):
        return False
    return True


# ─── Parse ────────────────────────────────────────────────────────────────────

def _parse_event(raw: dict) -> Optional[dict]:
    """
    Normalise a raw FF JSON event into our internal schema.
    The FF JSON uses ISO8601 strings in the 'date' field.
    """
    try:
        # Date parsing — FF uses ISO8601 with timezone offset
        date_str = raw.get("date") or raw.get("datetime") or ""
        if not date_str:
            return None

        # Parse and convert to UTC ISO8601
        try:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except ValueError:
            # Try stripping timezone if parsing fails
            dt = datetime.strptime(date_str[:19], "%Y-%m-%dT%H:%M:%S")
            dt = dt.replace(tzinfo=timezone.utc)

        dt_utc = dt.astimezone(timezone.utc)
        event_date_iso = dt_utc.isoformat()

        title = (raw.get("title") or raw.get("name") or "").strip()
        if not title:
            return None

        return {
            "event_name": title,
            "event_date": event_date_iso,
            "currency":   (raw.get("country") or raw.get("currency") or "USD").upper(),
            "impact":     (raw.get("impact") or "High").capitalize(),
            "forecast":   _clean_value(raw.get("forecast")),
            "previous":   _clean_value(raw.get("previous")),
            "actual":     _clean_value(raw.get("actual")),
            "detail_url": raw.get("url"),
        }
    except Exception as exc:
        log.warning("Failed to parse event %s: %s", raw, exc)
        return None


def _clean_value(val) -> Optional[str]:
    """Normalise forecast/actual/previous strings."""
    if val is None:
        return None
    s = str(val).strip()
    if s in ("", "null", "None", "N/A", "-"):
        return None
    return s


# ─── Store & sync ─────────────────────────────────────────────────────────────

def _store_events(events: list[dict]) -> None:
    """Upsert events and also store resolved actuals as historical results."""
    for ev in events:
        db.upsert_event(ev)

        # If this event has an actual value, store it as a historical result
        if ev.get("actual"):
            hist = {
                "event_name":   ev["event_name"],
                "release_date": ev["event_date"][:10],  # date part only
                "actual":       ev["actual"],
                "forecast":     ev.get("forecast"),
                "previous":     ev.get("previous"),
                "source":       "ff",
            }
            db.upsert_historical(hist)


def _resolve_predictions(events: list[dict]) -> None:
    """
    For any event that now has an actual value, check if we predicted it
    and mark the prediction correct/incorrect.
    """
    for ev in events:
        actual = ev.get("actual")
        forecast = ev.get("forecast")
        if not actual or not forecast:
            continue

        pred = db.get_prediction(ev["event_name"], ev["event_date"])
        if not pred or pred.get("was_correct") is not None:
            continue  # No prediction or already resolved

        # Determine what actually happened vs forecast
        actual_direction = _compare_values(actual, forecast)
        if actual_direction is None:
            continue

        was_correct = pred["direction"] == actual_direction
        db.resolve_prediction(
            event_name=ev["event_name"],
            event_date=ev["event_date"],
            actual_value=actual,
            was_correct=was_correct,
        )
        log.info(
            "Resolved prediction for '%s' on %s — predicted: %s, actual direction: %s → %s",
            ev["event_name"],
            ev["event_date"][:10],
            pred["direction"],
            actual_direction,
            "✓ CORRECT" if was_correct else "✗ WRONG",
        )


def _compare_values(actual: str, forecast: str) -> Optional[str]:
    """
    Parse numeric strings and return 'greater', 'less', or 'equal'.
    Returns None if either value can't be parsed.
    """
    try:
        a = _parse_number(actual)
        f = _parse_number(forecast)
        if a is None or f is None:
            return None
        if abs(a - f) < 0.001:
            return "equal"
        return "greater" if a > f else "less"
    except Exception:
        return None


def _parse_number(s: str) -> Optional[float]:
    """Strip units (%, K, M, B) and parse to float."""
    if not s:
        return None
    s = str(s).strip().replace(",", "")
    # Handle K / M / B suffixes
    multipliers = {"K": 1e3, "M": 1e6, "B": 1e9, "T": 1e12}
    for suffix, mult in multipliers.items():
        if s.upper().endswith(suffix):
            try:
                return float(s[:-1]) * mult
            except ValueError:
                return None
    # Strip non-numeric except . and -
    cleaned = re.sub(r"[^0-9.\-]", "", s)
    try:
        return float(cleaned) if cleaned else None
    except ValueError:
        return None


# ─── Public API ───────────────────────────────────────────────────────────────

def refresh_calendar() -> list[dict]:
    """
    Main entry point: fetch current + next week events, filter, store, resolve.
    Returns list of upcoming crypto-relevant events.
    """
    # Only thisweek.json is a valid endpoint
    all_raw = _fetch_ff_json(FF_CALENDAR_THIS_WEEK)

    # Filter
    relevant = [e for e in all_raw if _is_crypto_relevant(e)]
    log.info("Found %d crypto-relevant high-impact USD events", len(relevant))

    # Parse
    parsed = [_parse_event(r) for r in relevant]
    parsed = [e for e in parsed if e is not None]

    # Store
    _store_events(parsed)

    # Resolve any pending predictions where actuals are now available
    _resolve_predictions(parsed)

    # Return upcoming events from DB (includes any previously stored)
    return db.get_upcoming_events(limit=30)


def get_cached_events() -> list[dict]:
    """Return events from DB without re-fetching (used for fast UI loads)."""
    return db.get_upcoming_events(limit=30)
