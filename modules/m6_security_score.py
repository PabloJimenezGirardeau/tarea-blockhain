"""
M6 - Security Score
Estimates the cost (USD/hour) of a 51% attack on Bitcoin based on live
hash rate data, and visualises how confirmation depth reduces attack
probability using Nakamoto (2008) §11.

Also includes:
  - Historical attack cost evolution (using M3 difficulty data)
  - Recommended confirmations by transaction value
  - Comparison with other blockchains
"""

import math
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from api.blockchain_client import get_latest_block, get_difficulty_adjustments

# ── Constants ──────────────────────────────────────────────────────────────────
# NiceHash SHA-256 rental price (USD per TH/s per hour) — approximate market rate
# Source: NiceHash marketplace, updated periodically
NICEHASH_PRICE_USD_PER_THS_PER_HOUR = 0.0001  # ~$0.0001/TH/s/hour

# Bitcoin block reward (BTC) + avg fees
BLOCK_REWARD_BTC = 3.125   # post-halving April 2024
AVG_FEES_BTC     = 0.05    # approximate average fees per block
BTC_PRICE_USD    = 95000   # approximate BTC price — update as needed

# Other blockchains for comparison (hashrate in TH/s, price in USD/TH/s/hour)
OTHER_CHAINS = {
    "Bitcoin":      {"hashrate_ehs": None,   "price": 0.0001,   "color": "#f97316"},
    "Bitcoin Cash": {"hashrate_ehs": 0.003,  "price": 0.0001,   "color": "#22c55e"},
    "Litecoin":     {"hashrate_ehs": 0.0008, "price": 0.00008,  "color": "#3b82f6"},
    "Bitcoin SV":   {"hashrate_ehs": 0.0001, "price": 0.0001,   "color": "#a855f7"},
}


# ── Nakamoto (2008) §11 — Attack probability ───────────────────────────────────

def attack_success_probability(q: float, z: int) -> float:
    """
    Compute the probability that an attacker with hashrate fraction q
    can successfully reverse z confirmed blocks.

    From Nakamoto (2008) §11:
    P = 1 - sum_{k=0}^{z} (e^(-lambda) * lambda^k / k!) * (1 - (q/p)^(z-k))
    where lambda = z * (q/p)

    q = attacker fraction (< 0.5 for partial attack, 0.5 for 51%)
    p = honest fraction = 1 - q
    z = number of confirmations
    """
    if q >= 0.5:
        return 1.0  # attacker with >= 50% always wins eventually
    if q <= 0:
        return 0.0

    p      = 1.0 - q
    lam    = z * (q / p)
    total  = 0.0

    for k in range(z + 1):
        poisson = math.exp(-lam) * (lam ** k) / math.factorial(k)
        total  += poisson * (1.0 - (q / p) ** (z - k))

    return max(0.0, 1.0 - total)


def confirmations_for_risk(q: float, max_risk: float) -> int:
    """Find minimum confirmations needed so attack probability < max_risk."""
    for z in range(1, 100):
        if attack_success_probability(q, z) < max_risk:
            return z
    return 100


# ── Cost calculation ───────────────────────────────────────────────────────────

def compute_attack_cost(hashrate_ehs: float) -> dict:
    """
    Compute the cost of a 51% attack given network hashrate in EH/s.
    Returns cost breakdown and related metrics.
    """
    hashrate_ths     = hashrate_ehs * 1e6   # EH/s → TH/s
    attack_ths       = hashrate_ths * 0.51  # need 51% of total

    cost_per_hour    = attack_ths * NICEHASH_PRICE_USD_PER_THS_PER_HOUR
    cost_per_day     = cost_per_hour * 24
    cost_per_block   = cost_per_hour / 6    # ~6 blocks/hour

    block_reward_usd = (BLOCK_REWARD_BTC + AVG_FEES_BTC) * BTC_PRICE_USD

    return {
        "hashrate_ehs":       hashrate_ehs,
        "attack_ths":         attack_ths,
        "cost_per_hour_usd":  cost_per_hour,
        "cost_per_day_usd":   cost_per_day,
        "cost_per_block_usd": cost_per_block,
        "block_reward_usd":   block_reward_usd,
        "roi_blocks":         cost_per_hour / block_reward_usd if block_reward_usd else 0,
    }


# ── Section renderers ──────────────────────────────────────────────────────────

