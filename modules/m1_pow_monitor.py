"""
M1 - Proof of Work Monitor
Displays live Bitcoin mining metrics, inter-block time distribution,
nonce distribution, and next difficulty adjustment estimate.
Auto-refreshes every 60 seconds.
"""

import time
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st
import streamlit.components.v1 as components

from api.blockchain_client import get_latest_block, get_blocks_paginated

# ── Constants ──────────────────────────────────────────────────────────────────
BLOCK_TIME_TARGET = 600        # 10 minutes in seconds
ADJUSTMENT_PERIOD = 2016       # blocks between difficulty adjustments
NONCE_MAX         = 2**32      # nonces live in [0, 2^32)
BLOCKS_TO_FETCH   = 50         # how many recent blocks to analyse


# ── Cryptographic helpers ──────────────────────────────────────────────────────

def count_leading_zero_bits(hash_hex: str) -> int:
    hash_int = int(hash_hex, 16)
    if hash_int == 0:
        return 256
    return 256 - hash_int.bit_length()


def estimate_hashrate(difficulty: float) -> float:
    return difficulty * (2**32) / BLOCK_TIME_TARGET


def bits_to_target_hex(bits: int) -> str:
    exponent = bits >> 24
    mantissa = bits & 0x007FFFFF
    target   = mantissa * (2 ** (8 * (exponent - 3)))
    return f"{target:064x}"


# ── Section renderers ──────────────────────────────────────────────────────────

def _render_live_metrics(block: dict) -> None:
    st.subheader("📡 Live Network State")

    difficulty = block["difficulty"]
    hash_hex   = block["id"]
    bits       = block["bits"]

    hashrate_hs  = estimate_hashrate(difficulty)
    hashrate_ehs = hashrate_hs / 1e18
    leading_zeros = count_leading_zero_bits(hash_hex)

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("⛏️ Difficulty", f"{difficulty:,.0f}")
        st.caption("How many times harder than block #1")

    with col2:
        st.metric("🔥 Est. Hash Rate", f"{hashrate_ehs:.2f} EH/s")
        st.caption("Network hashes per second · difficulty × 2³² / 600")

    with col3:
        st.metric("🔢 Leading Zero Bits", f"{leading_zeros} / 256")
        st.caption("Bits forced to 0 in the latest block hash")

    with st.expander("🔍 Latest block details"):
        st.write(f"**Height:** {block['height']:,}")
        st.write(f"**Hash:** `{hash_hex}`")
        st.write(f"**Bits (compact target):** `{bits:#010x}`")
        st.write(f"**Full target threshold:** `{bits_to_target_hex(bits)}`")
        st.write(f"**Nonce:** {block['nonce']:,}")
        st.write(f"**Transactions:** {block['tx_count']:,}")


def _render_256bit_visual(block: dict) -> None:
    st.subheader("🎯 SHA-256 Target Threshold (256-bit space)")

    leading_zeros = count_leading_zero_bits(block["id"])
    free_bits     = 256 - leading_zeros

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=[leading_zeros],
        y=["256-bit hash space"],
        orientation="h",
        name=f"Must be 0  ({leading_zeros} bits)",
        marker_color="#ef4444",
        text=f"{leading_zeros} zero bits",
        textposition="inside",
    ))
    fig.add_trace(go.Bar(
        x=[free_bits],
        y=["256-bit hash space"],
        orientation="h",
        name=f"Free bits  ({free_bits} bits)",
        marker_color="#22c55e",
        text=f"{free_bits} free bits",
        textposition="inside",
    ))

    fig.update_layout(
        barmode="stack",
        title="Leading zero bits required by current difficulty",
        xaxis=dict(title="Bits (out of 256)", range=[0, 256]),
        yaxis=dict(showticklabels=False),
        legend=dict(orientation="h", y=-0.3),
        height=200,
        margin=dict(t=40, b=60, l=20, r=20),
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        "A valid block hash must start with at least "
        f"**{leading_zeros} zero bits** out of 256. "
        "Miners iterate the nonce until they find a hash that satisfies this constraint."
    )


def _render_interblock_times(blocks: list[dict]) -> None:
    st.subheader("⏱️ Inter-Block Time Distribution")

    timestamps = sorted([b["timestamp"] for b in blocks])
    deltas     = np.diff(timestamps)

    if len(deltas) < 5:
        st.warning("Not enough blocks to plot distribution.")
        return

    mean_delta = float(np.mean(deltas))
    lam        = 1.0 / BLOCK_TIME_TARGET

    x_theory = np.linspace(0, max(deltas) * 1.1, 300)
    y_theory = lam * np.exp(-lam * x_theory)
    n_bins    = 20
    bin_width = (max(deltas) - min(deltas)) / n_bins
    y_theory_scaled = y_theory * len(deltas) * bin_width

    fig = go.Figure()

    fig.add_trace(go.Histogram(
        x=deltas,
        nbinsx=n_bins,
        name="Observed inter-block times",
        marker_color="#3b82f6",
        opacity=0.7,
    ))

    fig.add_trace(go.Scatter(
        x=x_theory,
        y=y_theory_scaled,
        mode="lines",
        name="Exponential(λ=1/600) — theory",
        line=dict(color="#f97316", width=2, dash="dash"),
    ))

    fig.add_vline(
        x=BLOCK_TIME_TARGET,
        line_dash="dot",
        line_color="gray",
        annotation_text="Target: 600 s",
        annotation_position="top right",
    )

    fig.update_layout(
        title=f"Inter-block times — last {len(blocks)} blocks  |  mean = {mean_delta:.0f} s",
        xaxis_title="Time between blocks (seconds)",
        yaxis_title="Count",
        legend=dict(orientation="h", y=-0.3),
        height=400,
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        "Bitcoin mining is a memoryless process — each hash attempt is independent. "
        "This makes block arrival times follow a **Poisson process**, whose inter-arrival "
        "times are **exponentially distributed** with λ = 1/600 s⁻¹. "
        "The network adjusts difficulty every 2016 blocks to keep the mean near 600 s."
    )


