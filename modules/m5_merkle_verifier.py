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
    """
    Convert a transaction ID (big-endian hex) to the internal hash bytes
    (little-endian) used in Merkle tree computation.
    """
    return bytes.fromhex(txid)[::-1]


def hash_to_txid(h: bytes) -> str:
    """Convert internal hash bytes back to a human-readable txid."""
    return h[::-1].hex()


def build_merkle_tree(txids: list[str]) -> list[list[bytes]]:
    """
    Build the full Merkle tree and return all levels.
    Level 0 = leaves (transactions), last level = root.

    If a level has an odd number of nodes, the last node is duplicated
    (Bitcoin protocol rule).
    """
    if not txids:
        return []

    # Level 0: convert txids to internal byte format (little-endian)
    current_level = [txid_to_hash(txid) for txid in txids]
    levels = [current_level]

    while len(current_level) > 1:
        next_level = []
        # Duplicate last element if odd number
        if len(current_level) % 2 == 1:
            current_level = current_level + [current_level[-1]]

        for i in range(0, len(current_level), 2):
            combined = current_level[i] + current_level[i + 1]
            next_level.append(double_sha256(combined))

        levels.append(next_level)
        current_level = next_level

    return levels


def get_merkle_proof(txids: list[str], tx_index: int) -> list[dict]:
    """
    Compute the Merkle proof for a transaction at tx_index.
    Returns a list of proof steps, each with:
      - level: tree level
      - sibling_hash: the sibling node hash
      - position: 'left' or 'right' (position of the sibling)
      - current_hash: hash being verified at this step
      - combined: concatenation before hashing
      - result: hash after combining
    """
    levels = build_merkle_tree(txids)
    if not levels:
        return []

    proof = []
    current_idx = tx_index

    for level_idx, level in enumerate(levels[:-1]):  # skip root
        # Duplicate if odd
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


def verify_merkle_proof(txid: str, proof: list[dict], expected_root: str) -> bool:
    """
    Verify that txid is included in the block by recomputing the Merkle root
    from the proof steps and comparing to the expected root.
    """
    if not proof:
        return False
    computed_root = proof[-1]["result"]
    return computed_root == expected_root


# ── Visualisation helpers ──────────────────────────────────────────────────────

