"""
database.py — SQLite database layer.
Handles events, predictions, prediction history, historical results, cache, and learning loop.
Thread-safe via connection-per-call pattern (compatible with Streamlit).
"""

import sqlite3
import json
import logging
from datetime import datetime, timezone
from contextlib import contextmanager
from typing import Optional

from config import DATABASE_PATH

log = logging.getLogger(__name__)


# ─── Schema ───────────────────────────────────────────────────────────────────

_SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    event_name  TEXT    NOT NULL,
    event_date  TEXT    NOT NULL,
    currency    TEXT    NOT NULL DEFAULT 'USD',
    impact      TEXT    NOT NULL DEFAULT 'High',
    forecast    TEXT,
    previous    TEXT,
    actual      TEXT,
    detail_url  TEXT,
    scraped_at  TEXT    NOT NULL,
    UNIQUE(event_name, event_date)
);

CREATE TABLE IF NOT EXISTS historical_results (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    event_name   TEXT NOT NULL,
    release_date TEXT NOT NULL,
    actual       TEXT,
    forecast     TEXT,
    previous     TEXT,
    source       TEXT DEFAULT 'ff',
    UNIQUE(event_name, release_date)
);

CREATE TABLE IF NOT EXISTS predictions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    event_name          TEXT    NOT NULL,
    event_date          TEXT    NOT NULL,
    direction           TEXT,
    confidence          REAL,
    crypto_impact       TEXT,
    economic_analysis   TEXT,
    historical_pattern  TEXT,
    reasoning           TEXT,
    risk_factors        TEXT,
    learning_notes      TEXT,
    raw_response        TEXT,
    -- Versioning & re-prediction tracking
    version             INTEGER NOT NULL DEFAULT 1,
    reprediction_reason TEXT,
    context_snapshot    TEXT,   -- JSON hash of FRED values used; detect drift
    -- Resolution
    actual_value        TEXT,
    was_correct         INTEGER,
    resolved_at         TEXT,
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL,
    UNIQUE(event_name, event_date)
);

