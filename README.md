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
| M2 | Block Header Analyzer | In progress |
| M3 | Difficulty History | Not started |
| M4 | AI Component | Not started |

## Current Progress

- M1 fully implemented: live difficulty, estimated hash rate, leading zero bits, 256-bit target threshold visual, inter-block time histogram with theoretical exponential curve, nonce distribution across last 50 blocks, and next difficulty adjustment estimator.
- API client (`api/blockchain_client.py`) refactored into reusable functions used by all modules.
- Auto-refresh every 60 seconds implemented in M1 via `st.rerun()`.
- Connected to Mempool.space API with paginated block fetching (up to 50 blocks).
- AI approach confirmed: Anomaly Detector for M4, Difficulty Predictor for M7.

## Next Step

- Complete M2: Block Header Analyzer with SHA-256 double-hash local verification using `hashlib`.

## Main Problem or Blocker

- No blockers at this point.

## How to Run

​```bash
pip install -r requirements.txt
streamlit run app.py
​```

## Project Structure

​```text
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
    `-- m4_ai_component.py
​```