def _render_tree_diagram(levels: list[list[bytes]], tx_index: int,
                          proof: list[dict]) -> None:
    """
    Draw the Merkle tree as a Plotly diagram.
    - Blue nodes: normal nodes
    - Orange nodes: the proof path (siblings needed for verification)
    - Green nodes: the transaction being verified and its computed path
    Only shows up to 6 levels to keep the diagram readable.
    """
    st.subheader("🌳 Merkle Tree Diagram")

    MAX_LEVELS = min(len(levels), 6)
    display_levels = levels[:MAX_LEVELS]

    # Identify proof path nodes
    proof_path_nodes = set()   # (level, idx) of nodes in the verification path
    sibling_nodes    = set()   # (level, idx) of sibling nodes

    current_idx = tx_index
    for step in proof[:MAX_LEVELS - 1]:
        proof_path_nodes.add((step["level"], current_idx))
        if step["position"] == "right":
            sibling_nodes.add((step["level"], current_idx + 1))
        else:
            sibling_nodes.add((step["level"], current_idx - 1))
        current_idx //= 2
    # Add root
    proof_path_nodes.add((len(display_levels) - 1, 0))

    node_x, node_y, node_color, node_text, node_hover = [], [], [], [], []
    edge_x, edge_y = [], []

    for level_idx, level in enumerate(display_levels):
        y = level_idx
        n = len(level)
        max_n = len(display_levels[0])  # leaf count for spacing

        for idx, h in enumerate(level):
            x = (idx + 0.5) * (max_n / n)

            if (level_idx, idx) in proof_path_nodes:
                color = "#22c55e"
            elif (level_idx, idx) in sibling_nodes:
                color = "#f97316"
            else:
                color = "#3b82f6"

            short = hash_to_txid(h)[:8] + "..."
            node_x.append(x)
            node_y.append(y)
            node_color.append(color)
            node_text.append(short)
            node_hover.append(hash_to_txid(h))

            # Draw edge to parent
            if level_idx < len(display_levels) - 1:
                parent_idx = idx // 2
                parent_level = display_levels[level_idx + 1]
                parent_n = len(parent_level)
                px = (parent_idx + 0.5) * (max_n / parent_n)
                py = level_idx + 1
                edge_x += [x, px, None]
                edge_y += [y, py, None]

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=edge_x, y=edge_y,
        mode="lines",
        line=dict(color="#475569", width=1),
        hoverinfo="none",
        showlegend=False,
    ))

    fig.add_trace(go.Scatter(
        x=node_x, y=node_y,
        mode="markers+text",
        marker=dict(size=18, color=node_color,
                    line=dict(width=1.5, color="white")),
        text=node_text,
        textposition="top center",
        textfont=dict(size=7, color="white"),
        customdata=node_hover,
        hovertemplate="%{customdata}<extra></extra>",
        showlegend=False,
    ))

    # Legend
    for color, label in [("#22c55e", "Verification path"),
                          ("#f97316", "Proof siblings"),
                          ("#3b82f6",  "Other nodes")]:
        fig.add_trace(go.Scatter(
            x=[None], y=[None], mode="markers",
            marker=dict(size=10, color=color),
            name=label,
        ))

    n_leaves = len(display_levels[0])
    fig.update_layout(
        title=f"Merkle tree — {len(levels)} levels · {n_leaves} leaves shown"
              + (" (truncated)" if len(levels) > MAX_LEVELS else ""),
        xaxis=dict(showticklabels=False, showgrid=False, zeroline=False),
        yaxis=dict(showticklabels=False, showgrid=False, zeroline=False,
                   title="Tree level (0 = leaves, top = root)"),
        height=420,
        legend=dict(orientation="h", y=-0.1),
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        "🟢 Green = transaction being verified + computed path to root. "
        "🟠 Orange = sibling hashes provided in the proof. "
        "🔵 Blue = other nodes (not needed for verification)."
    )


def _render_proof_steps(proof: list[dict], txid: str) -> None:
    """Section 3 — Step-by-step proof verification with each hash computation."""
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
    """Section 4 — Final verification result and computational savings."""
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

    # Computational savings
    st.subheader("💡 Computational Savings")
    proof_hashes   = len(proof)
    full_hashes    = n_txs
    log2_n         = math.ceil(math.log2(n_txs)) if n_txs > 1 else 1
    savings_pct    = (1 - proof_hashes / full_hashes) * 100

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Hashes needed (Merkle proof)", f"{proof_hashes}")
        st.caption(f"= ceil(log₂({n_txs})) = {log2_n}")
    with col2:
        st.metric("Hashes needed (full block)", f"{full_hashes:,}")
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

    # ── Block selection ────────────────────────────────────────────────────────
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

    # ── Load block and txids ───────────────────────────────────────────────────
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

    n_txs         = len(txids)
    merkle_root   = block.get("merkle_root") or block.get("merkleroot", "")

    st.success(
        f"Block **#{block['height']:,}** · "
        f"**{n_txs:,} transactions** · "
        f"Merkle root: `{merkle_root[:16]}...`"
    )

    # ── Transaction selection ──────────────────────────────────────────────────
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

    # ── Build tree and proof ───────────────────────────────────────────────────
    with st.spinner("Building Merkle tree…"):
        levels = build_merkle_tree(txids)
        proof  = get_merkle_proof(txids, tx_index)

    # ── Render sections ────────────────────────────────────────────────────────
    st.divider()
    _render_tree_diagram(levels, tx_index, proof)
    st.divider()
    _render_proof_steps(proof, selected_txid)
    st.divider()
    _render_verification_result(proof, merkle_root, selected_txid, tx_index, n_txs)