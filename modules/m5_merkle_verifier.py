"""
M5 - Merkle Proof Verifier
Picks a transaction from a Bitcoin block and verifies its Merkle proof
step by step, showing each hash computation.

Bitcoin Merkle tree specifics:
  - Double SHA-256 at every node: SHA256(SHA256(left + right))
  - Transaction IDs are stored in little-endian; must be reversed before hashing
  - If a level has an odd number of nodes, the last one is duplicated
  - The root must match the merkleroot field in the block header (M2)

Computational savings:
  - Full verification requires only ceil(log2(N)) hashes
  - vs downloading all N transaction IDs
"""

import hashlib
import math
import plotly.graph_objects as go
import streamlit as st

from api.blockchain_client import get_latest_block, get_block, get_block_txids


# ── Merkle helpers ─────────────────────────────────────────────────────────────

def double_sha256(data: bytes) -> bytes:
    """Bitcoin's standard hash function: SHA256(SHA256(data))."""
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()


def txid_to_hash(txid: str) -> bytes:
    return bytes.fromhex(txid)[::-1]


def hash_to_txid(h: bytes) -> str:
    return h[::-1].hex()


def build_merkle_tree(txids: list[str]) -> list[list[bytes]]:
    if not txids:
        return []
    current_level = [txid_to_hash(txid) for txid in txids]
    levels = [current_level]
    while len(current_level) > 1:
        next_level = []
        if len(current_level) % 2 == 1:
            current_level = current_level + [current_level[-1]]
        for i in range(0, len(current_level), 2):
            combined = current_level[i] + current_level[i + 1]
            next_level.append(double_sha256(combined))
        levels.append(next_level)
        current_level = next_level
    return levels


def get_merkle_proof(txids: list[str], tx_index: int) -> list[dict]:
    levels = build_merkle_tree(txids)
    if not levels:
        return []
    proof = []
    current_idx = tx_index
    for level_idx, level in enumerate(levels[:-1]):
        padded = level + ([level[-1]] if len(level) % 2 == 1 else [])
        if current_idx % 2 == 0:
            sibling_idx = current_idx + 1
            position = "right"
            left  = padded[current_idx]
            right = padded[sibling_idx] if sibling_idx < len(padded) else padded[current_idx]
        else:
            sibling_idx = current_idx - 1
            position = "left"
            left  = padded[sibling_idx]
            right = padded[current_idx]
        combined = left + right
        result   = double_sha256(combined)
        proof.append({
            "level":        level_idx,
            "current_hash": hash_to_txid(padded[current_idx]),
            "sibling_hash": hash_to_txid(padded[sibling_idx] if sibling_idx < len(padded) else padded[current_idx]),
            "position":     position,
            "left":         hash_to_txid(left),
            "right":        hash_to_txid(right),
            "combined_hex": combined.hex(),
            "result":       hash_to_txid(result),
        })
        current_idx //= 2
    return proof


# ── Visualisation ──────────────────────────────────────────────────────────────

