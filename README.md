# CryptoChain Analyzer Dashboard

**Real-time Bitcoin cryptographic metrics dashboard**
Cryptography · Universidad Alfonso X el Sabio · Prof. Jorge Calvo · 2025–26

---

## Student Information

| Field | Value |
|---|---|
| Student Name | Pablo Jiménez |
| GitHub Username | PabloJimenezGirardeau |
| Project Title | CryptoChain Analyzer Dashboard |
| AI Approaches | M4: Anomaly Detector (exponential MLE) · M7: Difficulty Predictor (OLS regression) |

---

## What it does

A single-file HTML dashboard that connects directly to the Bitcoin network via public APIs (Mempool.space) and displays live cryptographic metrics — no server, no Python, no dependencies. Open the file and it works.

---

## How to Run

Run a local server from the project folder:

    python -m http.server 8080

Then open http://localhost:8080 in your browser.

No pip install, no virtual environment, no setup required.

---

## Modules

| Module | Title | Status |
|---|---|---|
| M1 | Proof of Work Monitor | Done |
| M2 | Block Header Analyzer | Done |
| M3 | Difficulty History | Done |
| M4 | AI — Anomaly Detector | Done |
| M5 | Merkle Proof Verifier | Done |
| M6 | Security Score — 51% Attack | Done |
| M7 | AI — Difficulty Predictor (optional) | Done |

---

## Key Features

- Real-time data via WebSocket (mempool.space) — new blocks update M1 instantly
- All cryptography runs in the browser — SHA256 double-hash verification in M2 uses the Web Crypto API
- AI models in pure JavaScript — MLE for anomaly detection (M4), OLS regression for difficulty prediction (M7)
- Interactive charts — zoom and pan across all modules
- Click-through navigation — click any block hash in M1 to inspect its header in M2
- M3 + M7 connected — enable the M7 prediction overlay directly on the difficulty history chart
- Multi-period forecast in M7 — predicts next 5 difficulty adjustments with confidence intervals

---

## Project Structure

    tarea-blockhain/
    |-- index.html        <- entire dashboard (HTML + CSS + JS, single file)
    |-- README.md
    |-- PROPOSALS.md      <- roadmap of future improvements
    |-- .gitignore

---

## APIs Used

| API | Purpose |
|---|---|
| mempool.space/api | Blocks, headers, txids, difficulty adjustments |
| mempool.space/ws | WebSocket for real-time block updates |
| mempool.space/api/v1/prices | Live BTC price in top bar |

All APIs are free and require no registration or API key.

---

## Main Problem or Blocker

No blockers.

---

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
