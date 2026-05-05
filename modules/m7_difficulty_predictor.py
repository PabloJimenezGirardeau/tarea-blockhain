"""
M7 - Second AI Approach: Difficulty Predictor
Predicts the next Bitcoin difficulty adjustment value using a linear regression
model trained on historical adjustment data from Mempool.space.

Features used:
  - Previous difficulty (t-1)
  - Adjustment ratio of the previous period
  - 3-period moving average of difficulty
  - Temporal index (captures long-term growth trend)

Train/test split is temporal (chronological), not random, to avoid data leakage.
Includes 90% confidence intervals on predictions.

Compared against M4 (Anomaly Detector) as required by the project spec.
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import StandardScaler

from api.blockchain_client import get_difficulty_adjustments

# ── Constants ──────────────────────────────────────────────────────────────────
TRAIN_RATIO    = 0.80   # 80% train, 20% test (temporal split)
CONFIDENCE     = 0.90   # confidence interval level
MA_WINDOW      = 3      # moving average window for feature engineering
MIN_SAMPLES    = 20     # minimum adjustments needed to train


# ── Data preparation ───────────────────────────────────────────────────────────

def load_and_parse_adjustments() -> pd.DataFrame:
    """
    Load difficulty adjustments from Mempool.space and parse into a DataFrame.
    Returns columns: date, height, difficulty, ratio.
    """
    raw = get_difficulty_adjustments()
    rows = []
    for item in raw:
        try:
            if isinstance(item, (list, tuple)) and len(item) >= 4:
                rows.append({
                    "date":       pd.to_datetime(int(item[0]), unit="s"),
                    "height":     int(item[1]),
                    "difficulty": float(item[2]),
                    "ratio":      float(item[3]),
                })
            elif isinstance(item, dict):
                ts   = item.get("time") or item.get("timestamp")
                diff = item.get("difficulty")
                rat  = item.get("adjustment") or item.get("ratio") or 1.0
                h    = item.get("height")
                if ts and diff:
                    rows.append({
                        "date":       pd.to_datetime(int(ts), unit="s"),
                        "height":     int(h) if h else 0,
                        "difficulty": float(diff),
                        "ratio":      float(rat),
                    })
        except Exception:
            continue

    df = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
    return df


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Engineer features for the regression model.
    Uses only past information to avoid data leakage.
    """
    df = df.copy()
    df["diff_lag1"]   = df["difficulty"].shift(1)       # previous difficulty
    df["ratio_lag1"]  = df["ratio"].shift(1)             # previous ratio
    df["diff_ma3"]    = df["difficulty"].shift(1).rolling(MA_WINDOW).mean()  # 3-period MA
    df["time_index"]  = np.arange(len(df))               # temporal trend
    df["target"]      = df["difficulty"]                  # what we want to predict
    df = df.dropna().reset_index(drop=True)
    return df


# ── Model training ─────────────────────────────────────────────────────────────

def train_model(df: pd.DataFrame):
    """
    Train a linear regression model with temporal train/test split.
    Returns: model, scaler, X_train, X_test, y_train, y_test, split_idx
    """
    feature_cols = ["diff_lag1", "ratio_lag1", "diff_ma3", "time_index"]
    X = df[feature_cols].values
    y = df["target"].values

    split_idx = int(len(df) * TRAIN_RATIO)
    X_train, X_test = X[:split_idx], X[split_idx:]
    y_train, y_test = y[:split_idx], y[split_idx:]

    scaler  = StandardScaler()
    X_train_sc = scaler.fit_transform(X_train)
    X_test_sc  = scaler.transform(X_test)

    model = LinearRegression()
    model.fit(X_train_sc, y_train)

    return model, scaler, X_train_sc, X_test_sc, y_train, y_test, split_idx, feature_cols


def compute_prediction_interval(model, X_train, y_train, X_pred, confidence=0.90):
    """
    Compute prediction intervals for linear regression using residual std.
    PI = y_hat ± t * std_residuals * sqrt(1 + h)
    where h is the leverage (simplified as 1/n for new predictions).
    """
    y_hat_train = model.predict(X_train)
    residuals   = y_train - y_hat_train
    std_resid   = np.std(residuals)

    from scipy import stats
    alpha   = 1 - confidence
    t_crit  = stats.t.ppf(1 - alpha / 2, df=len(y_train) - X_train.shape[1] - 1)

    y_pred  = model.predict(X_pred)
    margin  = t_crit * std_resid * np.sqrt(1 + 1 / len(X_train))

    return y_pred, y_pred - margin, y_pred + margin


