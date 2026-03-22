"""
predictor.py — Groq-powered prediction engine with learning feedback loop
and adaptive re-prediction based on time proximity and macro context drift.

Re-prediction schedule (hours until event):
  > 72h  : every 24h
  24-72h : every 12h
  6-24h  : every 4h
  1-6h   : every 2h
  < 1h   : every 30min (final window — anything can happen)

Context drift: if any FRED indicator moves by more than its drift threshold
vs the snapshot stored with the last prediction, a re-prediction is forced.
"""

import json
import hashlib
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Optional

from groq import Groq, RateLimitError, APIError

from config import (
    GROQ_API_KEY,
    GROQ_MODEL,
    GROQ_MAX_TOKENS,
    GROQ_TEMPERATURE,
)
import database as db
import fred_client

log = logging.getLogger(__name__)

_client: Optional[Groq] = None

# ─── Re-prediction schedule ───────────────────────────────────────────────────
# (hours_until_event_threshold, re_predict_interval_minutes)
# Read as: "if event is fewer than X hours away, re-predict every Y minutes"
REPREDICTION_SCHEDULE = [
    (1,   30),    # < 1h  away → every 30 min
    (6,   120),   # < 6h  away → every 2h
    (24,  240),   # < 24h away → every 4h
    (72,  720),   # < 72h away → every 12h
    (999, 1440),  # otherwise  → every 24h
]

# FRED indicator drift thresholds — if any value shifts by more than this
# vs the stored snapshot, force a re-prediction regardless of schedule.
CONTEXT_DRIFT_THRESHOLDS = {
    "Federal Funds Rate (%)":        0.25,   # Fed actually moved rates
    "CPI YoY Inflation (%)":         0.2,
    "Unemployment Rate (%)":         0.2,
    "Real GDP Growth Rate (%)":      0.5,
    "Core PCE Inflation (%)":        0.2,
    "10-Year Treasury Yield (%)":    0.3,
    "Total Nonfarm Payrolls (thousands)": 50,
}


def _get_client() -> Groq:
    global _client
    if _client is None:
        if not GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY not set.")
        _client = Groq(api_key=GROQ_API_KEY)
    return _client


# ─── Re-prediction logic ──────────────────────────────────────────────────────

def _hours_until_event(event_date: str) -> float:
    """Return hours between now and the event. Negative if past."""
    try:
        dt    = datetime.fromisoformat(event_date.replace("Z", "+00:00")).astimezone(timezone.utc)
        delta = (dt - datetime.now(timezone.utc)).total_seconds()
        return delta / 3600
    except Exception:
        return 999.0


def _interval_for_hours(hours: float) -> int:
    """Return the re-prediction interval in minutes for a given hours-until-event."""
    for threshold, interval_minutes in REPREDICTION_SCHEDULE:
        if hours < threshold:
            return interval_minutes
    return 1440


def _build_context_snapshot(context: dict) -> str:
    """Build a compact JSON snapshot of current FRED values for drift detection."""
    snap = {label: info.get("value") for label, info in context.items()}
    return json.dumps(snap, sort_keys=True)


def _detect_context_drift(old_snapshot_json: Optional[str], current_context: dict) -> Optional[str]:
    """
    Compare current FRED context against the stored snapshot.
    Returns a human-readable drift description if significant change detected,
    or None if context is stable.
    """
    if not old_snapshot_json:
        return None
    try:
        old_snap = json.loads(old_snapshot_json)
    except Exception:
        return None

    drifts = []
    for label, info in current_context.items():
        old_val = old_snap.get(label)
        new_val = info.get("value")
        if old_val is None or new_val is None:
            continue
        try:
            change = abs(float(new_val) - float(old_val))
            threshold = CONTEXT_DRIFT_THRESHOLDS.get(label, 999)
            if change >= threshold:
                direction = "↑" if float(new_val) > float(old_val) else "↓"
                drifts.append(f"{label}: {old_val} → {new_val} ({direction}{change:.2f})")
        except (ValueError, TypeError):
            continue

    return "; ".join(drifts) if drifts else None


