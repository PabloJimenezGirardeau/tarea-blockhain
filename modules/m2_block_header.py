"""
M2 - Block Header Analyzer
Displays the 80-byte Bitcoin block header structure, verifies Proof of Work
locally using hashlib (SHA256 double-hash), and compares the result against
the difficulty target derived from the bits field.
"""

import hashlib
import struct
import streamlit as st
import plotly.graph_objects as go

from api.blockchain_client import get_latest_block, get_block, get_block_header_hex


# ── Constants ──────────────────────────────────────────────────────────────────

HEADER_FIELDS = [
    ("Version",             0,   4,  "#6366f1"),
    ("Previous Block Hash", 4,  36,  "#3b82f6"),
    ("Merkle Root",        36,  68,  "#22c55e"),
    ("Timestamp",          68,  72,  "#f59e0b"),
    ("Bits",               72,  76,  "#ef4444"),
    ("Nonce",              76,  80,  "#a855f7"),
]


# ── Cryptographic helpers ──────────────────────────────────────────────────────

def parse_header(header_hex: str) -> dict:
    raw = bytes.fromhex(header_hex)
    assert len(raw) == 80, f"Expected 80 bytes, got {len(raw)}"
    version   = struct.unpack("<I", raw[0:4])[0]
    prev_hash = raw[4:36][::-1].hex()
    merkle    = raw[36:68][::-1].hex()
    timestamp = struct.unpack("<I", raw[68:72])[0]
    bits      = struct.unpack("<I", raw[72:76])[0]
    nonce     = struct.unpack("<I", raw[76:80])[0]
    return {
        "version":   version,
        "prev_hash": prev_hash,
        "merkle":    merkle,
        "timestamp": timestamp,
        "bits":      bits,
        "nonce":     nonce,
    }


def double_sha256(header_hex: str) -> str:
    raw   = bytes.fromhex(header_hex)
    hash1 = hashlib.sha256(raw).digest()
    hash2 = hashlib.sha256(hash1).digest()
    return hash2[::-1].hex()


def bits_to_target(bits: int) -> int:
    exponent = bits >> 24
    mantissa = bits & 0x007FFFFF
    return mantissa * (2 ** (8 * (exponent - 3)))


def count_leading_zero_bits(hash_hex: str) -> int:
    hash_int = int(hash_hex, 16)
    return 256 - hash_int.bit_length() if hash_int != 0 else 256


# ── Section renderers ──────────────────────────────────────────────────────────

def _render_header_fields(fields: dict) -> None:
    st.subheader("🧱 Block Header Fields (80 bytes)")

    import datetime
    ts = datetime.datetime.utcfromtimestamp(fields["timestamp"]).strftime("%Y-%m-%d %H:%M:%S UTC")

    data = [
        ("Version",             f"{fields['version']}",             "Mining protocol version. Signals which soft-forks the miner supports."),
        ("Previous Block Hash", f"`{fields['prev_hash']}`",         "SHA-256² hash of the previous block — links the chain cryptographically."),
        ("Merkle Root",         f"`{fields['merkle']}`",            "Root of the Merkle tree of all transactions in this block."),
        ("Timestamp",           f"{fields['timestamp']}  ({ts})",   "Unix timestamp when the miner started hashing this header."),
        ("Bits",                f"`{fields['bits']:#010x}`",        "Compact encoding of the difficulty target threshold."),
        ("Nonce",               f"{fields['nonce']:,}",             "32-bit value miners iterate to find a valid hash."),
    ]

    for name, value, explanation in data:
        col1, col2 = st.columns([1, 2])
        with col1:
            st.markdown(f"**{name}**")
            st.caption(explanation)
        with col2:
            st.markdown(value)
        st.divider()


def _render_byte_map(header_hex: str) -> None:
    st.subheader("🗺️ Header Byte Map (80 bytes)")

    fig = go.Figure()
    for name, start, end, color in HEADER_FIELDS:
        length = end - start
        fig.add_trace(go.Bar(
            x=[length],
            y=["Header"],
            orientation="h",
            name=f"{name} ({length} B)",
            marker_color=color,
            text=f"{name}<br>{length} bytes",
            textposition="inside",
            insidetextanchor="middle",
        ))

    fig.update_layout(
        barmode="stack",
        title="80-byte block header — field layout",
        xaxis=dict(title="Byte offset", range=[0, 80]),
        yaxis=dict(showticklabels=False),
        legend=dict(orientation="h", y=-0.4),
        height=180,
        margin=dict(t=40, b=100, l=20, r=20),
    )
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("🔍 Raw hex dump by field"):
        raw = bytes.fromhex(header_hex)
        for name, start, end, color in HEADER_FIELDS:
            chunk = header_hex[start*2 : end*2]
            st.markdown(f"**{name}** (`bytes {start}–{end-1}`)")
            st.code(chunk, language=None)