def _render_live_cost(metrics: dict) -> None:
    """Section 1 — Live attack cost based on current hashrate."""
    st.subheader("💰 Current 51% Attack Cost")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Network hashrate", f"{metrics['hashrate_ehs']:.1f} EH/s")
        st.caption("Live from Mempool.space")
    with col2:
        st.metric("Attack hashrate needed", f"{metrics['attack_ths']:,.0f} TH/s")
        st.caption("51% of total network")
    with col3:
        st.metric("Cost per hour", f"${metrics['cost_per_hour_usd']:,.0f}")
        st.caption(f"At ${NICEHASH_PRICE_USD_PER_THS_PER_HOUR}/TH/s/h (NiceHash)")
    with col4:
        st.metric("Cost per day", f"${metrics['cost_per_day_usd']:,.0f}")
        st.caption("Sustained attack")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Cost per block reversed", f"${metrics['cost_per_block_usd']:,.0f}")
        st.caption("~10 min per block")
    with col2:
        st.metric("Block reward value", f"${metrics['block_reward_usd']:,.0f}")
        st.caption(f"{BLOCK_REWARD_BTC} BTC + fees at ${BTC_PRICE_USD:,}/BTC")
    with col3:
        roi = metrics['roi_blocks']
        st.metric("Blocks needed to break even", f"{roi:.1f}")
        st.caption("Attack cost vs mining reward")

    with st.expander("📐 How is this calculated?"):
        st.markdown(f"""
        **Step 1 — Hashrate needed:**
        attack_TH/s = network_TH/s × 0.51 = {metrics['hashrate_ehs']:.1f} EH/s × 10⁶ × 0.51
        = **{metrics['attack_ths']:,.0f} TH/s**

        **Step 2 — Rental cost:**
        NiceHash SHA-256 price ≈ ${NICEHASH_PRICE_USD_PER_THS_PER_HOUR}/TH/s/hour
        cost/hour = {metrics['attack_ths']:,.0f} × {NICEHASH_PRICE_USD_PER_THS_PER_HOUR}
        = **${metrics['cost_per_hour_usd']:,.0f}/hour**

        **Note:** This is a lower-bound estimate. In practice, there is not nearly
        enough SHA-256 hashrate for rent on NiceHash to execute this attack —
        the available rental capacity is orders of magnitude below what's needed.
        The cost also excludes hardware acquisition, electricity, and cooling.
        """)


def _render_confirmation_depth(q: float = 0.30) -> None:
    """
    Section 2 — Attack success probability vs confirmation depth.
    Uses Nakamoto (2008) §11 formula.
    """
    st.subheader("🔐 Confirmation Depth vs Attack Probability")

    q_slider = st.slider(
        "Attacker hashrate fraction",
        min_value=0.01, max_value=0.49, value=q, step=0.01,
        format="%.2f",
        key="m6_q",
        help="Fraction of total network hashrate controlled by attacker (< 0.5)"
    )

    z_values = list(range(0, 31))
    probs    = [attack_success_probability(q_slider, z) * 100 for z in z_values]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=z_values, y=probs,
        mode="lines+markers",
        name=f"Attacker q={q_slider:.0%}",
        line=dict(color="#ef4444", width=2.5),
        marker=dict(size=7),
        fill="tozeroy",
        fillcolor="rgba(239,68,68,0.1)",
    ))

    # Common thresholds
    for threshold, label, color in [
        (50, "50% risk", "#f97316"),
        (1,  "1% risk",  "#22c55e"),
        (0.1,"0.1% risk","#3b82f6"),
    ]:
        fig.add_hline(
            y=threshold, line_dash="dot", line_color=color,
            annotation_text=label, annotation_position="right",
            line_width=1,
        )

    fig.update_layout(
        title=f"Attack success probability vs confirmation depth  (q = {q_slider:.0%})",
        xaxis_title="Number of confirmations (z)",
        yaxis_title="Attack success probability (%)",
        yaxis=dict(range=[0, 100]),
        height=400,
        hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        "Formula from Nakamoto (2008) §11. As confirmation depth increases, "
        "the probability of a successful double-spend attack decreases exponentially. "
        "With q < 0.5, the honest chain always wins in the long run."
    )