def should_repredict(event: dict, force: bool = False) -> tuple[bool, str]:
    """
    Determine whether an event should be re-predicted right now.

    Returns (should_repredict: bool, reason: str)

    Reasons:
      - "first_prediction"  — no prediction exists yet
      - "schedule"          — normal time-based interval
      - "context_drift"     — macro conditions changed significantly
      - "forced"            — manual user request
    """
    if force:
        return True, "Manual re-prediction requested"

    hours = _hours_until_event(event["event_date"])

    # Don't predict for past events
    if hours < 0:
        return False, "Event already released"

    existing = db.get_prediction(event["event_name"], event["event_date"])
    if not existing or not existing.get("direction"):
        return True, "first_prediction"

    # Check context drift (only if FRED is configured)
    if fred_client.FRED_API_KEY:
        current_context = fred_client.get_economic_context()
        if current_context:
            drift = _detect_context_drift(existing.get("context_snapshot"), current_context)
            if drift:
                log.info("Context drift detected for '%s': %s", event["event_name"], drift)
                return True, f"Macro context shifted: {drift}"

    # Time-based schedule
    interval_minutes = _interval_for_hours(hours)
    updated_at = existing.get("updated_at") or existing.get("created_at", "")
    if not updated_at:
        return True, "first_prediction"

    try:
        last_updated = datetime.fromisoformat(updated_at.replace("Z", "+00:00")).astimezone(timezone.utc)
        age_minutes  = (datetime.now(timezone.utc) - last_updated).total_seconds() / 60
        if age_minutes >= interval_minutes:
            label = _schedule_label(hours)
            return True, f"Scheduled update ({label} — refreshes every {interval_minutes//60}h{interval_minutes%60:02d}m)"
    except Exception:
        return True, "first_prediction"

    return False, f"Up to date (next update in ~{int(interval_minutes - age_minutes)}m)"


def _schedule_label(hours: float) -> str:
    if hours < 1:    return "< 1h to release"
    if hours < 6:    return f"{hours:.0f}h to release"
    if hours < 24:   return f"{hours:.0f}h to release"
    if hours < 72:   return f"{hours/24:.1f}d to release"
    return f"{hours/24:.0f}d to release"


# ─── System prompt ────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """You are a world-class macroeconomic analyst and crypto market strategist with deep expertise in:
- US economic data releases and their historical patterns
- Federal Reserve policy and its impact on risk assets
- Bitcoin and cryptocurrency market dynamics
- Statistical analysis of economic surprises

Your role: predict upcoming US economic data releases and their likely impact on cryptocurrency markets (primarily Bitcoin/ETH).

You will be given:
1. The specific economic event and its consensus forecast
2. Real-time US macroeconomic context from FRED
3. Historical results for this exact event (past releases)
4. Your own past prediction accuracy for this event type
5. Specific mistakes you made before — LEARN FROM THEM
6. Why this prediction is being re-run (if applicable) — factor this in

CRITICAL OUTPUT RULES:
- Return ONLY a valid JSON object — no markdown, no explanation, no code blocks
- Every field must be present
- "direction": must be exactly "greater", "less", or "equal" (actual vs forecast)
- "confidence": integer 0–100 (be honest — fundamental analysis alone is uncertain)
- "crypto_impact": must be exactly "bullish", "bearish", or "neutral"

