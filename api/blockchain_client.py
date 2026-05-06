"""
Bitcoin API client for the CryptoChain Analyzer Dashboard.
Uses Mempool.space (no API key required).
"""

import requests

BASE_MEMPOOL = "https://mempool.space/api"
TIMEOUT = 10  # seconds


# ── helpers ────────────────────────────────────────────────────────────────────

def _get(url: str) -> dict | list | str:
    """GET request with timeout and basic error handling."""
    response = requests.get(url, timeout=TIMEOUT)
    response.raise_for_status()
    try:
        return response.json()
    except Exception:
        return response.text.strip()


# ── M1 – Proof of Work Monitor ─────────────────────────────────────────────────

def get_latest_block() -> dict:
    """Return the latest Bitcoin block (all fields from Mempool.space)."""
    tip_hash = _get(f"{BASE_MEMPOOL}/blocks/tip/hash")
    return _get(f"{BASE_MEMPOOL}/block/{tip_hash}")


def get_blocks_paginated(n: int = 50) -> list[dict]:
    """
    Fetch the last N blocks by paginating the Mempool.space API.
    Each page returns ~10 blocks. Used for inter-block time analysis
    and nonce distribution in M1.
    """
    blocks = []
    tip_height = int(_get(f"{BASE_MEMPOOL}/blocks/tip/height"))
    current_height = tip_height

    while len(blocks) < n:
        batch = _get(f"{BASE_MEMPOOL}/blocks/{current_height}")
        if not batch:
            break
        blocks.extend(batch)
        current_height = batch[-1]["height"] - 1

    return blocks[:n]


# ── M2 – Block Header Analyzer ─────────────────────────────────────────────────

def get_block(block_hash: str) -> dict:
    """Return all fields for a given block hash from Mempool.space."""
    return _get(f"{BASE_MEMPOOL}/block/{block_hash}")


def get_block_header_hex(block_hash: str) -> str:
    """
    Return the raw 80-byte block header as a hex string.
    Used in M2 to recompute SHA256(SHA256(header)) locally with hashlib.
    """
    return _get(f"{BASE_MEMPOOL}/block/{block_hash}/header")


# ── M3 – Difficulty History ────────────────────────────────────────────────────

def get_difficulty_history(n_points: int = 100) -> list[dict]:
    """
    Return difficulty over time as a list of {x: timestamp, y: difficulty}.
    Source: Mempool.space difficulty-adjustments endpoint.
    """
    data = _get(f"{BASE_MEMPOOL}/v1/mining/difficulty-adjustments")

    if not isinstance(data, list):
        return []

    values = []
    for item in data:
        try:
            if isinstance(item, (list, tuple)) and len(item) >= 3:
                values.append({"x": int(item[0]), "y": float(item[2])})
            elif isinstance(item, dict):
                ts   = item.get("time") or item.get("timestamp")
                diff = item.get("difficulty")
                if ts and diff:
                    values.append({"x": int(ts), "y": float(diff)})
        except Exception:
            continue

    values.sort(key=lambda v: v["x"])
    return values[-n_points:]


def get_difficulty_adjustments() -> list:
    """
    Return the last difficulty adjustment periods from Mempool.space.
    Each item is an array: [timestamp, height, difficulty, adjustment_ratio].
    Used in M3 to mark adjustment events on the chart.
    """
    return _get(f"{BASE_MEMPOOL}/v1/mining/difficulty-adjustments")


def get_block_txids(block_hash: str) -> list[str]:
    """Return all transaction IDs for a given block hash."""
    return _get(f"{BASE_MEMPOOL}/block/{block_hash}/txids")