def _render_proof_path_diagram(proof: list[dict], txid: str) -> None:
    """
    Draw only the proof path — the minimal set of nodes needed for verification.
    At most log2(N) ≈ 12 nodes. Clean, fast, and communicates the key insight:
    you only need these few hashes to verify any transaction.
    """
    st.subheader("🌳 Merkle Proof Path")

    if not proof:
        st.warning("No proof to display.")
        return

    n_levels = len(proof) + 1  # proof steps + root

    node_x, node_y = [], []
    node_color, node_text, node_hover = [], [], []
    edge_x, edge_y = [], []

    # Build nodes: for each level we show current + sibling + result
    # Layout: sibling on left/right, current in center, result above
    level_nodes = []  # list of (x, y, color, short_label, full_hash)

    current_x = 0.5
    spacing   = 1.0

    for i, step in enumerate(proof):
        y = i * 2

        if step["position"] == "right":
            x_current = current_x
            x_sibling = current_x + spacing
        else:
            x_sibling = current_x - spacing
            x_current = current_x

        x_result = (x_current + x_sibling) / 2

        # Current node (green)
        level_nodes.append((x_current, y, "#22c55e",
                            step["current_hash"][:8] + "...",
                            step["current_hash"], "Current"))
        # Sibling node (orange)
        level_nodes.append((x_sibling, y, "#f97316",
                            step["sibling_hash"][:8] + "...",
                            step["sibling_hash"], "Sibling"))
        # Result node (blue, will be current at next level)
        level_nodes.append((x_result, y + 1, "#3b82f6",
                            step["result"][:8] + "...",
                            step["result"], "Result"))

        # Edges
        edge_x += [x_current, x_result, None, x_sibling, x_result, None]
        edge_y += [y, y + 1, None, y, y + 1, None]

        current_x = x_result

    # Root node
    root_step = proof[-1]
    level_nodes.append((current_x, len(proof) * 2, "#a855f7",
                        root_step["result"][:8] + "...",
                        root_step["result"], "Root ✅"))

    for x, y, color, short, full, role in level_nodes:
        node_x.append(x)
        node_y.append(y)
        node_color.append(color)
        node_text.append(short)
        node_hover.append(f"<b>{role}</b><br>{full}")

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=edge_x, y=edge_y,
        mode="lines",
        line=dict(color="#475569", width=1.5),
        hoverinfo="none",
        showlegend=False,
    ))

    fig.add_trace(go.Scatter(
        x=node_x, y=node_y,
        mode="markers+text",
        marker=dict(size=22, color=node_color,
                    line=dict(width=2, color="white")),
        text=node_text,
        textposition="middle center",
        textfont=dict(size=7, color="white"),
        customdata=node_hover,
        hovertemplate="%{customdata}<extra></extra>",
        showlegend=False,
    ))

    for color, label in [
        ("#22c55e", "Current hash (path)"),
        ("#f97316", "Sibling hash (proof)"),
        ("#3b82f6", "Computed result"),
        ("#a855f7", "Merkle Root"),
    ]:
        fig.add_trace(go.Scatter(
            x=[None], y=[None], mode="markers",
            marker=dict(size=10, color=color),
            name=label,
        ))

    fig.update_layout(
        title=f"Proof path: {len(proof)} steps to reach the Merkle Root",
        xaxis=dict(showticklabels=False, showgrid=False, zeroline=False),
        yaxis=dict(showticklabels=False, showgrid=False, zeroline=False,
                   title="Level (bottom = tx, top = root)"),
        height=max(400, n_levels * 80),
        legend=dict(orientation="h", y=-0.1),
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        "Only the 🟠 orange (sibling) hashes are needed to verify the transaction. "
        "The 🟢 green path is recomputed locally. "
        "If the final result matches the Merkle Root in the block header, the transaction is confirmed."
    )


def _render_proof_steps(proof: list[dict], txid: str) -> None:
    st.subheader("🔢 Step-by-Step Verification")
    st.markdown(
        f"**Transaction:** `{txid[:32]}...{txid[-8:]}`\n\n"
        "At each level, we combine the current hash with its sibling and apply "
        "SHA256(SHA256(left ∥ right)) to climb to the next level."
    )
    for i, step in enumerate(proof):
        with st.expander(
            f"Level {step['level']} → {step['level'] + 1}  "
            f"(sibling on the **{step['position']}**)",
            expanded=(i == 0),
        ):
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Current hash (this node):**")
                st.code(step["current_hash"], language=None)
                st.markdown(f"**Sibling hash ({step['position']}):**")
                st.code(step["sibling_hash"], language=None)
            with col2:
                st.markdown("**Left input:**")
                st.code(step["left"], language=None)
                st.markdown("**Right input:**")
                st.code(step["right"], language=None)
            st.markdown("**SHA256(SHA256(left ∥ right)) →**")
            st.code(step["result"], language=None)


