"""
M3 - Difficulty History
Plots the evolution of Bitcoin mining difficulty over time, marks each
adjustment event, shows the ratio between actual and target block time,
and applies the adjustment formula from Section 6.1 of the course notes.
"""

import datetime
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

from api.blockchain_client import get_difficulty_history, get_difficulty_adjustments

# ── Constants ──────────────────────────────────────────────────────────────────
TARGET_BLOCK_TIME  = 600          # seconds (10 minutes)
ADJUSTMENT_PERIOD  = 2016         # blocks
EXPECTED_PERIOD_S  = TARGET_BLOCK_TIME * ADJUSTMENT_PERIOD  # 1,209,600 s ≈ 2 weeks

TIMESPAN_OPTIONS = {
    "30 days":  30,
    "3 months": 90,
    "6 months": 180,
    "1 year":   365,
}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _build_history_df(values: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(values)
    df["date"] = pd.to_datetime(df["x"], unit="s")
    df = df.rename(columns={"y": "difficulty"})
    df = df[["date", "difficulty"]].sort_values("date").reset_index(drop=True)
    return df


def _build_adjustments_df(adjustments: list) -> pd.DataFrame:
    """
    Parse the Mempool.space difficulty-adjustments response.
    The endpoint returns a list of arrays: [timestamp, height, difficulty, adjustment_ratio]
    """
    rows = []
    for item in adjustments:
        try:
            if isinstance(item, (list, tuple)) and len(item) >= 4:
                ts, height, difficulty, ratio = item[0], item[1], item[2], item[3]
            elif isinstance(item, dict):
                ts         = item.get("time") or item.get("timestamp")
                height     = item.get("height")
                difficulty = item.get("difficulty")
                ratio      = item.get("adjustment") or item.get("ratio") or 1.0
            else:
                continue
            rows.append({
                "date":       pd.to_datetime(ts, unit="s"),
                "height":     int(height),
                "difficulty": float(difficulty),
                "ratio":      float(ratio),
                "change_pct": (float(ratio) - 1) * 100,
            })
        except Exception:
            continue

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("date").reset_index(drop=True)
    return df


# ── Section renderers ──────────────────────────────────────────────────────────

def _render_difficulty_chart(hist_df: pd.DataFrame, adj_df: pd.DataFrame) -> None:
    """Section 1 + 2 — Difficulty over time with adjustment event markers."""
    st.subheader("📈 Bitcoin Difficulty History")

    fig = go.Figure()

    # Main difficulty line
    fig.add_trace(go.Scatter(
        x=hist_df["date"],
        y=hist_df["difficulty"],
        mode="lines",
        name="Difficulty",
        line=dict(color="#3b82f6", width=2),
        fill="tozeroy",
        fillcolor="rgba(59,130,246,0.08)",
    ))

    # Mark adjustment events within the visible date range
    if not adj_df.empty:
        visible_adj = adj_df[
            (adj_df["date"] >= hist_df["date"].min()) &
            (adj_df["date"] <= hist_df["date"].max())
        ]
        for _, row in visible_adj.iterrows():
            color = "#22c55e" if row["change_pct"] >= 0 else "#ef4444"
            fig.add_vline(
                x=row["date"].timestamp() * 1000,  # Plotly expects ms
                line_dash="dot",
                line_color=color,
                line_width=1,
                annotation_text=f"{row['change_pct']:+.1f}%",
                annotation_font_size=9,
                annotation_font_color=color,
                annotation_position="top",
            )

    # Annotate biggest increase and biggest drop
    if not adj_df.empty and not visible_adj.empty:
        max_row = visible_adj.loc[visible_adj["change_pct"].idxmax()]
        min_row = visible_adj.loc[visible_adj["change_pct"].idxmin()]

        for row, symbol, label_color in [(max_row, "▲ Max increase", "#22c55e"),
                                          (min_row, "▼ Max drop", "#ef4444")]:
            # Find closest difficulty value in history
            closest = hist_df.iloc[(hist_df["date"] - row["date"]).abs().argsort()[:1]]
            if not closest.empty:
                fig.add_annotation(
                    x=row["date"],
                    y=closest["difficulty"].values[0],
                    text=f"{symbol}<br>{row['change_pct']:+.1f}%",
                    showarrow=True,
                    arrowhead=2,
                    font=dict(color=label_color, size=10),
                    bgcolor="rgba(0,0,0,0.6)",
                    bordercolor=label_color,
                )

    fig.update_layout(
        title="Bitcoin mining difficulty over time · green = increase, red = decrease",
        xaxis_title="Date",
        yaxis_title="Difficulty",
        legend=dict(orientation="h", y=-0.2),
        height=450,
        hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        "Each vertical line marks a difficulty adjustment event (every 2016 blocks ≈ 2 weeks). "
        "Green = difficulty increased (blocks were arriving too fast). "
        "Red = difficulty decreased (blocks were arriving too slow)."
    )


def _render_ratio_chart(adj_df: pd.DataFrame, hist_df: pd.DataFrame) -> None:
    """
    Section 3 — Ratio between actual block time and target (600 s).
    ratio = actual_period_time / expected_period_time
    ratio > 1 → miners were slower than target → difficulty decreases
    ratio < 1 → miners were faster than target → difficulty increases
    This directly implements the formula from Section 6.1 of the notes.
    """
    st.subheader("⚖️ Actual Block Time vs Target (600 s)")

    if adj_df.empty:
        st.warning("No adjustment data available.")
        return

    # Filter to visible range
    visible = adj_df[
        (adj_df["date"] >= hist_df["date"].min()) &
        (adj_df["date"] <= hist_df["date"].max())
    ].copy()

    if visible.empty:
        st.warning("No adjustments in the selected time range.")
        return

    # ratio column already present; compute avg block time from it
    # actual_period = ratio × expected_period → avg_block_time = ratio × 600
    visible["avg_block_time"] = visible["ratio"] * TARGET_BLOCK_TIME

    colors = ["#22c55e" if abs(r - 1) < 0.05 else
              "#f59e0b" if abs(r - 1) < 0.15 else
              "#ef4444"
              for r in visible["ratio"]]

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=visible["date"],
        y=visible["ratio"],
        marker_color=colors,
        name="Actual / Target ratio",
        text=[f"{r:.3f}" for r in visible["ratio"]],
        textposition="outside",
    ))

    fig.add_hline(
        y=1.0,
        line_dash="dash",
        line_color="white",
        annotation_text="Target ratio = 1.0 (600 s/block)",
        annotation_position="bottom right",
    )

    fig.update_layout(
        title="Block time ratio per adjustment period  (1.0 = perfect target)",
        xaxis_title="Adjustment date",
        yaxis_title="Ratio (actual / target)",
        height=380,
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        "A ratio > 1 means blocks took longer than 600 s on average → "
        "difficulty **decreases** at the next adjustment. "
        "A ratio < 1 means blocks were faster → difficulty **increases**."
    )