def _render_recommended_confirmations(q: float = 0.30) -> None:
    """
    Section 3 — Recommended confirmations by transaction value.
    Inverts Nakamoto's formula: given a risk tolerance, how many confirmations?
    """
    st.subheader("📋 Recommended Confirmations by Transaction Value")

    q_val = st.session_state.get("m6_q", 0.30)

    tx_tiers = [
        ("< $100",        100,        0.10,   "Coffee, small purchase"),
        ("$100 – $1K",    1_000,      0.05,   "Electronics, services"),
        ("$1K – $10K",    10_000,     0.01,   "Large purchases"),
        ("$10K – $100K",  100_000,    0.001,  "Business transactions"),
        ("> $100K",       1_000_000,  0.0001, "High-value transfers"),
    ]

    rows = []
    for tier, value_usd, max_risk, example in tx_tiers:
        z = confirmations_for_risk(q_val, max_risk)
        cost_to_attack = value_usd / (BLOCK_REWARD_BTC * BTC_PRICE_USD) * \
                         compute_attack_cost(1.0)["cost_per_block_usd"]
        rows.append({
            "Transaction value": tier,
            "Example": example,
            "Max risk tolerance": f"{max_risk*100:.1f}%",
            "Confirmations needed": z,
            "Wait time (approx)": f"~{z * 10} min",
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.caption(
        f"Based on attacker controlling {q_val:.0%} of hashrate. "
        "Industry standard for large exchanges is 6 confirmations (~1 hour). "
        "Bitcoin Core shows transactions as 'confirmed' after 6 blocks."
    )


def _render_historical_cost(adjustments_raw: list) -> None:
    """
    Section 4 — Historical evolution of 51% attack cost.
    Uses difficulty adjustment data from M3 to reconstruct hashrate history.
    """
    st.subheader("📈 Historical 51% Attack Cost")

    if not adjustments_raw:
        st.warning("No historical data available.")
        return

    rows = []
    for item in adjustments_raw:
        try:
            if isinstance(item, (list, tuple)) and len(item) >= 3:
                ts   = int(item[0])
                diff = float(item[2])
            elif isinstance(item, dict):
                ts   = item.get("time") or item.get("timestamp")
                diff = item.get("difficulty")
                if not ts or not diff:
                    continue
                ts, diff = int(ts), float(diff)
            else:
                continue

            # Estimate hashrate from difficulty: hashrate = difficulty × 2^32 / 600
            hashrate_ths = diff * (2**32) / 600 / 1e12
            hashrate_ehs = hashrate_ths / 1e6
            cost_hour    = hashrate_ths * 0.51 * NICEHASH_PRICE_USD_PER_THS_PER_HOUR

            rows.append({
                "date":       pd.to_datetime(ts, unit="s"),
                "difficulty": diff,
                "hashrate_ehs": hashrate_ehs,
                "cost_hour":  cost_hour,
            })
        except Exception:
            continue

    if not rows:
        st.warning("Could not parse historical data.")
        return

    df = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)

    # Highlight key dates
    highlights = {
        "2017-12": ("Bitcoin ATH $20K", "#f59e0b"),
        "2021-07": ("China mining ban", "#ef4444"),
        "2024-04": ("Halving #4",       "#22c55e"),
    }

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df["date"], y=df["cost_hour"],
        mode="lines",
        name="Attack cost ($/hour)",
        line=dict(color="#3b82f6", width=2),
        fill="tozeroy",
        fillcolor="rgba(59,130,246,0.08)",
    ))

    for date_str, (label, color) in highlights.items():
        mask = df["date"].dt.strftime("%Y-%m") == date_str
        if mask.any():
            row = df[mask].iloc[0]
            fig.add_annotation(
                x=row["date"], y=row["cost_hour"],
                text=label,
                showarrow=True, arrowhead=2,
                font=dict(color=color, size=9),
                bgcolor="rgba(0,0,0,0.6)",
                bordercolor=color,
            )

    fig.update_layout(
        title="Estimated cost to 51% attack Bitcoin over time",
        xaxis_title="Date",
        yaxis_title="Attack cost (USD/hour)",
        height=400,
        hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True)

    # Key milestones
    col1, col2, col3 = st.columns(3)
    with col1:
        first = df.iloc[0]
        first_cost = first['cost_hour']
        if first_cost < 0.01:
            cost_str = f"${first_cost:.6f}/hr"
        elif first_cost < 1:
            cost_str = f"${first_cost:.4f}/hr"
        elif first_cost < 100:
            cost_str = f"${first_cost:.2f}/hr"
        else:
            cost_str = f"${first_cost:,.0f}/hr"
        st.metric("Cost in 2009", cost_str)
        st.caption(first["date"].strftime("%Y-%m-%d"))
    with col2:
        peak = df.loc[df["cost_hour"].idxmax()]
        st.metric("Peak cost", f"${peak['cost_hour']:,.0f}/hr")
        st.caption(peak["date"].strftime("%Y-%m-%d"))
    with col3:
        last = df.iloc[-1]
        st.metric("Cost today", f"${last['cost_hour']:,.0f}/hr")
        st.caption(last["date"].strftime("%Y-%m-%d"))