-- Full history of every prediction version for the change-log UI
CREATE TABLE IF NOT EXISTS prediction_history (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    event_name          TEXT NOT NULL,
    event_date          TEXT NOT NULL,
    version             INTEGER NOT NULL,
    direction           TEXT,
    confidence          REAL,
    crypto_impact       TEXT,
    reasoning           TEXT,
    reprediction_reason TEXT,
    context_snapshot    TEXT,
    created_at          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cache (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL,
    expires_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_events_date       ON events(event_date);
CREATE INDEX IF NOT EXISTS idx_pred_name_date    ON predictions(event_name, event_date);
CREATE INDEX IF NOT EXISTS idx_hist_name         ON historical_results(event_name);
CREATE INDEX IF NOT EXISTS idx_pred_hist_name    ON prediction_history(event_name, event_date);
"""

# Migration: add new columns to existing DBs without dropping data
_MIGRATIONS = [
    "ALTER TABLE predictions ADD COLUMN version INTEGER NOT NULL DEFAULT 1",
    "ALTER TABLE predictions ADD COLUMN reprediction_reason TEXT",
    "ALTER TABLE predictions ADD COLUMN context_snapshot TEXT",
    "ALTER TABLE predictions ADD COLUMN updated_at TEXT",
]


# ─── Connection ───────────────────────────────────────────────────────────────

@contextmanager
def _conn():
    con = sqlite3.connect(DATABASE_PATH, check_same_thread=False, timeout=10)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def init_db() -> None:
    with _conn() as con:
        con.executescript(_SCHEMA)
        # Run migrations safely (ignore "duplicate column" errors)
        for sql in _MIGRATIONS:
            try:
                con.execute(sql)
            except sqlite3.OperationalError:
                pass  # Column already exists
    log.info("Database initialised at %s", DATABASE_PATH)


# ─── Cache ────────────────────────────────────────────────────────────────────

def cache_get(key: str) -> Optional[str]:
    with _conn() as con:
        row = con.execute(
            "SELECT value FROM cache WHERE key=? AND expires_at > ?",
            (key, _now())
        ).fetchone()
    return row["value"] if row else None


def cache_set(key: str, value: str, ttl_seconds: int) -> None:
    from datetime import timedelta
    expires = (datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)).isoformat()
    with _conn() as con:
        con.execute(
            "INSERT OR REPLACE INTO cache(key, value, expires_at) VALUES(?,?,?)",
            (key, value, expires)
        )


def cache_clear_expired() -> None:
    with _conn() as con:
        con.execute("DELETE FROM cache WHERE expires_at <= ?", (_now(),))


# ─── Events ──────────────────────────────────────────────────────────────────

def upsert_event(event: dict) -> int:
    with _conn() as con:
        cur = con.execute("""
            INSERT INTO events(event_name, event_date, currency, impact,
                               forecast, previous, actual, detail_url, scraped_at)
            VALUES(:event_name,:event_date,:currency,:impact,
                   :forecast,:previous,:actual,:detail_url,:scraped_at)
            ON CONFLICT(event_name, event_date) DO UPDATE SET
                forecast   = excluded.forecast,
                previous   = excluded.previous,
                actual     = COALESCE(excluded.actual, events.actual),
                scraped_at = excluded.scraped_at
        """, {
            "event_name": event.get("event_name", ""),
            "event_date": event.get("event_date", ""),
            "currency":   event.get("currency", "USD"),
            "impact":     event.get("impact", "High"),
            "forecast":   event.get("forecast"),
            "previous":   event.get("previous"),
            "actual":     event.get("actual"),
            "detail_url": event.get("detail_url"),
            "scraped_at": _now(),
        })
    return cur.lastrowid


def get_upcoming_events(limit: int = 50) -> list[dict]:
    with _conn() as con:
        rows = con.execute("""
            SELECT * FROM events
            WHERE event_date >= datetime('now', '-2 hours')
            ORDER BY event_date ASC
            LIMIT ?
        """, (limit,)).fetchall()
    return [dict(r) for r in rows]


def get_recent_events(days: int = 7) -> list[dict]:
    with _conn() as con:
        rows = con.execute("""
            SELECT * FROM events
            WHERE event_date >= datetime('now', ?)
              AND actual IS NOT NULL AND actual != ''
            ORDER BY event_date DESC
        """, (f"-{days} days",)).fetchall()
    return [dict(r) for r in rows]


def update_event_actual(event_name: str, event_date: str, actual: str) -> None:
    with _conn() as con:
        con.execute(
            "UPDATE events SET actual=? WHERE event_name=? AND event_date=?",
            (actual, event_name, event_date)
        )


# ─── Historical Results ───────────────────────────────────────────────────────

def upsert_historical(record: dict) -> None:
    with _conn() as con:
        con.execute("""
            INSERT OR IGNORE INTO historical_results
                (event_name, release_date, actual, forecast, previous, source)
            VALUES(:event_name,:release_date,:actual,:forecast,:previous,:source)
        """, {
            "event_name":   record.get("event_name", ""),
            "release_date": record.get("release_date", ""),
            "actual":       record.get("actual"),
            "forecast":     record.get("forecast"),
            "previous":     record.get("previous"),
            "source":       record.get("source", "ff"),
        })


def get_historical(event_name: str, limit: int = 10) -> list[dict]:
    with _conn() as con:
        rows = con.execute("""
            SELECT * FROM historical_results
            WHERE event_name LIKE ?
            ORDER BY release_date DESC
            LIMIT ?
        """, (f"%{event_name.split()[0]}%", limit)).fetchall()
    return [dict(r) for r in rows]


# ─── Predictions ─────────────────────────────────────────────────────────────

def upsert_prediction(pred: dict) -> None:
    """
    Insert or update a prediction.
    If updating, first archives the current version to prediction_history,
    then increments the version counter.
    """
    now = _now()

    with _conn() as con:
        # Check if a prediction already exists
        existing = con.execute(
            "SELECT * FROM predictions WHERE event_name=? AND event_date=?",
            (pred["event_name"], pred["event_date"])
        ).fetchone()

        if existing:
            current_version = existing["version"] or 1
            new_version = current_version + 1

            # Archive current version to history before overwriting
            con.execute("""
                INSERT OR IGNORE INTO prediction_history
                    (event_name, event_date, version, direction, confidence,
                     crypto_impact, reasoning, reprediction_reason, context_snapshot, created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?)
            """, (
                existing["event_name"],
                existing["event_date"],
                current_version,
                existing["direction"],
                existing["confidence"],
                existing["crypto_impact"],
                existing["reasoning"],
                existing["reprediction_reason"],
                existing["context_snapshot"],
                existing["updated_at"] or existing["created_at"],
            ))

            # Update with new prediction
            con.execute("""
                UPDATE predictions SET
                    direction          = :direction,
                    confidence         = :confidence,
                    crypto_impact      = :crypto_impact,
                    economic_analysis  = :economic_analysis,
                    historical_pattern = :historical_pattern,
                    reasoning          = :reasoning,
                    risk_factors       = :risk_factors,
                    learning_notes     = :learning_notes,
                    raw_response       = :raw_response,
                    version            = :version,
                    reprediction_reason= :reprediction_reason,
                    context_snapshot   = :context_snapshot,
                    updated_at         = :updated_at
                WHERE event_name=:event_name AND event_date=:event_date
            """, {
                **pred,
                "version":    new_version,
                "updated_at": now,
            })
        else:
            # Fresh insert
            con.execute("""
                INSERT INTO predictions
                    (event_name, event_date, direction, confidence, crypto_impact,
                     economic_analysis, historical_pattern, reasoning, risk_factors,
                     learning_notes, raw_response, version, reprediction_reason,
                     context_snapshot, created_at, updated_at)
                VALUES
                    (:event_name,:event_date,:direction,:confidence,:crypto_impact,
                     :economic_analysis,:historical_pattern,:reasoning,:risk_factors,
                     :learning_notes,:raw_response,1,:reprediction_reason,
                     :context_snapshot,:created_at,:updated_at)
            """, {
                **pred,
                "created_at": now,
                "updated_at": now,
            })


def get_prediction(event_name: str, event_date: str) -> Optional[dict]:
    with _conn() as con:
        row = con.execute(
            "SELECT * FROM predictions WHERE event_name=? AND event_date=?",
            (event_name, event_date)
        ).fetchone()
    return dict(row) if row else None


def get_prediction_history(event_name: str, event_date: str) -> list[dict]:
    """Return all archived past versions for an event, newest first."""
    with _conn() as con:
        rows = con.execute("""
            SELECT * FROM prediction_history
            WHERE event_name=? AND event_date=?
            ORDER BY version DESC
        """, (event_name, event_date)).fetchall()
    return [dict(r) for r in rows]


def resolve_prediction(event_name: str, event_date: str,
                        actual_value: str, was_correct: bool) -> None:
    with _conn() as con:
        con.execute("""
            UPDATE predictions
            SET actual_value=?, was_correct=?, resolved_at=?
            WHERE event_name=? AND event_date=?
        """, (actual_value, int(was_correct), _now(), event_name, event_date))


def get_accuracy_stats(event_name: str) -> dict:
    keyword = event_name.split()[0]
    with _conn() as con:
        rows = con.execute("""
            SELECT direction, crypto_impact, reasoning, actual_value,
                   was_correct, event_date
            FROM predictions
            WHERE event_name LIKE ? AND was_correct IS NOT NULL
            ORDER BY event_date DESC
            LIMIT 10
        """, (f"%{keyword}%",)).fetchall()

    if not rows:
        return {"total": 0, "correct": 0, "accuracy_pct": 0, "mistakes": []}

    total   = len(rows)
    correct = sum(1 for r in rows if r["was_correct"] == 1)
    mistakes = [
        {
            "date":         r["event_date"],
            "predicted":    r["direction"],
            "actual_value": r["actual_value"],
            "reasoning":    r["reasoning"],
        }
        for r in rows if r["was_correct"] == 0
    ]
    return {
        "total":        total,
        "correct":      correct,
        "accuracy_pct": round(correct / total * 100, 1),
        "mistakes":     mistakes[-3:],
    }


def get_all_predictions_for_ui() -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM predictions ORDER BY event_date ASC"
        ).fetchall()
    return [dict(r) for r in rows]


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