PREDICTION LOGIC:
- "greater" = actual release will BEAT the forecast → usually bullish for economy
- "less" = actual release will MISS the forecast → usually bearish for economy
- Map economic outcome to crypto impact based on the current macro regime:
  * In a "risk-on" / rate-cut environment: strong economy can be bullish for crypto
  * In a "rate-hike" / inflation-fighting environment: strong economy = higher rates = bearish crypto
  * Weak jobs/CPI can signal rate cuts → bullish crypto in that regime
  * Always consider the CURRENT Fed stance before mapping economy → crypto"""


# ─── Prompt builder ───────────────────────────────────────────────────────────

def _build_prompt(event: dict, economic_context: str, historical: list[dict],
                  accuracy_stats: dict, reprediction_reason: str) -> str:

    hist_text = "No historical data available."
    if historical:
        lines = []
        for h in historical[:10]:
            actual   = h.get("actual",   "?")
            forecast = h.get("forecast", "?")
            previous = h.get("previous", "?")
            date     = h.get("release_date", "?")[:10]
            surprise = ""
            try:
                a = float(str(actual).replace("%","").replace("K","000").replace("M","000000"))
                f = float(str(forecast).replace("%","").replace("K","000").replace("M","000000"))
                if a > f:   surprise = " ↑ BEAT"
                elif a < f: surprise = " ↓ MISS"
                else:       surprise = " → MET"
            except Exception:
                pass
            lines.append(f"  {date} | Actual: {actual} | Forecast: {forecast} | Prev: {previous}{surprise}")
        hist_text = "Last 10 releases (newest first):\n" + "\n".join(lines)

    acc_text = ""
    if accuracy_stats["total"] > 0:
        acc_text = (
            f"\nYOUR TRACK RECORD FOR THIS EVENT TYPE:\n"
            f"  Total: {accuracy_stats['total']} | Correct: {accuracy_stats['correct']} "
            f"| Accuracy: {accuracy_stats['accuracy_pct']}%\n"
        )
        if accuracy_stats["mistakes"]:
            acc_text += "\nYOUR RECENT MISTAKES — ACTIVELY CORRECT THESE:\n"
            for m in accuracy_stats["mistakes"]:
                acc_text += (
                    f"  Date: {m['date'][:10]} | Predicted: {m['predicted']} | "
                    f"Actual was: {m['actual_value']} | Reasoning was: {m['reasoning'][:120]}...\n"
                )

    is_repredict = reprediction_reason and reprediction_reason != "first_prediction"
    repredict_block = ""
    if is_repredict:
        repredict_block = (
            f"\n⚠️  RE-PREDICTION TRIGGERED: {reprediction_reason}\n"
            f"This is not your first analysis of this event. "
            f"Update your view based on new information above.\n"
        )

    return f"""=== ECONOMIC EVENT TO PREDICT ===
Event:              {event['event_name']}
Date/Time (UTC):    {event['event_date']}
Consensus Forecast: {event.get('forecast') or 'No consensus yet'}
Previous Release:   {event.get('previous') or 'Unknown'}
Hours Until Release: {_hours_until_event(event['event_date']):.1f}h

=== CURRENT US MACRO CONTEXT ===
{economic_context}

=== HISTORICAL RESULTS ===
{hist_text}

=== YOUR LEARNING FEEDBACK ==={acc_text if acc_text else chr(10) + 'No past predictions resolved yet.'}
{repredict_block}
=== YOUR TASK ===
Predict whether ACTUAL will be GREATER THAN, LESS THAN, or EQUAL TO forecast.
Then predict crypto market impact given the CURRENT macro regime.

