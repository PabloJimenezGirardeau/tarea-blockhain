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
| M2 | Block Header Analyzer | Not started |
| M3 | Difficulty History | Not started |
| M4 | AI Component | Not started |

## Current Progress
- Accepted GitHub Classroom assignment and set up the repository structure.
- Connected to the Mempool.space API and retrieved live Bitcoin block data.
- Script `api/blockchain_client.py` fetches height, hash, difficulty, nonce, bits and transaction count from the latest block.
- Verified that the block hash shows leading zeros, confirming Proof of Work visually.
- AI approach decided: Anomaly Detector for M4 and Difficulty Predictor for M7.

## Next Step
- Begin M1: build the Proof of Work Monitor module with difficulty value and block time distribution plot.

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
    `-- m4_ai_component.py
```