def _render_adjustment_formula(adj_df: pd.DataFrame, hist_df: pd.DataFrame) -> None:
    """
    Section 4 — Adjustment formula from Section 6.1 of the course notes.
    new_difficulty = old_difficulty × (actual_time / expected_time)
    Shows predicted vs actual difficulty for each period.
    """
    st.subheader("🧮 Adjustment Formula (Section 6.1)")

    st.latex(r"""
        D_{new} = D_{old} \times \frac{t_{actual}}{t_{expected}}
        \quad \text{where} \quad t_{expected} = 2016 \times 600 = 1{,}209{,}600 \text{ s}
    """)

    st.caption(
        "This formula is capped at ×4 / ×0.25 to prevent extreme jumps. "
        "Bitcoin enforces: `0.25 ≤ adjustment_ratio ≤ 4.0`"
    )

    if adj_df.empty or len(adj_df) < 2:
        st.warning("Not enough adjustment data to show formula application.")
        return

    visible = adj_df[
        (adj_df["date"] >= hist_df["date"].min()) &
        (adj_df["date"] <= hist_df["date"].max())
    ].copy().reset_index(drop=True)

    if len(visible) < 2:
        st.warning("Not enough adjustments in the selected range.")
        return

    rows = []
    for i in range(1, len(visible)):
        prev = visible.iloc[i - 1]
        curr = visible.iloc[i]
        predicted = prev["difficulty"] * prev["ratio"]
        actual    = curr["difficulty"]
        error_pct = ((actual - predicted) / predicted) * 100 if predicted else 0
        rows.append({
            "Date":           curr["date"].strftime("%Y-%m-%d"),
            "Height":         f"{curr['height']:,}",
            "Old difficulty": f"{prev['difficulty']:,.0f}",
            "Ratio":          f"{prev['ratio']:.4f}",
            "Predicted D":    f"{predicted:,.0f}",
            "Actual D":       f"{actual:,.0f}",
            "Error":          f"{error_pct:+.2f}%",
            "Change":         f"{curr['change_pct']:+.1f}%",
        })

    df_table = pd.DataFrame(rows).tail(10)
    st.dataframe(df_table, use_container_width=True, hide_index=True)
    st.caption(
        "Predicted D = Old difficulty × Ratio. "
        "Small errors come from rounding and the ×4/×0.25 cap."
    )