Return this exact JSON:
{{
  "direction": "greater" | "less" | "equal",
  "confidence": <integer 0-100>,
  "crypto_impact": "bullish" | "bearish" | "neutral",
  "economic_analysis": "<2-3 sentences on current conditions>",
  "historical_pattern": "<2-3 sentences on what history shows>",
  "reasoning": "<3-5 sentences: WHY this direction + crypto impact>",
  "risk_factors": "<1-2 sentences: what could invalidate this>",
  "learning_notes": "<what you corrected from past mistakes, or 'No corrections needed'>"
}}"""


# ─── Core ─────────────────────────────────────────────────────────────────────

def predict_event(event: dict, force: bool = False,
                  reprediction_reason: Optional[str] = None) -> Optional[dict]:
    """
    Generate or refresh a prediction for a single event.
    Checks should_repredict() unless force=True.
    """
    event_name = event["event_name"]
    event_date = event["event_date"]

    # Determine if we should actually re-predict
    if not force and reprediction_reason is None:
        do_it, reason = should_repredict(event)
        if not do_it:
            log.debug("Skipping re-predict for '%s': %s", event_name, reason)
            return db.get_prediction(event_name, event_date)
        reprediction_reason = reason
    elif force:
        reprediction_reason = reprediction_reason or "Manual re-prediction requested"

    log.info("Predicting '%s' — reason: %s", event_name, reprediction_reason)

    # Build context
    current_context  = fred_client.get_economic_context() if fred_client.FRED_API_KEY else {}
    economic_context = fred_client.get_context_summary_text()
    historical       = db.get_historical(event_name, limit=10)
    accuracy_stats   = db.get_accuracy_stats(event_name)

    if not historical and fred_client.FRED_API_KEY:
        fred_client.seed_historical_for_event(event_name)
        historical = db.get_historical(event_name, limit=10)

    user_prompt = _build_prompt(
        event, economic_context, historical, accuracy_stats,
        reprediction_reason or "first_prediction"
    )

    raw_response = _call_groq(user_prompt)
    if not raw_response:
        return db.get_prediction(event_name, event_date)

    parsed = _parse_groq_response(raw_response)
    if not parsed:
        log.error("Failed to parse Groq response for '%s'", event_name)
        return db.get_prediction(event_name, event_date)

    # Build context snapshot for drift detection
    context_snapshot = _build_context_snapshot(current_context) if current_context else None

    prediction = {
        "event_name":           event_name,
        "event_date":           event_date,
        "direction":            parsed.get("direction"),
        "confidence":           parsed.get("confidence"),
        "crypto_impact":        parsed.get("crypto_impact"),
        "economic_analysis":    parsed.get("economic_analysis"),
        "historical_pattern":   parsed.get("historical_pattern"),
        "reasoning":            parsed.get("reasoning"),
        "risk_factors":         parsed.get("risk_factors"),
        "learning_notes":       parsed.get("learning_notes"),
        "raw_response":         raw_response,
        "reprediction_reason":  reprediction_reason,
        "context_snapshot":     context_snapshot,
    }
    db.upsert_prediction(prediction)
    return db.get_prediction(event_name, event_date)


def predict_all_upcoming(events: list[dict], force: bool = False) -> dict:
    """
    Check and re-predict all upcoming events that warrant an update.
    Returns dict of event key → prediction.
    """
    results = {}
    # Only events without actuals
    pending = [e for e in events if not e.get("actual")]

    for i, event in enumerate(pending):
        key = f"{event['event_name']}::{event['event_date']}"
        try:
            pred = predict_event(event, force=force)
            results[key] = pred
            if i < len(pending) - 1:
                time.sleep(2)
        except RateLimitError:
            log.warning("Groq rate limit — pausing 60s")
            time.sleep(60)
            try:
                pred = predict_event(event, force=force)
                results[key] = pred
            except Exception as exc:
                log.error("Retry failed for '%s': %s", event["event_name"], exc)
                results[key] = None
        except Exception as exc:
            log.error("Prediction failed for '%s': %s", event["event_name"], exc)
            results[key] = None

    return results


# ─── Groq helpers ─────────────────────────────────────────────────────────────

def _call_groq(user_prompt: str, retries: int = 2) -> Optional[str]:
    client = _get_client()
    for attempt in range(retries + 1):
        try:
            chat = client.chat.completions.create(
                model=GROQ_MODEL,
                max_tokens=GROQ_MAX_TOKENS,
                temperature=GROQ_TEMPERATURE,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user",   "content": user_prompt},
                ],
            )
            return chat.choices[0].message.content.strip()
        except RateLimitError:
            raise
        except APIError as exc:
            log.warning("Groq API error (attempt %d): %s", attempt + 1, exc)
            if attempt < retries:
                time.sleep(5 * (attempt + 1))
        except Exception as exc:
            log.error("Unexpected Groq error: %s", exc)
            if attempt < retries:
                time.sleep(3)
    return None


def _parse_groq_response(raw: str) -> Optional[dict]:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1]) if len(lines) > 2 else text

    start = text.find("{")
    end   = text.rfind("}") + 1
    if start == -1 or end == 0:
        log.error("No JSON in Groq response: %s", raw[:200])
        return None

    try:
        parsed = json.loads(text[start:end])
        required = {"direction", "confidence", "crypto_impact", "reasoning"}
        if not required.issubset(parsed.keys()):
            log.error("Missing fields: %s", required - parsed.keys())
            return None
        parsed["direction"]     = parsed["direction"].lower().strip()
        parsed["crypto_impact"] = parsed["crypto_impact"].lower().strip()
        if parsed["direction"] not in ("greater", "less", "equal"):
            return None
        if parsed["crypto_impact"] not in ("bullish", "bearish", "neutral"):
            parsed["crypto_impact"] = "neutral"
        return parsed
    except json.JSONDecodeError as exc:
        log.error("JSON parse error: %s | Raw: %s", exc, raw[:400])
        return None