def _render_blockchain_comparison(btc_hashrate_ehs: float) -> None:
    """
    Section 5 — Compare 51% attack cost across blockchains.
    Shows why smaller PoW chains are more vulnerable.
    """
    st.subheader("⚖️ 51% Attack Cost — Blockchain Comparison")

    OTHER_CHAINS["Bitcoin"]["hashrate_ehs"] = btc_hashrate_ehs

    rows = []
    for chain, data in OTHER_CHAINS.items():
        hr  = data["hashrate_ehs"]
        hr_ths = hr * 1e6
        cost = hr_ths * 0.51 * data["price"]
        rows.append({
            "Blockchain":         chain,
            "Hashrate (EH/s)":    f"{hr:.4f}",
            "Attack TH/s needed": f"{hr_ths * 0.51:,.0f}",
            "Cost per hour":      f"${cost:,.0f}",
            "Cost per day":       f"${cost * 24:,.0f}",
            "Relative to BTC":    f"{cost / (OTHER_CHAINS['Bitcoin']['hashrate_ehs'] * 1e6 * 0.51 * 0.0001):.6f}x" if chain != "Bitcoin" else "1.00x",
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

    # Bar chart
    costs = [
        OTHER_CHAINS[c]["hashrate_ehs"] * 1e6 * 0.51 * OTHER_CHAINS[c]["price"]
        for c in OTHER_CHAINS
    ]
    colors = [OTHER_CHAINS[c]["color"] for c in OTHER_CHAINS]

    fig = go.Figure(go.Bar(
        x=list(OTHER_CHAINS.keys()),
        y=costs,
        marker_color=colors,
        text=[f"${c:,.0f}/hr" for c in costs],
        textposition="outside",
    ))
    fig.update_layout(
        title="51% attack cost per hour by blockchain (log scale)",
        yaxis_title="USD per hour",
        yaxis_type="log",
        height=380,
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        "Smaller PoW blockchains are orders of magnitude cheaper to attack. "
        "Bitcoin's massive hashrate makes a 51% attack economically irrational — "
        "the attacker would spend far more than they could gain."
    )


# ── Main render ────────────────────────────────────────────────────────────────

def render() -> None:
    st.header("M6 — Security Score: 51% Attack Cost")
    st.caption(
        "Estimates the cost of a 51% attack on Bitcoin using live hashrate data "
        "and visualises confirmation depth security using Nakamoto (2008) §11."
    )

    col1, col2 = st.columns([3, 1])
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        run_btn = st.button("🔒 Calculate security", key="m6_run")

    @st.cache_data(ttl=300, show_spinner=False)
    def load_data():
        block       = get_latest_block()
        adjustments = get_difficulty_adjustments()
        return block, adjustments

    if run_btn:
        load_data.clear()

    with st.spinner("Fetching live Bitcoin data…"):
        try:
            block, adjustments = load_data()
        except Exception as exc:
            st.error(f"⚠️ Could not fetch data: {exc}")
            return

    # Estimate hashrate from difficulty
    difficulty    = block["difficulty"]
    hashrate_ths  = difficulty * (2**32) / 600 / 1e12
    hashrate_ehs  = hashrate_ths / 1e6
    metrics       = compute_attack_cost(hashrate_ehs)

    st.success(
        f"Live data loaded · Block **#{block['height']:,}** · "
        f"Hashrate: **{hashrate_ehs:.1f} EH/s**"
    )

    st.divider()
    _render_live_cost(metrics)
    st.divider()
    _render_confirmation_depth()
    st.divider()
    _render_recommended_confirmations()
    st.divider()
    _render_historical_cost(adjustments)
    st.divider()
    _render_blockchain_comparison(hashrate_ehs)