"""
M4 - AI Component: Anomaly Detector
Detects statistically abnormal inter-block times using an exponential
distribution baseline. Lambda is estimated via Maximum Likelihood Estimation
(MLE) from the data rather than assumed as 1/600.

Anomaly types:
  - Fast block  (< p5):  possible mining pool advantage or empty block
  - Slow block  (> p95): possible hashrate drop or network disruption

Also includes a rolling-window lambda estimator for adaptive detection.
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from scipy import stats

from api.blockchain_client import get_blocks_paginated

# ── Constants ──────────────────────────────────────────────────────────────────
TARGET_BLOCK_TIME  = 600       # seconds — theoretical mean
BLOCKS_TO_FETCH    = 150       # more blocks → better statistical baseline
ROLLING_WINDOW     = 10        # blocks for rolling lambda estimation
LOWER_PERCENTILE   = 5         # below this → fast anomaly
UPPER_PERCENTILE   = 95        # above this → slow anomaly


# ── Statistical helpers ────────────────────────────────────────────────────────

def compute_interblock_times(blocks: list[dict]) -> pd.DataFrame:
    """
    Sort blocks by timestamp and compute inter-block times in seconds.
    Returns a DataFrame with columns: height, timestamp, delta_s.
    """
    df = pd.DataFrame([{
        "height":    b["height"],
        "timestamp": b["timestamp"],
    } for b in blocks])
    df = df.sort_values("timestamp").reset_index(drop=True)
    df["delta_s"] = df["timestamp"].diff()
    df = df.dropna(subset=["delta_s"])
    df = df[df["delta_s"] > 0].reset_index(drop=True)
    return df


def estimate_lambda_mle(deltas: np.ndarray) -> float:
    """
    Maximum Likelihood Estimation of lambda for an exponential distribution.
    For Exp(lambda), MLE is: lambda_hat = 1 / mean(x)
    This is more accurate than assuming lambda = 1/600 when data deviates
    from the theoretical target.
    """
    return 1.0 / np.mean(deltas)


def exponential_cdf(x: float, lam: float) -> float:
    """CDF of Exp(lambda): P(X <= x) = 1 - exp(-lambda * x)"""
    return 1.0 - np.exp(-lam * x)


def classify_anomaly(percentile: float) -> str:
    """Classify a block as normal, fast anomaly, or slow anomaly."""
    if percentile < LOWER_PERCENTILE:
        return "fast"
    elif percentile > UPPER_PERCENTILE:
        return "slow"
    return "normal"


def compute_rolling_lambda(df: pd.DataFrame, window: int) -> pd.Series:
    """
    Compute a rolling MLE lambda using a sliding window of `window` blocks.
    Adapts to local changes in hashrate rather than using a single global lambda.
    """
    return df["delta_s"].rolling(window=window, min_periods=3).apply(
        lambda x: 1.0 / np.mean(x), raw=True
    )


def add_anomaly_columns(df: pd.DataFrame, lam_global: float) -> pd.DataFrame:
    """
    Add percentile, anomaly type, and rolling lambda columns to the DataFrame.
    """
    df = df.copy()
    df["percentile"]      = df["delta_s"].apply(
        lambda x: exponential_cdf(x, lam_global) * 100
    )
    df["anomaly_type"]    = df["percentile"].apply(classify_anomaly)
    df["rolling_lambda"]  = compute_rolling_lambda(df, ROLLING_WINDOW)
    df["rolling_mean_bt"] = 1.0 / df["rolling_lambda"]  # seconds
    return df


# ── Section renderers ──────────────────────────────────────────────────────────

def _render_model_explanation(lam_mle: float, lam_theory: float, n: int) -> None:
    """Section 1 — Model description and MLE vs theoretical lambda."""
    st.subheader("🤖 Anomaly Detection Model")

    st.markdown("""
    **Approach:** Exponential distribution baseline with MLE parameter estimation.

    Bitcoin block arrival is a **memoryless Poisson process** — each hash attempt
    is independent of the previous ones. This means inter-block times follow an
    **exponential distribution** with rate parameter λ.

    A block is flagged as **anomalous** if its inter-block time falls outside the
    central 90% of that distribution (below percentile 5 or above percentile 95).
    """)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("λ (MLE from data)", f"{lam_mle:.6f} s⁻¹")
        st.caption("Estimated from actual block times")
    with col2:
        st.metric("λ (theoretical)", f"{lam_theory:.6f} s⁻¹")
        st.caption("= 1/600, the target")
    with col3:
        mean_bt = 1.0 / lam_mle
        st.metric("Estimated mean block time", f"{mean_bt:.1f} s")
        st.caption(f"vs target {TARGET_BLOCK_TIME} s")
    with col4:
        st.metric("Blocks analysed", f"{n}")
        st.caption("Sample size for MLE")

    deviation = abs(lam_mle - lam_theory) / lam_theory * 100
    if deviation > 10:
        st.warning(
            f"⚠️ MLE λ deviates {deviation:.1f}% from the theoretical value. "
            "The network may be running faster or slower than the 10-minute target. "
            "Using MLE ensures the anomaly detector adapts to actual conditions."
        )
    else:
        st.success(
            f"✅ MLE λ is within {deviation:.1f}% of the theoretical value — "
            "the network is running close to the 10-minute target."
        )

    with st.expander("📐 Why MLE instead of 1/600?"):
        st.markdown("""
        Using a **fixed** λ = 1/600 assumes the network always hits the target
        exactly. In practice, between difficulty adjustments the actual block time
        can differ. MLE estimates λ **from the observed data**, making the anomaly
        threshold adaptive and statistically correct for the current network state.

        **MLE for Exp(λ):**  λ̂ = 1 / x̄  (reciprocal of the sample mean)

        This is the minimum-variance unbiased estimator for the exponential rate.
        """)


def _render_timeline(df: pd.DataFrame) -> None:
    """Section 2 — Timeline of inter-block times with anomalies highlighted."""
    st.subheader("📊 Inter-Block Times — Anomaly Timeline")

    normal = df[df["anomaly_type"] == "normal"]
    fast   = df[df["anomaly_type"] == "fast"]
    slow   = df[df["anomaly_type"] == "slow"]

    fig = go.Figure()

    # Normal blocks
    fig.add_trace(go.Scatter(
        x=normal["height"], y=normal["delta_s"],
        mode="markers",
        name="Normal",
        marker=dict(color="#3b82f6", size=6, opacity=0.7),
    ))

    # Fast anomalies
    if not fast.empty:
        fig.add_trace(go.Scatter(
            x=fast["height"], y=fast["delta_s"],
            mode="markers",
            name=f"Fast anomaly (< p{LOWER_PERCENTILE})",
            marker=dict(color="#f97316", size=10, symbol="triangle-up",
                        line=dict(width=1, color="#ea580c")),
        ))

    # Slow anomalies
    if not slow.empty:
        fig.add_trace(go.Scatter(
            x=slow["height"], y=slow["delta_s"],
            mode="markers",
            name=f"Slow anomaly (> p{UPPER_PERCENTILE})",
            marker=dict(color="#ef4444", size=10, symbol="triangle-down",
                        line=dict(width=1, color="#dc2626")),
        ))

    # Rolling mean block time
    fig.add_trace(go.Scatter(
        x=df["height"], y=df["rolling_mean_bt"],
        mode="lines",
        name=f"Rolling mean ({ROLLING_WINDOW}-block window)",
        line=dict(color="#22c55e", width=2, dash="dash"),
    ))

    # Target line
    fig.add_hline(
        y=TARGET_BLOCK_TIME,
        line_dash="dot", line_color="white", line_width=1,
        annotation_text="Target: 600 s",
        annotation_position="bottom right",
    )

    fig.update_layout(
        title=f"Inter-block times — last {len(df)} blocks",
        xaxis_title="Block height",
        yaxis_title="Time since previous block (seconds)",
        legend=dict(orientation="h", y=-0.25),
        height=430,
        hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        "🟠 Fast anomaly: block arrived unusually quickly — possible mining pool "
        "with hashrate advantage or intentionally empty block. "
        "🔴 Slow anomaly: block took much longer than expected — possible hashrate "
        "drop, network disruption, or gap between pool rounds."
    )


def _render_distribution(df: pd.DataFrame, lam_mle: float) -> None:
    """Section 3 — Empirical distribution vs theoretical with anomaly thresholds."""
    st.subheader("📈 Distribution vs Exponential Baseline")

    deltas = df["delta_s"].values
    x_max  = np.percentile(deltas, 99) * 1.2
    x_line = np.linspace(0, x_max, 400)

    # Theoretical PDF scaled to histogram area
    n_bins    = 25
    bin_width = x_max / n_bins
    pdf_vals  = lam_mle * np.exp(-lam_mle * x_line) * len(deltas) * bin_width

    # Anomaly thresholds
    lower_thresh = -np.log(1 - LOWER_PERCENTILE / 100) / lam_mle
    upper_thresh = -np.log(1 - UPPER_PERCENTILE / 100) / lam_mle

    fig = go.Figure()

    # Histogram
    fig.add_trace(go.Histogram(
        x=deltas, nbinsx=n_bins,
        name="Observed inter-block times",
        marker_color="#3b82f6", opacity=0.65,
    ))

    # Theoretical PDF
    fig.add_trace(go.Scatter(
        x=x_line, y=pdf_vals,
        mode="lines",
        name=f"Exp(λ={lam_mle:.5f}) — MLE fit",
        line=dict(color="#22c55e", width=2.5),
    ))

    # Anomaly zones
    fig.add_vrect(
        x0=0, x1=lower_thresh,
        fillcolor="#f97316", opacity=0.12,
        layer="below", line_width=0,
        annotation_text=f"Fast zone\n(< {lower_thresh:.0f} s)",
        annotation_position="top left",
        annotation_font_color="#f97316",
    )
    fig.add_vrect(
        x0=upper_thresh, x1=x_max,
        fillcolor="#ef4444", opacity=0.12,
        layer="below", line_width=0,
        annotation_text=f"Slow zone\n(> {upper_thresh:.0f} s)",
        annotation_position="top right",
        annotation_font_color="#ef4444",
    )

    fig.add_vline(x=lower_thresh, line_dash="dash", line_color="#f97316",
                  annotation_text=f"p{LOWER_PERCENTILE}", line_width=1.5)
    fig.add_vline(x=upper_thresh, line_dash="dash", line_color="#ef4444",
                  annotation_text=f"p{UPPER_PERCENTILE}", line_width=1.5)
    fig.add_vline(x=TARGET_BLOCK_TIME, line_dash="dot", line_color="white",
                  annotation_text="600 s target", line_width=1)

    fig.update_layout(
        title="Empirical distribution vs MLE exponential fit",
        xaxis_title="Inter-block time (seconds)",
        yaxis_title="Count",
        legend=dict(orientation="h", y=-0.25),
        height=400,
        xaxis=dict(range=[0, x_max]),
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_anomaly_table(df: pd.DataFrame) -> None:
    """Section 4 — Table of detected anomalous blocks."""
    st.subheader("🚨 Detected Anomalies")

    anomalies = df[df["anomaly_type"] != "normal"].copy()

    if anomalies.empty:
        st.success("✅ No anomalies detected in the analysed blocks.")
        return

    fast_count = (anomalies["anomaly_type"] == "fast").sum()
    slow_count = (anomalies["anomaly_type"] == "slow").sum()
    total      = len(df)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total anomalies", f"{len(anomalies)} / {total}")
        st.caption(f"Detection rate: {len(anomalies)/total*100:.1f}%")
    with col2:
        st.metric("🟠 Fast anomalies", f"{fast_count}")
        st.caption(f"Below p{LOWER_PERCENTILE} threshold")
    with col3:
        st.metric("🔴 Slow anomalies", f"{slow_count}")
        st.caption(f"Above p{UPPER_PERCENTILE} threshold")

    display = anomalies[[
        "height", "delta_s", "percentile", "anomaly_type"
    ]].copy()
    display.columns = ["Block height", "Inter-block time (s)", "Percentile", "Type"]
    display["Inter-block time (s)"] = display["Inter-block time (s)"].round(1)
    display["Percentile"]           = display["Percentile"].round(2)
    display["Type"] = display["Type"].map({
        "fast": "🟠 Fast",
        "slow": "🔴 Slow",
    })
    display = display.sort_values("Percentile").reset_index(drop=True)

    st.dataframe(display, use_container_width=True, hide_index=True)


def _render_metrics(df: pd.DataFrame, lam_mle: float) -> None:
    """Section 5 — Model evaluation metrics."""
    st.subheader("📐 Model Evaluation Metrics")

    deltas       = df["delta_s"].values
    n            = len(deltas)
    anomalies    = df[df["anomaly_type"] != "normal"]
    detection_rate = len(anomalies) / n * 100

    lower_thresh = -np.log(1 - LOWER_PERCENTILE / 100) / lam_mle
    upper_thresh = -np.log(1 - UPPER_PERCENTILE / 100) / lam_mle

    # KS test: how well does the exponential fit the data?
    ks_stat, ks_pval = stats.kstest(deltas, "expon", args=(0, 1/lam_mle))

    col1, col2 = st.columns(2)
    with col1:
        metrics_data = {
            "Metric": [
                "Sample size (n)",
                "MLE λ",
                "Estimated mean block time",
                "Lower threshold (p5)",
                "Upper threshold (p95)",
                "Detection rate",
                "Fast anomalies",
                "Slow anomalies",
                "KS statistic",
                "KS p-value",
            ],
            "Value": [
                str(n),
                f"{lam_mle:.6f} s⁻¹",
                f"{1/lam_mle:.1f} s",
                f"{lower_thresh:.1f} s",
                f"{upper_thresh:.1f} s",
                f"{detection_rate:.1f}%",
                str((df["anomaly_type"] == "fast").sum()),
                str((df["anomaly_type"] == "slow").sum()),
                f"{ks_stat:.4f}",
                f"{ks_pval:.4f}",
            ]
        }
        st.dataframe(pd.DataFrame(metrics_data), use_container_width=True,
                     hide_index=True)

    with col2:
        st.markdown("**Interpretation:**")
        if ks_pval > 0.05:
            st.success(
                f"✅ KS test p-value = {ks_pval:.3f} > 0.05. "
                "We cannot reject the hypothesis that the data follows an "
                "exponential distribution. The model is a good fit."
            )
        else:
            st.warning(
                f"⚠️ KS test p-value = {ks_pval:.3f} < 0.05. "
                "The data shows significant deviation from the exponential model. "
                "This may indicate non-stationary hashrate or pool behaviour."
            )

        st.markdown("**Expected vs observed detection rate:**")
        expected_rate = (LOWER_PERCENTILE + (100 - UPPER_PERCENTILE))
        st.info(
            f"By construction, the p{LOWER_PERCENTILE}/p{UPPER_PERCENTILE} thresholds "
            f"should flag {expected_rate}% of blocks as anomalous under a perfect "
            f"exponential model. Observed rate: {detection_rate:.1f}%. "
            f"Deviation from expected: {abs(detection_rate - expected_rate):.1f} pp."
        )

    with st.expander("📚 Model justification"):
        st.markdown(f"""
        **Why exponential distribution?**
        Bitcoin mining is a Bernoulli process with a very large number of trials
        (hash attempts) and a very small success probability per trial. By the
        Poisson limit theorem, block arrivals follow a Poisson process, whose
        inter-arrival times are exponentially distributed.

        **Why MLE for λ?**
        The MLE estimator λ̂ = 1/x̄ is the minimum-variance unbiased estimator
        for the exponential rate. It adapts to the actual network conditions
        between difficulty adjustments, making the anomaly thresholds more
        accurate than using the fixed theoretical value of 1/600.

        **Why p{LOWER_PERCENTILE}/p{UPPER_PERCENTILE} thresholds?**
        These percentiles define the central 90% of the distribution. Blocks
        outside this range have less than 5% probability of occurring under
        normal conditions — a standard threshold in statistical anomaly detection.

        **What do anomalies indicate?**
        - **Fast blocks** (< {LOWER_PERCENTILE}th percentile): a mining pool may have found
          a block immediately after the previous one, or an empty block was mined
          to claim the reward quickly.
        - **Slow blocks** (> {UPPER_PERCENTILE}th percentile): a temporary hashrate drop,
          network propagation issues, or a long gap between mining pool rounds.

        **KS test:** The Kolmogorov-Smirnov test measures the maximum distance
        between the empirical CDF and the theoretical exponential CDF. A high
        p-value (> 0.05) means the exponential model is a statistically acceptable
        fit for the data.
        """)


# ── Main render ────────────────────────────────────────────────────────────────

def render() -> None:
    st.header("M4 — AI Component: Anomaly Detector")
    st.caption(
        "Detects statistically abnormal inter-block times using an exponential "
        "distribution baseline with MLE parameter estimation."
    )

    # ── Controls ───────────────────────────────────────────────────────────────
    col1, col2 = st.columns([2, 1])
    with col1:
        n_blocks = st.slider(
            "Blocks to analyse",
            min_value=50, max_value=200, value=BLOCKS_TO_FETCH, step=10,
            key="m4_n_blocks",
            help="More blocks → better statistical estimate, slower to load."
        )
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        run_btn = st.button("🔍 Run detector", key="m4_run")

    # ── Data loading ───────────────────────────────────────────────────────────
    @st.cache_data(ttl=120, show_spinner=False)
    def load_data(n: int):
        blocks = get_blocks_paginated(n)
        return blocks

    if run_btn:
        load_data.clear()

    with st.spinner(f"Fetching {n_blocks} blocks and running anomaly detector…"):
        try:
            blocks = load_data(n_blocks)
        except Exception as exc:
            st.error(f"⚠️ Could not fetch blocks: {exc}")
            return

    # ── Processing ─────────────────────────────────────────────────────────────
    df = compute_interblock_times(blocks)
    if len(df) < 10:
        st.warning("Not enough data points to run the detector.")
        return

    deltas     = df["delta_s"].values
    lam_mle    = estimate_lambda_mle(deltas)
    lam_theory = 1.0 / TARGET_BLOCK_TIME
    df         = add_anomaly_columns(df, lam_mle)

    st.success(
        f"Analysed **{len(df)} inter-block intervals** from blocks "
        f"#{df['height'].min():,} to #{df['height'].max():,}"
    )

    # ── Render sections ────────────────────────────────────────────────────────
    st.divider()
    _render_model_explanation(lam_mle, lam_theory, len(df))
    st.divider()
    _render_timeline(df)
    st.divider()
    _render_distribution(df, lam_mle)
    st.divider()
    _render_anomaly_table(df)
    st.divider()
    _render_metrics(df, lam_mle)