def _render_nonce_distribution(blocks: list[dict]) -> None:
    st.subheader("🎲 Nonce Distribution")

    nonces  = [b["nonce"] for b in blocks]
    heights = [b["height"] for b in blocks]

    col1, col2 = st.columns(2)

    with col1:
        fig_scatter = go.Figure(go.Scatter(
            x=heights,
            y=nonces,
            mode="markers",
            marker=dict(color="#8b5cf6", size=6, opacity=0.8),
            name="Nonce",
        ))
        fig_scatter.add_hline(
            y=NONCE_MAX / 2,
            line_dash="dot",
            line_color="gray",
            annotation_text="Midpoint (2³¹)",
        )
        fig_scatter.update_layout(
            title="Nonce value per block",
            xaxis_title="Block height",
            yaxis_title="Nonce value",
            yaxis=dict(range=[0, NONCE_MAX]),
            height=350,
        )
        st.plotly_chart(fig_scatter, use_container_width=True)

    with col2:
        fig_hist = go.Figure(go.Histogram(
            x=nonces,
            nbinsx=16,
            marker_color="#8b5cf6",
            opacity=0.8,
            name="Nonce frequency",
        ))
        fig_hist.update_layout(
            title="Nonce frequency distribution",
            xaxis_title="Nonce value (0 – 2³²)",
            yaxis_title="Count",
            height=350,
        )
        st.plotly_chart(fig_hist, use_container_width=True)

    st.caption(
        "The nonce is a 32-bit integer (0 – 4,294,967,295) that miners increment "
        "until SHA256(SHA256(header)) < target. If the full nonce space is exhausted "
        "without finding a valid hash, miners change the **extra nonce** in the coinbase "
        "transaction, effectively restarting the search space."
    )


def _render_next_adjustment(block: dict, blocks: list[dict]) -> None:
    st.subheader("📅 Next Difficulty Adjustment")

    height           = block["height"]
    blocks_since_adj = height % ADJUSTMENT_PERIOD
    blocks_remaining = ADJUSTMENT_PERIOD - blocks_since_adj

    timestamps    = sorted([b["timestamp"] for b in blocks])
    deltas        = np.diff(timestamps)
    avg_blocktime = float(np.mean(deltas)) if len(deltas) > 0 else BLOCK_TIME_TARGET

    eta_seconds = blocks_remaining * avg_blocktime
    eta_hours   = eta_seconds / 3600
    eta_days    = eta_hours / 24

    projected_period = avg_blocktime * ADJUSTMENT_PERIOD
    expected_period  = BLOCK_TIME_TARGET * ADJUSTMENT_PERIOD
    adj_ratio        = projected_period / expected_period
    adj_pct          = (adj_ratio - 1) * 100

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Blocks remaining", f"{blocks_remaining:,}")
        st.caption(f"Out of 2016 — currently at block {blocks_since_adj} in this period")
    with col2:
        st.metric("Estimated ETA", f"{eta_days:.1f} days")
        st.caption(f"≈ {eta_hours:.0f} hours based on recent avg {avg_blocktime:.0f} s/block")
    with col3:
        direction = "⬆️ increase" if adj_pct > 0 else "⬇️ decrease"
        st.metric("Projected Δ difficulty", f"{adj_pct:+.1f}%")
        st.caption(
            f"Difficulty will {direction} if blocks keep arriving every {avg_blocktime:.0f} s "
            f"(target is {BLOCK_TIME_TARGET} s)"
        )

    progress = blocks_since_adj / ADJUSTMENT_PERIOD
    st.progress(progress, text=f"Period progress: {blocks_since_adj}/{ADJUSTMENT_PERIOD} blocks ({progress*100:.1f}%)")


# ── Main render ────────────────────────────────────────────────────────────────

def render() -> None:
    st.header("M1 — Proof of Work Monitor")
    st.caption("Live Bitcoin mining metrics · auto-refreshes every 60 seconds")

    col_refresh, col_btn = st.columns([3, 1])
    with col_refresh:
        auto_refresh = st.toggle("Auto-refresh (60 s)", value=True, key="m1_auto_refresh")
    with col_btn:
        manual = st.button("🔄 Refresh now", key="m1_manual_refresh")

    @st.cache_data(ttl=60, show_spinner=False)
    def load_data():
        block  = get_latest_block()
        blocks = get_blocks_paginated(BLOCKS_TO_FETCH)
        return block, blocks

    if manual:
        load_data.clear()

    with st.spinner("Fetching live Bitcoin data…"):
        try:
            block, blocks = load_data()
        except Exception as exc:
            st.error(f"⚠️ Could not fetch data: {exc}")
            return

    _render_live_metrics(block)
    st.divider()
    _render_256bit_visual(block)
    st.divider()
    _render_interblock_times(blocks)
    st.divider()
    _render_nonce_distribution(blocks)
    st.divider()
    _render_next_adjustment(block, blocks)

    # ── Auto-refresh via JavaScript (no bloquea otros tabs) ───────────────────
    if auto_refresh:
        components.html(
            "<script>setTimeout(function(){window.location.reload();}, 60000);</script>",
            height=0,
        )