# ── Section renderers ──────────────────────────────────────────────────────────

def _render_model_explanation(df: pd.DataFrame, split_idx: int) -> None:
    """Section 1 — Model description and comparison with M4."""
    st.subheader("📈 Difficulty Predictor Model")

    st.markdown("""
    **Approach:** Linear regression with engineered temporal features.

    The model learns the relationship between past difficulty values, adjustment
    ratios, and the long-term growth trend to predict the next difficulty value
    before the adjustment occurs.
    """)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Training samples", f"{split_idx}")
        st.caption(f"First {int(TRAIN_RATIO*100)}% of history")
    with col2:
        st.metric("Test samples", f"{len(df) - split_idx}")
        st.caption(f"Last {int((1-TRAIN_RATIO)*100)}% (unseen data)")
    with col3:
        st.metric("Features", "4")
        st.caption("lag1, ratio, MA3, trend")
    with col4:
        st.metric("Confidence interval", f"{int(CONFIDENCE*100)}%")
        st.caption("On next adjustment prediction")

    with st.expander("📐 Why linear regression?"):
        st.markdown("""
        Bitcoin difficulty has a strong **long-term upward trend** and
        short-term fluctuations driven by the adjustment ratio. Linear regression
        captures both through:

        - **`diff_lag1`**: The previous difficulty is the strongest predictor
          of the next one (high autocorrelation).
        - **`ratio_lag1`**: The previous ratio tells us if miners were fast or slow,
          which determines the direction of the next adjustment.
        - **`diff_ma3`**: A 3-period moving average smooths noise and captures
          medium-term trends.
        - **`time_index`**: A linear time trend captures the long-term growth
          in Bitcoin's hashrate and difficulty.

        More complex models (LSTM, Prophet) are harder to justify for this
        problem because the adjustment formula is largely deterministic —
        complexity would overfit rather than improve generalisation.
        """)

    with st.expander("⚖️ M4 vs M7 — How the two AI approaches differ"):
        st.markdown("""
        | | M4 — Anomaly Detector | M7 — Difficulty Predictor |
        |---|---|---|
        | **Goal** | Detect unusual blocks | Predict future difficulty |
        | **Model** | Exponential distribution (MLE) | Linear regression |
        | **Input** | Inter-block times | Historical difficulty + ratios |
        | **Output** | Anomaly flag per block | Next difficulty value + CI |
        | **Evaluation** | KS test, detection rate | MAE, RMSE, R² |
        | **Type** | Unsupervised | Supervised (regression) |
        """)


def _render_predictions_chart(df: pd.DataFrame, y_pred_test, lower, upper,
                               split_idx: int) -> None:
    """Section 2 — Predictions vs actual values with confidence intervals."""
    st.subheader("📊 Predictions vs Actual Difficulty")

    train_df = df.iloc[:split_idx]
    test_df  = df.iloc[split_idx:]

    fig = go.Figure()

    # Training data
    fig.add_trace(go.Scatter(
        x=train_df["date"], y=train_df["difficulty"],
        mode="lines",
        name="Training data",
        line=dict(color="#3b82f6", width=1.5),
        opacity=0.6,
    ))

    # Actual test values
    fig.add_trace(go.Scatter(
        x=test_df["date"], y=test_df["difficulty"],
        mode="lines+markers",
        name="Actual (test set)",
        line=dict(color="#22c55e", width=2),
        marker=dict(size=5),
    ))

    # Predicted values
    fig.add_trace(go.Scatter(
        x=test_df["date"], y=y_pred_test,
        mode="lines+markers",
        name="Predicted",
        line=dict(color="#f97316", width=2, dash="dash"),
        marker=dict(size=5, symbol="diamond"),
    ))

    # Confidence interval
    fig.add_trace(go.Scatter(
        x=pd.concat([test_df["date"], test_df["date"].iloc[::-1]]),
        y=np.concatenate([upper, lower[::-1]]),
        fill="toself",
        fillcolor="rgba(249,115,22,0.12)",
        line=dict(color="rgba(255,255,255,0)"),
        name=f"{int(CONFIDENCE*100)}% prediction interval",
        showlegend=True,
    ))

    # Train/test split line
    split_date = test_df["date"].iloc[0].strftime("%Y-%m-%d")
    fig.add_shape(
        type="line",
        x0=split_date, x1=split_date,
        y0=0, y1=1,
        xref="x", yref="paper",
        line=dict(color="white", width=1.5, dash="dot"),
    )
    fig.add_annotation(
        x=split_date, y=1,
        xref="x", yref="paper",
        text="Train / Test split",
        showarrow=False,
        font=dict(color="white", size=10),
        bgcolor="rgba(0,0,0,0.5)",
        xanchor="left",
    )

    fig.update_layout(
        title="Bitcoin difficulty: actual vs predicted (linear regression)",
        xaxis_title="Date",
        yaxis_title="Difficulty",
        legend=dict(orientation="h", y=-0.25),
        height=450,
        hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        "The model is trained on the first 80% of historical adjustments and "
        "evaluated on the remaining 20% (unseen data). Orange shading shows "
        f"the {int(CONFIDENCE*100)}% prediction interval."
    )


