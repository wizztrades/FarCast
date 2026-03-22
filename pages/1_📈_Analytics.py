"""
pages/1_📈_Analytics.py — Prediction accuracy & learning metrics page.
Streamlit multi-page app — auto-discovered from the pages/ directory.
"""

import logging
from datetime import datetime, timezone

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

import database as db
import scheduler

log = logging.getLogger(__name__)

st.set_page_config(
    page_title="Analytics — FarCast",
    page_icon="📈",
    layout="wide",
)

# ─── Shared CSS (minimal — inherits from main app theme) ─────────────────────
st.markdown("""
<style>
.stApp { background-color: #0E1117; }
.metric-card {
    background: #1E2329;
    border: 1px solid #2D3748;
    border-radius: 10px;
    padding: 16px 20px;
    text-align: center;
}
.metric-val  { font-size: 32px; font-weight: 800; color: #F7931A; }
.metric-label{ font-size: 12px; color: #718096; text-transform: uppercase; letter-spacing: 1px; }
.section-hdr { font-size: 18px; font-weight: 700; color: #FAFAFA; margin: 24px 0 12px 0; }
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

_PLOTLY_LAYOUT = dict(
    paper_bgcolor="#161B22",
    plot_bgcolor="#161B22",
    font=dict(color="#A0AEC0", size=12),
    xaxis=dict(gridcolor="#2D3748", linecolor="#2D3748"),
    yaxis=dict(gridcolor="#2D3748", linecolor="#2D3748"),
    margin=dict(l=20, r=20, t=40, b=20),
)

# ─── Header ──────────────────────────────────────────────────────────────────

st.markdown("""
<div style="padding: 16px 0 8px 0;">
  <h1 style="font-size:30px;font-weight:800;color:#FAFAFA;margin:0;">
    📈 Analytics & Learning Metrics
  </h1>
  <p style="color:#A0AEC0;font-size:14px;margin-top:6px;">
    How well has the AI been predicting economic releases? Does it improve over time?
  </p>
</div>
""", unsafe_allow_html=True)

# ─── Load data ───────────────────────────────────────────────────────────────

all_preds = db.get_all_predictions_for_ui()
resolved  = [p for p in all_preds if p.get("was_correct") is not None]
pending   = [p for p in all_preds if p.get("was_correct") is None]

# ─── No data state ───────────────────────────────────────────────────────────

if not all_preds:
    st.info(
        "📭 No predictions in the database yet.\n\n"
        "Go back to the **Calendar** page and predictions will be generated automatically "
        "as you load events."
    )
    st.stop()

# ─── Top KPIs ────────────────────────────────────────────────────────────────

total   = len(all_preds)
n_res   = len(resolved)
n_pend  = len(pending)
correct = sum(1 for p in resolved if p["was_correct"] == 1)
acc_pct = round(correct / n_res * 100, 1) if n_res > 0 else 0

# Crypto impact accuracy
bullish_preds = [p for p in resolved if p.get("crypto_impact") == "bullish"]
bearish_preds = [p for p in resolved if p.get("crypto_impact") == "bearish"]
bullish_acc   = round(sum(1 for p in bullish_preds if p["was_correct"]==1) / len(bullish_preds) * 100, 1) if bullish_preds else 0
bearish_acc   = round(sum(1 for p in bearish_preds if p["was_correct"]==1) / len(bearish_preds) * 100, 1) if bearish_preds else 0

st.markdown("### 🏆 Overall Performance")
c1, c2, c3, c4, c5, c6 = st.columns(6)
metrics = [
    ("Total Predictions",   str(total),         "#FAFAFA"),
    ("Resolved",            str(n_res),          "#A0AEC0"),
    ("Pending",             str(n_pend),         "#F6E05E"),
    ("Overall Accuracy",    f"{acc_pct}%",       "#48BB78" if acc_pct >= 60 else "#FC8181"),
    ("Bullish Calls Acc.",  f"{bullish_acc}%",   "#48BB78"),
    ("Bearish Calls Acc.",  f"{bearish_acc}%",   "#FC8181"),
]
for col, (label, val, color) in zip([c1,c2,c3,c4,c5,c6], metrics):
    with col:
        st.markdown(
            f'<div class="metric-card">'
            f'<div class="metric-val" style="color:{color};">{val}</div>'
            f'<div class="metric-label">{label}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

st.markdown("<div style='height:24px;'></div>", unsafe_allow_html=True)

# ─── Only show detailed charts if we have resolved predictions ───────────────

if not resolved:
    st.info(
        "⏳ No resolved predictions yet — accuracy charts will appear here once events release "
        "and the system auto-resolves predictions against actual values."
    )
else:
    # ── 1. Accuracy over time (cumulative) ──────────────────────────────────
    st.markdown('<div class="section-hdr">📉 Accuracy Over Time</div>', unsafe_allow_html=True)

    sorted_res = sorted(resolved, key=lambda x: x.get("event_date", ""))
    cumulative_acc = []
    running_correct = 0
    for i, p in enumerate(sorted_res):
        running_correct += int(p["was_correct"] == 1)
        cumulative_acc.append({
            "Prediction #":  i + 1,
            "Event":         p["event_name"],
            "Date":          p.get("event_date", "")[:10],
            "Accuracy (%)":  round(running_correct / (i + 1) * 100, 1),
            "Correct":       p["was_correct"] == 1,
        })
    df_cum = pd.DataFrame(cumulative_acc)

    fig_acc = go.Figure()
    fig_acc.add_trace(go.Scatter(
        x=df_cum["Prediction #"],
        y=df_cum["Accuracy (%)"],
        mode="lines+markers",
        line=dict(color="#F7931A", width=2.5),
        marker=dict(
            color=["#48BB78" if c else "#FC8181" for c in df_cum["Correct"]],
            size=9,
            line=dict(color="#0E1117", width=2),
        ),
        hovertemplate=(
            "<b>%{customdata[0]}</b><br>"
            "Prediction #%{x}<br>"
            "Running accuracy: %{y:.1f}%<br>"
            "<extra></extra>"
        ),
        customdata=list(zip(df_cum["Event"], df_cum["Date"])),
    ))
    fig_acc.add_hline(y=50, line_dash="dot", line_color="#4A5568",
                       annotation_text="50% baseline", annotation_font_color="#4A5568")
    fig_acc.update_layout(
        **_PLOTLY_LAYOUT,
        height=280,
        title=dict(text="Cumulative Prediction Accuracy", font=dict(color="#FAFAFA", size=14)),
        yaxis=dict(**_PLOTLY_LAYOUT["yaxis"], range=[0, 105], ticksuffix="%"),
        xaxis_title="Prediction Number",
    )
    st.plotly_chart(fig_acc, width="stretch", config={"displayModeBar": False})

    # ── 2. Per-event accuracy breakdown ─────────────────────────────────────
    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown('<div class="section-hdr">🎯 Accuracy by Event Type</div>', unsafe_allow_html=True)

        event_stats: dict[str, dict] = {}
        for p in resolved:
            name = p["event_name"]
            if name not in event_stats:
                event_stats[name] = {"total": 0, "correct": 0}
            event_stats[name]["total"] += 1
            event_stats[name]["correct"] += int(p["was_correct"] == 1)

        event_df = pd.DataFrame([
            {
                "Event":    k,
                "Correct":  v["correct"],
                "Total":    v["total"],
                "Accuracy": round(v["correct"] / v["total"] * 100, 1),
            }
            for k, v in sorted(event_stats.items(), key=lambda x: -x[1]["correct"]/x[1]["total"])
        ])

        fig_ev = go.Figure(go.Bar(
            y=event_df["Event"],
            x=event_df["Accuracy"],
            orientation="h",
            marker_color=[
                "#48BB78" if a >= 60 else "#F6E05E" if a >= 40 else "#FC8181"
                for a in event_df["Accuracy"]
            ],
            text=[f"{a}% ({c}/{t})" for a, c, t in zip(
                event_df["Accuracy"], event_df["Correct"], event_df["Total"])],
            textposition="outside",
            hovertemplate="<b>%{y}</b><br>Accuracy: %{x:.1f}%<extra></extra>",
        ))
        fig_ev.update_layout(
            **_PLOTLY_LAYOUT,
            height=max(250, len(event_df) * 45),
            xaxis=dict(**_PLOTLY_LAYOUT["xaxis"], range=[0, 115], ticksuffix="%"),
            showlegend=False,
        )
        st.plotly_chart(fig_ev, width="stretch", config={"displayModeBar": False})

    with col_right:
        st.markdown('<div class="section-hdr">🔮 Direction Distribution</div>', unsafe_allow_html=True)

        dir_counts = {"greater": 0, "less": 0, "equal": 0}
        dir_correct = {"greater": 0, "less": 0, "equal": 0}
        for p in resolved:
            d = p.get("direction", "equal")
            dir_counts[d] = dir_counts.get(d, 0) + 1
            if p["was_correct"] == 1:
                dir_correct[d] = dir_correct.get(d, 0) + 1

        labels  = ["↑ Greater Than", "↓ Less Than", "→ Equal To"]
        keys    = ["greater", "less", "equal"]
        totals  = [dir_counts.get(k, 0) for k in keys]
        correct_counts = [dir_correct.get(k, 0) for k in keys]
        acc_vals = [
            round(c / t * 100, 1) if t > 0 else 0
            for c, t in zip(correct_counts, totals)
        ]

        fig_dir = go.Figure()
        fig_dir.add_trace(go.Bar(
            name="Correct",
            x=labels,
            y=correct_counts,
            marker_color="#48BB78",
        ))
        fig_dir.add_trace(go.Bar(
            name="Wrong",
            x=labels,
            y=[t - c for t, c in zip(totals, correct_counts)],
            marker_color="#FC8181",
        ))
        fig_dir.update_layout(
            **_PLOTLY_LAYOUT,
            barmode="stack",
            height=280,
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
        )
        st.plotly_chart(fig_dir, width="stretch", config={"displayModeBar": False})

        # Accuracy table per direction
        dir_summary = pd.DataFrame({
            "Direction": labels,
            "Predictions": totals,
            "Correct": correct_counts,
            "Accuracy": [f"{a}%" for a in acc_vals],
        })
        st.dataframe(dir_summary, use_container_width=True, hide_index=True)

    # ── 3. Confidence calibration ────────────────────────────────────────────
    st.markdown('<div class="section-hdr">📊 Confidence Calibration</div>', unsafe_allow_html=True)
    st.caption("A well-calibrated model should show ~60% accuracy on 60% confidence predictions, ~80% on 80%, etc.")

    bins = [(0,40,"0–40%"), (40,55,"40–55%"), (55,70,"55–70%"), (70,85,"70–85%"), (85,100,"85–100%")]
    calib_rows = []
    for lo, hi, label in bins:
        in_bin = [p for p in resolved if lo <= (p.get("confidence") or 0) < hi]
        if in_bin:
            acc = round(sum(1 for p in in_bin if p["was_correct"]==1) / len(in_bin) * 100, 1)
            avg_conf = round(sum(p.get("confidence") or 0 for p in in_bin) / len(in_bin), 1)
            calib_rows.append({
                "Confidence Band": label,
                "Predictions":     len(in_bin),
                "Avg Confidence":  avg_conf,
                "Actual Accuracy": acc,
                "Gap":             round(acc - avg_conf, 1),
            })

    if calib_rows:
        df_calib = pd.DataFrame(calib_rows)

        fig_calib = go.Figure()
        fig_calib.add_trace(go.Scatter(
            x=df_calib["Avg Confidence"],
            y=df_calib["Actual Accuracy"],
            mode="lines+markers+text",
            name="Model",
            line=dict(color="#F7931A", width=2),
            marker=dict(size=12, color="#F7931A"),
            text=df_calib["Confidence Band"],
            textposition="top center",
        ))
        fig_calib.add_trace(go.Scatter(
            x=[0, 100], y=[0, 100],
            mode="lines",
            name="Perfect calibration",
            line=dict(color="#4A5568", dash="dash"),
        ))
        fig_calib.update_layout(
            **_PLOTLY_LAYOUT,
            height=300,
            xaxis_title="Model Confidence (%)",
            yaxis_title="Actual Accuracy (%)",
            xaxis=dict(**_PLOTLY_LAYOUT["xaxis"], range=[0, 105]),
            yaxis=dict(**_PLOTLY_LAYOUT["yaxis"], range=[0, 105]),
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
        )
        st.plotly_chart(fig_calib, width="stretch", config={"displayModeBar": False})
    else:
        st.caption("Not enough resolved predictions yet to calculate calibration.")

    # ── 4. Recent prediction log ─────────────────────────────────────────────
    st.markdown('<div class="section-hdr">📋 Recent Prediction Log</div>', unsafe_allow_html=True)

    recent = sorted(all_preds, key=lambda x: x.get("event_date", ""), reverse=True)[:20]
    log_rows = []
    for p in recent:
        status = (
            "✅ Correct" if p.get("was_correct") == 1
            else "❌ Wrong" if p.get("was_correct") == 0
            else "⏳ Pending"
        )
        impact_icons = {"bullish": "🟢 Bullish", "bearish": "🔴 Bearish", "neutral": "🟡 Neutral"}
        dir_icons    = {"greater": "↑ Greater", "less": "↓ Less", "equal": "→ Equal"}
        log_rows.append({
            "Date":          p.get("event_date", "")[:10],
            "Event":         p.get("event_name", ""),
            "Direction":     dir_icons.get(p.get("direction",""), p.get("direction","")),
            "Crypto":        impact_icons.get(p.get("crypto_impact",""), p.get("crypto_impact","")),
            "Confidence":    f"{int(p.get('confidence') or 0)}%",
            "Actual Value":  p.get("actual_value") or "—",
            "Result":        status,
        })
    df_log = pd.DataFrame(log_rows)
    st.dataframe(df_log, use_container_width=True, hide_index=True, height=420)

# ─── Learning loop status ─────────────────────────────────────────────────────

st.markdown('<div class="section-hdr">🔁 Learning Loop & Scheduler Status</div>', unsafe_allow_html=True)

sched = scheduler.status()
c1, c2, c3 = st.columns(3)
with c1:
    color = "#48BB78" if sched["running"] else "#FC8181"
    st.markdown(
        f'<div class="metric-card">'
        f'<div class="metric-val" style="color:{color};font-size:20px;">'
        f'{"🟢 Running" if sched["running"] else "🔴 Stopped"}'
        f'</div><div class="metric-label">Auto-Refresh Scheduler</div></div>',
        unsafe_allow_html=True,
    )
with c2:
    st.markdown(
        f'<div class="metric-card">'
        f'<div class="metric-val" style="font-size:24px;">{sched["run_count"]}</div>'
        f'<div class="metric-label">Scheduler Runs</div></div>',
        unsafe_allow_html=True,
    )
with c3:
    next_in = sched.get("next_run_in")
    next_str = f"{next_in//60}m {next_in%60}s" if next_in is not None else "—"
    st.markdown(
        f'<div class="metric-card">'
        f'<div class="metric-val" style="font-size:24px;">{next_str}</div>'
        f'<div class="metric-label">Next Auto-Refresh In</div></div>',
        unsafe_allow_html=True,
    )

st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)
st.caption(
    "The learning loop automatically marks predictions correct/incorrect when actual values "
    "are published. Next time the same event type is predicted, the AI is given its accuracy "
    "rate and its specific past mistakes, allowing it to actively correct recurring errors."
)