def _render_pow_verification(header_hex: str, fields: dict) -> None:
    st.subheader("✅ Proof of Work Verification (local · hashlib)")

    raw    = bytes.fromhex(header_hex)
    hash1  = hashlib.sha256(raw).digest()
    hash2  = hashlib.sha256(hash1).digest()
    computed_hash = hash2[::-1].hex()

    target     = bits_to_target(fields["bits"])
    hash_int   = int(computed_hash, 16)
    is_valid   = hash_int <= target
    target_hex = f"{target:064x}"

    st.markdown("**Step 1 — SHA256(raw header bytes)**")
    st.code(hash1.hex(), language=None)

    st.markdown("**Step 2 — SHA256( result of step 1 )**")
    st.code(hash2.hex(), language=None)

    st.markdown("**Step 3 — Reverse byte order (Bitcoin convention)**")
    st.code(computed_hash, language=None)

    st.divider()

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Computed hash**")
        st.code(computed_hash, language=None)
    with col2:
        st.markdown("**Target threshold**")
        st.code(target_hex, language=None)

    if is_valid:
        st.success(
            f"✅ Valid Proof of Work — hash < target  "
            f"({count_leading_zero_bits(computed_hash)} leading zero bits)"
        )
    else:
        st.error("❌ Invalid — hash exceeds target (this should never happen for a real block)")

    _render_hash_vs_target(computed_hash, target_hex)


def _render_hash_vs_target(hash_hex: str, target_hex: str) -> None:
    st.subheader("🎯 Hash vs Target — 256-bit comparison")

    leading_zeros = count_leading_zero_bits(hash_hex)
    target_zeros  = count_leading_zero_bits(target_hex)

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=[leading_zeros],
        y=["Block Hash"],
        orientation="h",
        name=f"Zero bits ({leading_zeros})",
        marker_color="#ef4444",
        text=f"{leading_zeros} zero bits",
        textposition="inside",
    ))
    fig.add_trace(go.Bar(
        x=[256 - leading_zeros],
        y=["Block Hash"],
        orientation="h",
        name=f"Non-zero bits ({256 - leading_zeros})",
        marker_color="#3b82f6",
        text=f"{256 - leading_zeros} bits",
        textposition="inside",
        showlegend=False,
    ))
    fig.add_trace(go.Bar(
        x=[target_zeros],
        y=["Target"],
        orientation="h",
        name=f"Target zero bits ({target_zeros})",
        marker_color="#f97316",
        text=f"{target_zeros} zero bits",
        textposition="inside",
        showlegend=False,
    ))
    fig.add_trace(go.Bar(
        x=[256 - target_zeros],
        y=["Target"],
        orientation="h",
        name=f"Target free bits ({256 - target_zeros})",
        marker_color="#6b7280",
        text=f"{256 - target_zeros} bits",
        textposition="inside",
        showlegend=False,
    ))

    fig.update_layout(
        barmode="stack",
        title="Block hash vs difficulty target — leading zero bits",
        xaxis=dict(title="Bits (out of 256)", range=[0, 256]),
        legend=dict(orientation="h", y=-0.3),
        height=250,
        margin=dict(t=40, b=80, l=20, r=20),
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        f"The block hash has **{leading_zeros} leading zero bits**, "
        f"which is more than the **{target_zeros} required by the target**. "
        "This proves the miner performed the required amount of computational work."
    )


# ── Main render ────────────────────────────────────────────────────────────────

def render() -> None:
    st.header("M2 — Block Header Analyzer")
    st.caption("Inspect the 80-byte block header and verify Proof of Work locally using hashlib")

    # ── Block selection ────────────────────────────────────────────────────────
    if "m2_selected_hash" not in st.session_state:
        st.session_state["m2_selected_hash"] = ""

    col1, col2 = st.columns([3, 1])
    with col1:
        typed_hash = st.text_input(
            "Block hash",
            placeholder="Enter a block hash or load the latest block →",
            key="m2_hash_input",
        )
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        load_latest = st.button("⬇️ Load latest block", key="m2_latest")

    if load_latest:
        with st.spinner("Fetching latest block…"):
            try:
                latest = get_latest_block()
                st.session_state["m2_selected_hash"] = latest["id"]
            except Exception as exc:
                st.error(f"Could not fetch latest block: {exc}")
                return

    if typed_hash:
        st.session_state["m2_selected_hash"] = typed_hash

    block_hash_input = st.session_state["m2_selected_hash"]

    if not block_hash_input:
        st.info("Enter a block hash above or click **Load latest block** to begin.")
        return

    # ── Data loading ───────────────────────────────────────────────────────────
    @st.cache_data(ttl=300, show_spinner=False)
    def load_block_data(h: str):
        block      = get_block(h)
        header_hex = get_block_header_hex(h)
        return block, header_hex

    with st.spinner("Fetching block header…"):
        try:
            block, header_hex = load_block_data(block_hash_input.strip())
        except Exception as exc:
            st.error(f"⚠️ Could not fetch block: {exc}")
            return

    try:
        fields = parse_header(header_hex)
    except Exception as exc:
        st.error(f"⚠️ Could not parse header: {exc}")
        return

    st.success(f"Block **#{block['height']:,}** loaded — header: `{len(header_hex)//2}` bytes")

    # ── Render sections ────────────────────────────────────────────────────────
    st.divider()
    _render_header_fields(fields)
    st.divider()
    _render_byte_map(header_hex)
    st.divider()
    _render_pow_verification(header_hex, fields)