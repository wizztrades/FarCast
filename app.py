"""
app.py — FarCast
AI-powered crypto economic calendar with adaptive re-prediction.
"""

import logging
import time
import threading
from datetime import datetime, timezone
from typing import Optional

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

import database as db
import scheduler
from config import GROQ_API_KEY, FRED_API_KEY

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
log = logging.getLogger(__name__)

st.set_page_config(
    page_title="FarCast",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded",
)

DEMO_MODE = not bool(GROQ_API_KEY)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.stApp { background-color: #0A0C10; }
[data-testid="stSidebar"] { background: #0F1117; border-right: 1px solid #1E2330; }

.ecard {
    background: #0F1117; border: 1px solid #1E2330;
    border-radius: 14px; padding: 22px 26px; margin-bottom: 12px;
}
.ecard:hover { border-color: #2E3550; }

.badge {
    display:inline-flex; align-items:center; gap:5px;
    padding:4px 12px; border-radius:20px;
    font-size:12px; font-weight:600; letter-spacing:0.3px;
}
.b-bullish { background:#0D2B1D; color:#3DD68C; border:1px solid #1A5C3A; }
.b-bearish { background:#2B0D0D; color:#F87171; border:1px solid #5C1A1A; }
.b-neutral { background:#2B2B0D; color:#FBBF24; border:1px solid #5C500D; }
.b-greater { background:#0D2B1D; color:#3DD68C; }
.b-less    { background:#2B0D0D; color:#F87171; }
.b-equal   { background:#0D1A2B; color:#60A5FA; }
.b-impact  { background:#2B1A0D; color:#FB923C; border:1px solid #5C3A1A; font-size:10px; letter-spacing:1px; text-transform:uppercase; }
.b-version { background:#1A1A2B; color:#818CF8; border:1px solid #3730A3; font-size:10px; padding:2px 8px; }

.ev-name   { font-size:19px; font-weight:700; color:#F1F5F9; line-height:1.3; }
.ev-meta   { font-size:13px; color:#4B5563; margin-top:3px; }
.lbl       { font-size:11px; color:#4B5563; text-transform:uppercase; letter-spacing:0.8px; margin-bottom:4px; }
.val       { font-size:22px; font-weight:700; color:#F1F5F9; }
.val-pend  { font-size:22px; font-weight:700; color:#FBBF24; }
.val-act   { font-size:22px; font-weight:700; color:#3DD68C; }
.time-fut  { font-size:16px; font-weight:600; color:#60A5FA; }
.time-past { font-size:16px; font-weight:600; color:#374151; }

.cbar-wrap { display:flex; align-items:center; gap:10px; }
.cbar-bg   { flex:1; background:#1E2330; border-radius:4px; height:6px; }
.cbar-fill { height:100%; border-radius:4px; }
.cbar-pct  { font-size:14px; font-weight:700; min-width:36px; text-align:right; }

.section-hdr {
    font-size:11px; font-weight:600; color:#6B7280;
    text-transform:uppercase; letter-spacing:1.2px;
    margin:18px 0 8px 0; padding-bottom:6px;
    border-bottom:1px solid #1E2330;
}
.analysis-box {
    font-size:14px; line-height:1.75; color:#9CA3AF;
    background:#080A0E; border-left:2px solid #2E3550;
    padding:14px 18px; border-radius:0 8px 8px 0; margin:4px 0 10px 0;
}
.risk-box {
    font-size:13px; line-height:1.65; color:#FCA5A5;
    background:#130808; border-left:2px solid #5C1A1A;
    padding:12px 16px; border-radius:0 8px 8px 0; margin:4px 0 10px 0;
}
.learn-box {
    font-size:12px; color:#60A5FA; background:#080D18;
    border-left:2px solid #1D3A6E;
    padding:10px 14px; border-radius:0 6px 6px 0; margin-top:10px;
}

/* Change log rows */
.changelog-row {
    background:#080A0E; border:1px solid #1E2330;
    border-radius:8px; padding:12px 16px; margin-bottom:8px;
}
.changelog-ver   { font-size:11px; font-weight:700; color:#818CF8; }
.changelog-time  { font-size:11px; color:#4B5563; }
.changelog-why   { font-size:12px; color:#F59E0B; margin:4px 0; font-style:italic; }
.changelog-dirs  { font-size:13px; color:#9CA3AF; }

.result-correct { color:#3DD68C; font-size:13px; font-weight:600; margin-top:10px; }
.result-wrong   { color:#F87171; font-size:13px; font-weight:600; margin-top:10px; }

.demo-banner {
    background:#0D1A0D; border:1px solid #1A3A1A;
    border-radius:10px; padding:14px 18px;
    font-size:13px; color:#6B7280; margin-bottom:16px;
}
.demo-banner a { color:#F7931A; text-decoration:none; }
.quiet-week { text-align:center; padding:60px 20px; color:#374151; font-size:15px; }
hr.slim { border:none; border-top:1px solid #1E2330; margin:10px 0 16px 0; }

#MainMenu {visibility:hidden;} footer {visibility:hidden;}
header[data-testid="stHeader"] { background: transparent; }
</style>
""", unsafe_allow_html=True)


# ─── Init ────────────────────────────────────────────────────────────────────

@st.cache_resource
def _init():
    db.init_db()
    scheduler.start()
    if FRED_API_KEY:
        import fred_client
        threading.Thread(target=fred_client.seed_all_known_events, daemon=True).start()
    return True

_init()


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _fmt_dt(iso: str) -> tuple[str, str]:
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(timezone.utc)
        return dt.strftime("%b %d, %Y"), dt.strftime("%H:%M UTC")
    except Exception:
        return iso[:10], ""

def _fmt_ts(iso: str) -> str:
    """Format a stored timestamp into a short human string."""
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(timezone.utc)
        return dt.strftime("%b %d · %H:%M UTC")
    except Exception:
        return iso[:16]

def _is_future(iso: str) -> bool:
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(timezone.utc) > datetime.now(timezone.utc)
    except Exception:
        return True

def _time_until(iso: str) -> str:
    try:
        delta = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(timezone.utc) - datetime.now(timezone.utc)
        if delta.total_seconds() < 0:
            return "Released"
        h, m = int(delta.total_seconds() // 3600), int((delta.total_seconds() % 3600) // 60)
        return f"in {h//24}d {h%24}h" if h >= 24 else f"in {h}h {m}m" if h > 0 else f"in {m}m"
    except Exception:
        return ""

def _dir_badge(d: Optional[str]) -> str:
    d = (d or "").lower()
    labels = {"greater":"↑ Beat Forecast","less":"↓ Miss Forecast","equal":"→ Meet Forecast"}
    return f'<span class="badge b-{d}">{labels.get(d,d)}</span>'

def _impact_badge(i: Optional[str]) -> str:
    i = (i or "").lower()
    labels = {"bullish":"🟢 Bullish for Crypto","bearish":"🔴 Bearish for Crypto","neutral":"🟡 Neutral"}
    return f'<span class="badge b-{i}">{labels.get(i,i)}</span>'

def _conf_bar(confidence: Optional[float]) -> str:
    pct   = int(confidence or 0)
    color = "#3DD68C" if pct >= 70 else "#FBBF24" if pct >= 50 else "#F87171"
    return (
        f'<div class="lbl">Confidence</div>'
        f'<div class="cbar-wrap">'
        f'<div class="cbar-bg"><div class="cbar-fill" style="width:{pct}%;background:{color};"></div></div>'
        f'<span class="cbar-pct" style="color:{color};">{pct}%</span>'
        f'</div>'
    )

def _hist_chart(historical: list[dict]) -> Optional[go.Figure]:
    if not historical:
        return None
    dates, actuals, colors = [], [], []
    for h in reversed(historical):
        dates.append(h.get("release_date","")[:10])
        try:
            a = float(str(h.get("actual","0")).replace("%","").replace("K","").replace(",",""))
        except Exception:
            a = 0
        actuals.append(a)
        try:
            f = float(str(h.get("forecast","0") or "0").replace("%","").replace("K","").replace(",",""))
            colors.append("#3DD68C" if a >= f else "#F87171")
        except Exception:
            colors.append("#4B5563")

    fig = go.Figure(go.Bar(
        x=dates, y=actuals, marker_color=colors,
        hovertemplate="<b>%{x}</b><br>Actual: %{y}<extra></extra>",
    ))
    fig.update_layout(
        paper_bgcolor="#080A0E", plot_bgcolor="#080A0E",
        font=dict(color="#6B7280", family="Inter"),
        xaxis=dict(gridcolor="#1E2330", tickfont=dict(size=10)),
        yaxis=dict(gridcolor="#1E2330"),
        margin=dict(l=10,r=10,t=10,b=10), height=200,
        showlegend=False,
    )
    return fig

def _calc_streak(resolved: list[dict]) -> int:
    if not resolved:
        return 0
    s = sorted(resolved, key=lambda x: x.get("event_date",""), reverse=True)
    first, streak = s[0]["was_correct"], 0
    for p in s:
        if p["was_correct"] == first:
            streak += 1
        else:
            break
    return streak if first == 1 else -streak


# ─── Change log ───────────────────────────────────────────────────────────────

def _render_change_log(history: list[dict], current: dict) -> None:
    """Render the full prediction version history for an event."""
    if not history and (current.get("version", 1) <= 1):
        st.caption("This is the first prediction for this event — change log will appear after re-predictions.")
        return

    dir_icons   = {"greater":"↑ Beat","less":"↓ Miss","equal":"→ Meet"}
    impact_icons = {"bullish":"🟢","bearish":"🔴","neutral":"🟡"}

    # Show current version at top
    cur_ver = current.get("version", 1)
    updated = _fmt_ts(current.get("updated_at") or current.get("created_at",""))
    reason  = current.get("reprediction_reason") or "Initial prediction"
    d       = (current.get("direction") or "").lower()
    i       = (current.get("crypto_impact") or "").lower()

    st.markdown(
        f'<div class="changelog-row">'
        f'<span class="changelog-ver">v{cur_ver} · CURRENT</span>'
        f'<span class="changelog-time"> · {updated}</span>'
        f'<div class="changelog-why">💬 {reason}</div>'
        f'<div class="changelog-dirs">'
        f'{dir_icons.get(d,"?")} &nbsp;|&nbsp; {impact_icons.get(i,"?")} {i.capitalize()}'
        f' &nbsp;|&nbsp; {int(current.get("confidence") or 0)}% confidence'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # Past versions (newest first)
    for h in history:
        ver    = h.get("version", "?")
        ts     = _fmt_ts(h.get("created_at",""))
        why    = h.get("reprediction_reason") or "—"
        hd     = (h.get("direction") or "").lower()
        hi     = (h.get("crypto_impact") or "").lower()
        conf   = int(h.get("confidence") or 0)

        # Did direction or impact change vs the version above it?
        changed = (hd != d) or (hi != i)
        border  = "border-color:#F59E0B;" if changed else ""

        st.markdown(
            f'<div class="changelog-row" style="{border}">'
            f'<span class="changelog-ver">v{ver}</span>'
            f'<span class="changelog-time"> · {ts}</span>'
            f'{"<span style=\"font-size:11px;color:#F59E0B;\"> ⚠ changed</span>" if changed else ""}'
            f'<div class="changelog-why">💬 {why}</div>'
            f'<div class="changelog-dirs">'
            f'{dir_icons.get(hd,"?")} &nbsp;|&nbsp; {impact_icons.get(hi,"?")} {hi.capitalize()}'
            f' &nbsp;|&nbsp; {conf}% confidence'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )


# ─── Analysis detail ─────────────────────────────────────────────────────────

def _render_analysis(pred: dict, historical: list[dict], history: list[dict]) -> None:
    # Historical chart
    if historical:
        fig = _hist_chart(historical)
        if fig:
            st.plotly_chart(fig, width="stretch")
    else:
        st.caption("Historical data will accumulate as events release.")

    # Analysis sections
    for label, key, box_class in [
        ("Economic Context",   "economic_analysis",  "analysis-box"),
        ("Historical Pattern", "historical_pattern", "analysis-box"),
        ("Reasoning",          "reasoning",          "analysis-box"),
        ("Risk Factors",       "risk_factors",       "risk-box"),
    ]:
        val = pred.get(key)
        if val:
            st.markdown(f'<div class="section-hdr">{label}</div><div class="{box_class}">{val}</div>', unsafe_allow_html=True)

    if pred.get("learning_notes"):
        st.markdown(f'<div class="learn-box">Learning note: {pred["learning_notes"]}</div>', unsafe_allow_html=True)

    # Last 10 releases table
    if historical:
        st.markdown('<div class="section-hdr" style="margin-top:16px;">Past Releases</div>', unsafe_allow_html=True)
        st.dataframe(
            pd.DataFrame([{
                "Date":     h.get("release_date","")[:10],
                "Actual":   h.get("actual","—"),
                "Forecast": h.get("forecast","—"),
                "Previous": h.get("previous","—"),
            } for h in historical[:10]]),
            use_container_width=True, hide_index=True,
        )

    # Change log
    st.markdown('<div class="section-hdr" style="margin-top:16px;">Prediction Change Log</div>', unsafe_allow_html=True)
    _render_change_log(history, pred)


# ─── Event card ───────────────────────────────────────────────────────────────

def _render_event_card(event: dict, prediction: Optional[dict],
                       historical: list[dict], history: list[dict]) -> None:
    date_str, time_str = _fmt_dt(event["event_date"])
    is_future  = _is_future(event["event_date"])
    countdown  = _time_until(event["event_date"])
    has_actual = bool(event.get("actual"))
    has_pred   = prediction and prediction.get("direction")

    st.markdown('<div class="ecard">', unsafe_allow_html=True)

    # ── Row 1: Name + time ──
    col_name, col_time, col_cd = st.columns([5, 3, 2])
    with col_name:
        ver_badge = ""
        if has_pred:
            ver = prediction.get("version", 1)
            ver_badge = f' &nbsp;<span class="badge b-version">v{ver}</span>'
        st.markdown(
            f'<div class="ev-name">{event["event_name"]}{ver_badge}</div>'
            f'<div class="ev-meta"><span class="badge b-impact">USD · HIGH IMPACT</span></div>',
            unsafe_allow_html=True,
        )
    with col_time:
        st.markdown(
            f'<div class="lbl">Release Time</div>'
            f'<div style="color:#F1F5F9;font-weight:600;font-size:15px;">{date_str}</div>'
            f'<div style="color:#4B5563;font-size:13px;">{time_str}</div>',
            unsafe_allow_html=True,
        )
    with col_cd:
        css = "time-fut" if is_future else "time-past"
        st.markdown(
            f'<div class="lbl">Status</div><div class="{css}">{countdown}</div>',
            unsafe_allow_html=True,
        )

    # ── Row 2: Data ──
    st.markdown("<div style='height:14px;'></div>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f'<div class="lbl">Forecast</div><div class="val">{event.get("forecast") or "—"}</div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="lbl">Previous</div><div class="val">{event.get("previous") or "—"}</div>', unsafe_allow_html=True)
    with c3:
        if has_actual:
            st.markdown(f'<div class="lbl">Actual</div><div class="val-act">{event["actual"]}</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="lbl">Actual</div><div class="val-pend">Pending</div>', unsafe_allow_html=True)

    # ── Prediction row ──
    if has_pred:
        st.markdown('<hr class="slim">', unsafe_allow_html=True)

        # Last updated + reason
        updated_ts = prediction.get("updated_at") or prediction.get("created_at","")
        reason     = prediction.get("reprediction_reason") or "Initial prediction"
        if updated_ts:
            st.markdown(
                f'<div style="font-size:11px;color:#374151;margin-bottom:10px;">'
                f'Last analysed: {_fmt_ts(updated_ts)} &nbsp;·&nbsp; {reason}'
                f'</div>',
                unsafe_allow_html=True,
            )

        pc1, pc2, pc3 = st.columns([2, 3, 3])
        with pc1:
            st.markdown(
                f'<div class="lbl">Expected Result</div>{_dir_badge(prediction["direction"])}',
                unsafe_allow_html=True,
            )
        with pc2:
            st.markdown(
                f'<div class="lbl">Market Impact</div>{_impact_badge(prediction["crypto_impact"])}',
                unsafe_allow_html=True,
            )
        with pc3:
            st.markdown(_conf_bar(prediction.get("confidence")), unsafe_allow_html=True)

        # Expander + per-event re-predict button side by side
        exp_col, btn_col = st.columns([5, 1])
        with exp_col:
            with st.expander("View full analysis", expanded=False):
                _render_analysis(prediction, historical, history)
        with btn_col:
            if is_future and GROQ_API_KEY:
                btn_key = f"repredict_{event['event_name']}_{event['event_date']}"
                if st.button("⚡ Re-predict", key=btn_key, use_container_width=True,
                             help="Force a new AI analysis right now"):
                    with st.spinner("Re-analysing..."):
                        import predictor
                        predictor.predict_event(
                            event, force=True,
                            reprediction_reason="Manual re-prediction requested by user"
                        )
                    st.rerun()

    elif is_future and GROQ_API_KEY:
        # No prediction yet — show generate button
        btn_key = f"gen_{event['event_name']}_{event['event_date']}"
        col_txt, col_btn = st.columns([5, 1])
        with col_txt:
            st.markdown(
                '<div style="color:#374151;font-size:13px;margin-top:10px;">'
                'No prediction yet.</div>',
                unsafe_allow_html=True,
            )
        with col_btn:
            if st.button("⚡ Predict", key=btn_key, use_container_width=True):
                with st.spinner("Analysing..."):
                    import predictor
                    predictor.predict_event(event)
                st.rerun()
    elif not GROQ_API_KEY:
        st.markdown(
            '<div style="color:#374151;font-size:13px;margin-top:10px;">'
            'Add GROQ_API_KEY to enable predictions.</div>',
            unsafe_allow_html=True,
        )

    # Resolution badge
    if has_pred and prediction.get("was_correct") is not None:
        correct = prediction["was_correct"] == 1
        cls = "result-correct" if correct else "result-wrong"
        st.markdown(
            f'<div class="{cls}">{"✅ Prediction was correct" if correct else "❌ Prediction was wrong"}</div>',
            unsafe_allow_html=True,
        )

    st.markdown('</div>', unsafe_allow_html=True)


# ─── Accuracy stats ───────────────────────────────────────────────────────────

def _render_stats(all_preds: list[dict]) -> None:
    resolved = [p for p in all_preds if p.get("was_correct") is not None]
    if not resolved:
        return
    total   = len(resolved)
    correct = sum(1 for p in resolved if p["was_correct"] == 1)
    acc     = round(correct / total * 100, 1)
    streak  = _calc_streak(resolved)
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.metric("Predictions Resolved", total)
    with c2: st.metric("Correct",  correct)
    with c3: st.metric("Accuracy", f"{acc}%")
    with c4: st.metric("Streak",   f"{'✅' if streak >= 0 else '❌'} {abs(streak)}")
    st.divider()


# ─── Sidebar ─────────────────────────────────────────────────────────────────

def _sidebar() -> tuple[bool, bool]:
    with st.sidebar:
        st.markdown("## 📡 FarCast")
        st.caption("AI predictions for crypto-moving economic events.")
        st.divider()

        if st.button("↻  Refresh", use_container_width=True):
            st.session_state["force_refresh"] = True
            st.rerun()

        if GROQ_API_KEY and st.button("⚡ Re-run All Predictions", use_container_width=True,
                                       help="Force re-analysis for every upcoming event"):
            st.session_state["force_regen"] = True
            st.rerun()

        st.divider()
        show_past     = st.toggle("Show past events",     value=False)
        show_resolved = st.toggle("Show resolved events", value=True)

        st.divider()
        st.caption(
            "Predictions auto-update based on time to release:\n"
            "- > 3 days out: every 24h\n"
            "- 1–3 days: every 12h\n"
            "- 6–24h: every 4h\n"
            "- 1–6h: every 2h\n"
            "- < 1h: every 30min\n\n"
            "Also re-predicts automatically if macro data shifts significantly.\n\n"
            "For confluence only — not financial advice."
        )

    return show_past, show_resolved


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    st.markdown("""
    <div style="text-align:center; padding:28px 0 16px 0;">
      <div style="font-size:13px; color:#4B5563; letter-spacing:2px; text-transform:uppercase; margin-bottom:8px;">
        Economic Calendar
      </div>
      <h1 style="font-size:40px; font-weight:800; color:#F1F5F9; margin:0; letter-spacing:-1px;">
        📡 FarCast
      </h1>
      <p style="color:#4B5563; font-size:14px; margin-top:10px; max-width:500px; margin-left:auto; margin-right:auto;">
        High-impact US economic releases that move crypto — with AI predictions that update as the date approaches.
      </p>
    </div>
    """, unsafe_allow_html=True)

    show_past, show_resolved = _sidebar()

    if DEMO_MODE:
        st.markdown(
            '<div class="demo-banner">'
            '📡 Running in demo mode with sample data. '
            'Add API keys to <code>.env</code> to enable live predictions. '
            '<a href="https://console.groq.com/keys">Get a free Groq key →</a>'
            '</div>',
            unsafe_allow_html=True,
        )

    force_refresh = st.session_state.pop("force_refresh", False)
    force_regen   = st.session_state.pop("force_regen",   False)

    # ── Load events ──
    if DEMO_MODE:
        import mock_data
        events = mock_data.get_mock_events()
    else:
        import scraper
        with st.spinner("Updating calendar..."):
            events = (
                scraper.refresh_calendar()
                if (force_refresh or "events_loaded" not in st.session_state)
                else scraper.get_cached_events()
            )
            st.session_state["events_loaded"] = True

    if not events:
        st.markdown(
            '<div class="quiet-week">'
            '📭 No high-impact crypto events this week.<br>'
            '<span style="font-size:13px;color:#1F2937;">'
            'Check back for FOMC, CPI, NFP and other major releases.'
            '</span></div>',
            unsafe_allow_html=True,
        )
        return

    # ── Generate / refresh predictions ──
    if not DEMO_MODE and GROQ_API_KEY:
        import predictor
        upcoming = [e for e in events if not e.get("actual")]
        if force_regen:
            with st.spinner(f"Re-analysing {len(upcoming)} events..."):
                predictor.predict_all_upcoming(upcoming, force=True)
        else:
            # Generate for any that have no prediction at all
            needs = [
                e for e in upcoming
                if not (db.get_prediction(e["event_name"], e["event_date"]) or {}).get("direction")
            ]
            if needs:
                bar = st.progress(0, text=f"Generating predictions for {len(needs)} events...")
                for i, ev in enumerate(needs):
                    predictor.predict_event(ev)
                    bar.progress((i+1)/len(needs), text=f"Analysing: {ev['event_name']}")
                    time.sleep(2)
                bar.empty()

    # ── Stats ──
    _render_stats(db.get_all_predictions_for_ui())

    # ── Filter ──
    display_events = events if show_past else [e for e in events if _is_future(e["event_date"])]
    if not display_events:
        st.markdown(
            '<div class="quiet-week">✅ All events this week have released.<br>'
            '<span style="font-size:13px;color:#1F2937;">'
            'Toggle "Show past events" to review them.</span></div>',
            unsafe_allow_html=True,
        )
        return

    # ── Cards ──
    for event in display_events:
        if not show_past and not _is_future(event["event_date"]):
            continue

        if DEMO_MODE:
            import mock_data
            prediction = mock_data.get_mock_prediction(event["event_name"])
            historical = mock_data.get_mock_historical(event["event_name"])
            history    = []
        else:
            prediction = db.get_prediction(event["event_name"], event["event_date"])
            historical = db.get_historical(event["event_name"], limit=10)
            history    = db.get_prediction_history(event["event_name"], event["event_date"])

        if not show_resolved and prediction and prediction.get("was_correct") is not None:
            continue

        _render_event_card(event, prediction, historical, history)


if __name__ == "__main__":
    main()
