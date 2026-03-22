"""
scheduler.py — Background auto-refresh + adaptive re-prediction scheduler.

Every CALENDAR_REFRESH_INTERVAL seconds:
  1. Re-fetches ForexFactory calendar (new events, actuals, resolves predictions)
  2. Cleans expired cache
  3. For every upcoming event, calls predictor.should_repredict() and re-predicts if needed
     — frequency depends on time-until-release and macro context drift
"""

import logging
import threading
import time
from datetime import datetime, timezone

log = logging.getLogger(__name__)

CALENDAR_REFRESH_INTERVAL = 30 * 60  # 30 min calendar poll

_scheduler_thread: threading.Thread | None = None
_stop_event  = threading.Event()
_last_run:   datetime | None = None
_run_count:  int = 0
_last_prediction_check: datetime | None = None


def _run_loop() -> None:
    global _last_run, _run_count, _last_prediction_check

    log.info("⏰ Scheduler started (calendar interval: %ds)", CALENDAR_REFRESH_INTERVAL)

    while not _stop_event.is_set():
        try:
            import scraper
            import database as db
            from config import GROQ_API_KEY

            log.info("🔄 Scheduler tick #%d — refreshing calendar...", _run_count + 1)

            # 1. Refresh calendar data + resolve any predictions
            events = scraper.refresh_calendar()
            log.info("✅ Refreshed %d events", len(events))

            # 2. Clean expired cache
            db.cache_clear_expired()

            # 3. Adaptive re-prediction check
            if GROQ_API_KEY:
                upcoming = [e for e in events if not e.get("actual")]
                if upcoming:
                    _check_repredictions(upcoming)

            _last_run   = datetime.now(timezone.utc)
            _run_count += 1

        except Exception as exc:
            log.error("Scheduler error: %s", exc, exc_info=True)

        # Chunked sleep — wake up every second to check stop_event
        for _ in range(CALENDAR_REFRESH_INTERVAL):
            if _stop_event.is_set():
                break
            time.sleep(1)

    log.info("⏹️ Scheduler stopped after %d runs", _run_count)


def _check_repredictions(upcoming: list[dict]) -> None:
    """
    For each upcoming event, ask predictor.should_repredict().
    If yes, run prediction in this background thread (no UI blocking).
    Respects Groq rate limits with a 3s delay between calls.
    """
    global _last_prediction_check
    from predictor import should_repredict, predict_event

    repredicted = 0
    for event in upcoming:
        if _stop_event.is_set():
            break
        try:
            do_it, reason = should_repredict(event)
            if do_it:
                log.info(
                    "Re-predicting '%s' (reason: %s)",
                    event["event_name"], reason
                )
                predict_event(event, reprediction_reason=reason)
                repredicted += 1
                time.sleep(3)  # polite Groq rate limit delay
        except Exception as exc:
            log.error("Re-prediction failed for '%s': %s", event["event_name"], exc)

    if repredicted:
        log.info("✅ Scheduler re-predicted %d event(s) this cycle", repredicted)

    _last_prediction_check = datetime.now(timezone.utc)


def start() -> None:
    global _scheduler_thread
    if _scheduler_thread is not None and _scheduler_thread.is_alive():
        return
    _stop_event.clear()
    _scheduler_thread = threading.Thread(
        target=_run_loop,
        name="calendar-scheduler",
        daemon=True,
    )
    _scheduler_thread.start()
    log.info("Scheduler thread started: %s", _scheduler_thread.name)


def stop() -> None:
    _stop_event.set()
    if _scheduler_thread:
        _scheduler_thread.join(timeout=5)


def status() -> dict:
    is_alive = _scheduler_thread is not None and _scheduler_thread.is_alive()
    return {
        "running":    is_alive,
        "run_count":  _run_count,
        "last_run":   _last_run.isoformat() if _last_run else None,
        "next_run_in": _next_run_seconds(),
        "last_pred_check": _last_prediction_check.isoformat() if _last_prediction_check else None,
    }


def _next_run_seconds() -> int | None:
    if _last_run is None:
        return None
    elapsed = (datetime.now(timezone.utc) - _last_run).total_seconds()
    return int(max(0, CALENDAR_REFRESH_INTERVAL - elapsed))