def _render_verification_result(proof: list[dict], expected_root: str,
                                 txid: str, tx_index: int, n_txs: int) -> None:
    st.subheader("✅ Verification Result")
    if not proof:
        st.error("Could not generate proof.")
        return

    computed_root = proof[-1]["result"]
    is_valid      = computed_root == expected_root

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Computed Merkle root (from proof):**")
        st.code(computed_root, language=None)
    with col2:
        st.markdown("**Expected Merkle root (from block header):**")
        st.code(expected_root, language=None)

    if is_valid:
        st.success(
            f"✅ Merkle proof VALID — transaction #{tx_index} is confirmed "
            f"to be included in this block."
        )
    else:
        st.error("❌ Merkle proof INVALID — root mismatch.")

    st.subheader("💡 Computational Savings")
    proof_hashes = len(proof)
    log2_n       = math.ceil(math.log2(n_txs)) if n_txs > 1 else 1
    savings_pct  = (1 - proof_hashes / n_txs) * 100

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Hashes needed (Merkle proof)", f"{proof_hashes}")
        st.caption(f"= ceil(log₂({n_txs})) = {log2_n}")
    with col2:
        st.metric("Hashes needed (full block)", f"{n_txs:,}")
        st.caption("All transaction IDs")
    with col3:
        st.metric("Data saved", f"{savings_pct:.1f}%")
        st.caption("Bandwidth reduction vs full download")

    st.info(
        f"A Merkle proof for a block with **{n_txs:,} transactions** requires only "
        f"**{proof_hashes} hashes** (≈ log₂({n_txs}) = {log2_n}), instead of "
        f"downloading all {n_txs:,} transaction IDs. "
        "This is the SPV (Simplified Payment Verification) efficiency described "
        "in Section 8 of the Bitcoin whitepaper (Nakamoto 2008)."
    )


# ── Main render ────────────────────────────────────────────────────────────────

def render() -> None:
    st.header("M5 — Merkle Proof Verifier")
    st.caption(
        "Pick a transaction from a Bitcoin block and verify its Merkle proof "
        "step by step, recomputing each hash with SHA256²."
    )

    if "m5_selected_hash" not in st.session_state:
        st.session_state["m5_selected_hash"] = ""

    col1, col2 = st.columns([3, 1])
    with col1:
        typed_hash = st.text_input(
            "Block hash",
            placeholder="Enter a block hash or load the latest block →",
            key="m5_hash_input",
        )
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        load_latest = st.button("⬇️ Load latest block", key="m5_latest")

    if load_latest:
        with st.spinner("Fetching latest block…"):
            try:
                latest = get_latest_block()
                st.session_state["m5_selected_hash"] = latest["id"]
            except Exception as exc:
                st.error(f"Could not fetch latest block: {exc}")
                return

    if typed_hash:
        st.session_state["m5_selected_hash"] = typed_hash

    block_hash = st.session_state["m5_selected_hash"]

    if not block_hash:
        st.info("Enter a block hash or click **Load latest block** to begin.")
        return

    @st.cache_data(ttl=300, show_spinner=False)
    def load_block_data(h: str):
        block = get_block(h)
        txids = get_block_txids(h)
        return block, txids

    with st.spinner("Fetching block data…"):
        try:
            block, txids = load_block_data(block_hash.strip())
        except Exception as exc:
            st.error(f"⚠️ Could not fetch block: {exc}")
            return

    if not txids:
        st.warning("No transactions found in this block.")
        return

    n_txs       = len(txids)
    merkle_root = block.get("merkle_root") or block.get("merkleroot", "")

    st.success(
        f"Block **#{block['height']:,}** · "
        f"**{n_txs:,} transactions** · "
        f"Merkle root: `{merkle_root[:16]}...`"
    )

    st.subheader("🔍 Select Transaction")
    col1, col2 = st.columns([2, 1])
    with col1:
        tx_index = st.slider(
            "Transaction index",
            min_value=0, max_value=n_txs - 1, value=0,
            key="m5_tx_index",
            help="0 = coinbase (miner reward transaction)",
        )
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        st.info(f"**{tx_index}** of {n_txs - 1}")

    selected_txid = txids[tx_index]
    st.markdown(f"**Selected txid:** `{selected_txid}`")
    if tx_index == 0:
        st.caption("ℹ️ Transaction #0 is the coinbase — the miner's reward transaction.")

    with st.spinner("Building Merkle proof…"):
        proof = get_merkle_proof(txids, tx_index)

    st.divider()
    _render_proof_path_diagram(proof, selected_txid)
    st.divider()
    _render_proof_steps(proof, selected_txid)
    st.divider()
    _render_verification_result(proof, merkle_root, selected_txid, tx_index, n_txs)