def _render_next_prediction(model, scaler, df: pd.DataFrame) -> None:
    """Section 3 — Predict the NEXT (future) difficulty adjustment."""
    st.subheader("🔮 Next Difficulty Adjustment — Prediction")

    last = df.iloc[-1]
    next_time_index = last["time_index"] + 1

    X_next = np.array([[
        last["difficulty"],
        last["ratio"],
        df["difficulty"].tail(MA_WINDOW).mean(),
        next_time_index,
    ]])
    X_next_sc = scaler.transform(X_next)

    # Full training set for PI computation
    feature_cols = ["diff_lag1", "ratio_lag1", "diff_ma3", "time_index"]
    X_all = scaler.transform(df[feature_cols].values)
    y_all = df["target"].values

    y_hat, lower, upper = compute_prediction_interval(
        model, X_all, y_all, X_next_sc, CONFIDENCE
    )
    predicted  = float(y_hat[0])
    ci_lower   = float(lower[0])
    ci_upper   = float(upper[0])
    current    = float(last["difficulty"])
    change_pct = (predicted - current) / current * 100

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Current difficulty", f"{current:,.0f}")
        st.caption("Latest known adjustment")
    with col2:
        direction = "⬆️" if change_pct > 0 else "⬇️"
        st.metric("Predicted next difficulty", f"{predicted:,.0f}",
                  delta=f"{change_pct:+.2f}%")
        st.caption(f"{direction} vs current")
    with col3:
        st.metric(f"{int(CONFIDENCE*100)}% Confidence interval",
                  f"{ci_lower:,.0f} – {ci_upper:,.0f}")
        st.caption("Range within which next value is expected")

    # Visual gauge
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=["Current", "Predicted (low)", "Predicted", "Predicted (high)"],
        y=[current, ci_lower, predicted, ci_upper],
        marker_color=["#3b82f6", "#fbbf24", "#f97316", "#fbbf24"],
        text=[f"{v:,.0f}" for v in [current, ci_lower, predicted, ci_upper]],
        textposition="outside",
    ))
    fig.update_layout(
        title="Next difficulty adjustment — prediction with confidence interval",
        yaxis_title="Difficulty",
        height=350,
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_metrics(y_test, y_pred_test, model, feature_cols) -> None:
    """Section 4 — Model evaluation metrics."""
    st.subheader("📐 Model Evaluation Metrics")

    mae   = mean_absolute_error(y_test, y_pred_test)
    rmse  = np.sqrt(mean_squared_error(y_test, y_pred_test))
    r2    = r2_score(y_test, y_pred_test)
    mape  = np.mean(np.abs((y_test - y_pred_test) / y_test)) * 100

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("MAE", f"{mae:,.0f}")
        st.caption("Mean Absolute Error")
    with col2:
        st.metric("RMSE", f"{rmse:,.0f}")
        st.caption("Root Mean Squared Error")
    with col3:
        st.metric("R²", f"{r2:.4f}")
        st.caption("Coefficient of determination")
    with col4:
        st.metric("MAPE", f"{mape:.2f}%")
        st.caption("Mean Absolute % Error")

    if r2 > 0.95:
        st.success(f"✅ R² = {r2:.4f} — excellent fit. The model explains "
                   f"{r2*100:.1f}% of the variance in difficulty.")
    elif r2 > 0.80:
        st.info(f"ℹ️ R² = {r2:.4f} — good fit.")
    else:
        st.warning(f"⚠️ R² = {r2:.4f} — moderate fit. Consider additional features.")

    # Feature importance (coefficients)
    with st.expander("🔍 Feature importance (regression coefficients)"):
        coef_df = pd.DataFrame({
            "Feature": feature_cols,
            "Coefficient": model.coef_,
            "Abs importance": np.abs(model.coef_),
        }).sort_values("Abs importance", ascending=False)
        st.dataframe(coef_df.round(4), use_container_width=True, hide_index=True)
        st.caption(
            "Standardised coefficients — larger absolute value = more important feature."
        )


def _render_m4_vs_m7_comparison() -> None:
    """Section 5 — Side-by-side comparison of M4 and M7 as required by the spec."""
    st.subheader("⚖️ M4 vs M7 — Comparison of AI Approaches")

    comparison = pd.DataFrame({
        "Criterion": [
            "Problem type",
            "Model",
            "Data used",
            "Output",
            "Key metric",
            "Strength",
            "Limitation",
        ],
        "M4 — Anomaly Detector": [
            "Anomaly detection (unsupervised)",
            "Exponential distribution + MLE",
            "Inter-block times (last 150 blocks)",
            "Anomaly flag per block (fast/slow/normal)",
            "KS test p-value, detection rate",
            "No training data needed, statistically grounded, real-time",
            "Cannot predict future — only flags past events",
        ],
        "M7 — Difficulty Predictor": [
            "Regression (supervised)",
            "Linear regression with temporal features",
            "Historical difficulty adjustments (455 periods)",
            "Next difficulty value + 90% confidence interval",
            "MAE, RMSE, R², MAPE",
            "Predicts future values before they occur",
            "Requires historical data, assumes linear trend continues",
        ],
    })

    st.dataframe(comparison, use_container_width=True, hide_index=True)
    st.caption(
        "The two models are complementary: M4 monitors real-time anomalies in "
        "block arrival, while M7 predicts the next difficulty adjustment using "
        "historical trends. Together they cover both reactive and predictive "
        "analysis of the Bitcoin network."
    )


# ── Main render ────────────────────────────────────────────────────────────────

def render() -> None:
    st.header("M7 — Second AI Approach: Difficulty Predictor")
    st.caption(
        "Predicts the next Bitcoin difficulty adjustment using linear regression "
        "with temporal features. Compared against M4 (Anomaly Detector)."
    )

    col1, col2 = st.columns([3, 1])
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        run_btn = st.button("🚀 Train & predict", key="m7_run")

    # ── Data loading ───────────────────────────────────────────────────────────
    @st.cache_data(ttl=3600, show_spinner=False)
    def load_data():
        return load_and_parse_adjustments()

    if run_btn:
        load_data.clear()

    with st.spinner("Loading historical difficulty data and training model…"):
        try:
            raw_df = load_data()
        except Exception as exc:
            st.error(f"⚠️ Could not fetch data: {exc}")
            return

    if len(raw_df) < MIN_SAMPLES:
        st.warning(f"Not enough data ({len(raw_df)} adjustments). Need at least {MIN_SAMPLES}.")
        return

    df = build_features(raw_df)

    if len(df) < MIN_SAMPLES:
        st.warning("Not enough data after feature engineering.")
        return

    # ── Training ───────────────────────────────────────────────────────────────
    try:
        model, scaler, X_train, X_test, y_train, y_test, split_idx, feature_cols = train_model(df)
    except Exception as exc:
        st.error(f"⚠️ Model training failed: {exc}")
        return

    y_pred_test, lower_test, upper_test = compute_prediction_interval(
        model, X_train, y_train, X_test, CONFIDENCE
    )

    st.success(
        f"Model trained on **{split_idx} adjustments** · "
        f"evaluated on **{len(df) - split_idx} unseen adjustments**"
    )

    # ── Render sections ────────────────────────────────────────────────────────
    st.divider()
    _render_model_explanation(df, split_idx)
    st.divider()
    _render_predictions_chart(df, y_pred_test, lower_test, upper_test, split_idx)
    st.divider()
    _render_next_prediction(model, scaler, df)
    st.divider()
    _render_metrics(y_test, y_pred_test, model, feature_cols)
    st.divider()
    _render_m4_vs_m7_comparison()