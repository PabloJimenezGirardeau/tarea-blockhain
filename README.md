# Blockchain Dashboard Project

Update this README every week.

## Student Information

| Field | Value |
|---|---|
| Student Name | Pablo Jiménez |
| GitHub Username | PabloJimenezGirardeau |
| Project Title | CryptoChain Analyzer Dashboard |
| Chosen AI Approach | M4: Anomaly Detector (inter-block time distribution) + M7: Difficulty Predictor (time-series) |

## Module Tracking

Use one of these values: `Not started`, `In progress`, `Done`

| Module | What it should include | Status |
|---|---|---|
| M1 | Proof of Work Monitor | Done |
| M2 | Block Header Analyzer | Done |
| M3 | Difficulty History | Done |
| M4 | AI Component | Done |
| M7 | Difficulty Predictor (optional) | Done |

## Current Progress

- M1 fully implemented: live difficulty, estimated hash rate, leading zero bits, 256-bit target threshold visual, inter-block time histogram with theoretical exponential curve, nonce distribution across last 50 blocks, and next difficulty adjustment estimator.
- M2 fully implemented: 80-byte header parsed in little-endian, all 6 fields displayed, SHA256(SHA256(header)) verified locally with hashlib, byte map visualization, hash vs target 256-bit comparison.
- M3 fully implemented: historical difficulty chart with 455 adjustment event markers, block time ratio per period, Section 6.1 adjustment formula with predicted vs actual table, period summary stats. Largest drop identified: -27.9% on 2021-07-03 (China mining ban).
- M4 fully implemented: anomaly detector on inter-block times using exponential distribution baseline, MLE lambda estimation, rolling window adaptive detection, KS test evaluation, fast/slow anomaly classification.
- M7 fully implemented: difficulty predictor using linear regression with temporal features (lag1, ratio, MA3, time index), temporal train/test split (80/20), 90% confidence intervals, R²=0.9841, MAPE=3.49%, M4 vs M7 comparison table.
- All required modules complete. Two optional AI modules implemented. API client migrated fully to Mempool.space.

## Next Step

- Implement M5: Merkle Proof Verifier.
- Implement M6: Security Score (51% attack cost).
- Write final report (PDF, 2-3 pages) and add to repository before deadline.

## Main Problem or Blocker

- No blockers at this point.

## How to Run

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Project Structure

```text
tarea-blockhain/
|-- README.md
|-- requirements.txt
|-- .gitignore
|-- app.py
|-- api/
|   `-- blockchain_client.py
`-- modules/
    |-- m1_pow_monitor.py
    |-- m2_block_header.py
    |-- m3_difficulty_history.py
    |-- m4_ai_component.py
    `-- m7_difficulty_predictor.py
```

<!-- student-repo-auditor:teacher-feedback:start -->
## Teacher Feedback
### Kick-off Review
Review time: 2026-04-29 20:44 CEST
Status: Green
Strength:
- I can see the dashboard structure integrating the checkpoint modules.
Improve now:
- M3 still needs a clearer difficulty-history implementation with charting and adjustment evidence.
Next step:
- Add a real difficulty-history chart and connect it to adjustment-period evidence.
### Student Response
Feedback implemented on 2026-04-30:
- M3 now includes a full historical difficulty chart with 455 adjustment event markers.
- Block time ratio per adjustment period added, directly addressing the adjustment-period evidence requested.
- Section 6.1 formula applied with predicted vs actual difficulty values for each period.
<!-- student-repo-auditor:teacher-feedback:end -->