def _render_summary_stats(adj_df: pd.DataFrame, hist_df: pd.DataFrame) -> None:
    """Section 5 — Quick summary metrics for the selected period."""
    st.subheader("📊 Period Summary")

    visible = adj_df[
        (adj_df["date"] >= hist_df["date"].min()) &
        (adj_df["date"] <= hist_df["date"].max())
    ]

    if visible.empty:
        return

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Adjustments", f"{len(visible)}")
        st.caption("In selected period")
    with col2:
        increases = (visible["change_pct"] > 0).sum()
        st.metric("Increases", f"{increases}")
        st.caption(f"vs {len(visible) - increases} decreases")
    with col3:
        st.metric("Largest increase", f"{visible['change_pct'].max():+.1f}%")
        st.caption(visible.loc[visible['change_pct'].idxmax(), 'date'].strftime("%Y-%m-%d"))
    with col4:
        st.metric("Largest drop", f"{visible['change_pct'].min():+.1f}%")
        st.caption(visible.loc[visible['change_pct'].idxmin(), 'date'].strftime("%Y-%m-%d"))


# ── Main render ────────────────────────────────────────────────────────────────

def render() -> None:
    st.header("M3 — Difficulty History")
    st.caption("Bitcoin mining difficulty evolution · adjustment periods · block time ratio")

    # ── Time range selector ────────────────────────────────────────────────────
    col1, col2 = st.columns([2, 1])
    with col1:
        timespan_label = st.select_slider(
            "Time range",
            options=list(TIMESPAN_OPTIONS.keys()),
            value="1 year",
            key="m3_timespan",
        )
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        load_btn = st.button("📥 Load data", key="m3_load")

    n_points = TIMESPAN_OPTIONS[timespan_label]

    # ── Data loading ───────────────────────────────────────────────────────────
    @st.cache_data(ttl=3600, show_spinner=False)
    def load_history(n: int):
        return get_difficulty_history(n)

    @st.cache_data(ttl=3600, show_spinner=False)
    def load_adjustments():
        return get_difficulty_adjustments()

    if load_btn:
        load_history.clear()
        load_adjustments.clear()

    with st.spinner("Fetching difficulty data…"):
        try:
            history_raw     = load_history(n_points)
            adjustments_raw = load_adjustments()
        except Exception as exc:
            st.error(f"⚠️ Could not fetch data: {exc}")
            return

    if not history_raw:
        st.warning("No difficulty history data returned.")
        return

    hist_df = _build_history_df(history_raw)
    adj_df  = _build_adjustments_df(adjustments_raw) if adjustments_raw else pd.DataFrame()

    st.success(
        f"Loaded {len(hist_df)} difficulty data points · "
        f"{len(adj_df)} adjustment events"
    )

    # ── Render sections ────────────────────────────────────────────────────────
    st.divider()
    _render_difficulty_chart(hist_df, adj_df)
    st.divider()
    _render_ratio_chart(adj_df, hist_df)
    st.divider()
    _render_adjustment_formula(adj_df, hist_df)
    st.divider()
    _render_summary_stats(adj_df, hist_df)