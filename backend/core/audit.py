"""
backend/core/audit.py
=====================
Immutable, hash-chained audit trail for completed scans (Feature #8).

SRE / COMPLIANCE DESIGN NOTES
-----------------------------
In fintech, "what did the automated system decide, on what code, and when?" is a
regulator-facing question. The audit log is not a debugging convenience — it's a
tamper-evident record. Design choices:

  - HASH CHAIN: each entry stores prev_hash = sha256 of the *canonical
    serialization* of the previous entry. Any retroactive edit to entry N breaks
    the hash of N and every entry after it, so tampering is detectable by a single
    linear verification pass. This is the same primitive a blockchain uses,
    minus the distributed consensus we don't need for a single-writer log.

  - CANONICAL SERIALIZATION: we hash json.dumps(..., sort_keys=True,
    separators=(",",":")). Deterministic key order + no whitespace means the hash
    is reproducible on verification. A non-canonical hash is a hash you can't
    re-verify — worse than useless.

  - APPEND-ONLY JSONL: one JSON object per line. Append-only is the whole point;
    we never rewrite the file. JSONL is grep-able and stream-verifiable without
    loading the entire file into memory (matters once you're millions of scans in).

  - GENESIS: the first entry's prev_hash is a fixed sentinel ("0"*64) so the chain
    has a well-defined, verifiable root.

  - WRITE SERIALIZATION: an asyncio.Lock guards append so two concurrent scans
    can't interleave and compute prev_hash off a stale tail (which would fork the
    chain). Correctness of the chain depends on strictly serialized writes.

  - We store code_hash, NOT code. Same compliance reason as the tracing layer:
    the audit log must be safe to hand to an auditor without leaking source/secrets.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import time
from typing import Any, Optional

logger = logging.getLogger("devguard.audit")

AUDIT_LOG_PATH = os.getenv("AUDIT_LOG_PATH", "data/audit_log.jsonl")
GENESIS_PREV_HASH = "0" * 64

_write_lock = asyncio.Lock()


def _canonical(entry: dict[str, Any]) -> str:
    """Deterministic serialization used for hashing (excludes the entry's own hash)."""
    return json.dumps(entry, sort_keys=True, separators=(",", ":"))


def _hash_entry(entry: dict[str, Any]) -> str:
    """Hash the canonical form of an entry's payload (without its 'entry_hash')."""
    payload = {k: v for k, v in entry.items() if k != "entry_hash"}
    return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()


def _read_last_entry() -> Optional[dict[str, Any]]:
    """Read the tail of the JSONL log to get prev_hash. Streaming, not full-load."""
    if not os.path.exists(AUDIT_LOG_PATH):
        return None
    last_line = None
    with open(AUDIT_LOG_PATH, "r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                last_line = line
    if last_line is None:
        return None
    try:
        return json.loads(last_line)
    except json.JSONDecodeError:
        logger.error("Audit log tail is corrupt — chain integrity at risk.")
        return None


async def append_entry(scan_id: str, code_hash: str, verdict: str) -> dict[str, Any]:
    """
    Append a completed-scan record to the chain. Returns the written entry.

    Fields: {scan_id, timestamp, code_hash, verdict, prev_hash, entry_hash}
    entry_hash is stored too so verification can confirm each link without
    recomputing under ambiguity about what was hashed.
    """
    os.makedirs(os.path.dirname(AUDIT_LOG_PATH) or ".", exist_ok=True)

    async with _write_lock:  # serialize writers -> no chain forks
        last = _read_last_entry()
        prev_hash = last["entry_hash"] if last else GENESIS_PREV_HASH

        entry = {
            "scan_id": scan_id,
            "timestamp": time.time(),
            "code_hash": code_hash,
            "verdict": verdict,
            "prev_hash": prev_hash,
        }
        entry["entry_hash"] = _hash_entry(entry)

        with open(AUDIT_LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")

    logger.info("Audit entry appended: scan_id=%s verdict=%s", scan_id, verdict)
    return entry


def read_all() -> list[dict[str, Any]]:
    """Return all audit entries (for the /audit-log endpoint)."""
    if not os.path.exists(AUDIT_LOG_PATH):
        return []
    entries = []
    with open(AUDIT_LOG_PATH, "r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                entries.append(json.loads(line))
    return entries


def verify_chain() -> dict[str, Any]:
    """
    Walk the chain and verify integrity (for /audit-log/verify).

    Returns a report: {valid, entries_checked, broken_at, reason}. We check both:
      (a) each entry's stored entry_hash matches a fresh recompute (no in-place edit)
      (b) each entry's prev_hash equals the previous entry's entry_hash (no reorder/insert/delete)
    """
    entries = read_all()
    expected_prev = GENESIS_PREV_HASH

    for idx, entry in enumerate(entries):
        # (a) recompute hash — detects field tampering
        recomputed = _hash_entry(entry)
        if recomputed != entry.get("entry_hash"):
            return {
                "valid": False,
                "entries_checked": idx + 1,
                "broken_at": idx,
                "scan_id": entry.get("scan_id"),
                "reason": "entry_hash mismatch (record was modified)",
            }
        # (b) link check — detects reordering/insertion/deletion
        if entry.get("prev_hash") != expected_prev:
            return {
                "valid": False,
                "entries_checked": idx + 1,
                "broken_at": idx,
                "scan_id": entry.get("scan_id"),
                "reason": "prev_hash mismatch (chain link broken)",
            }
        expected_prev = entry["entry_hash"]

    return {
        "valid": True,
        "entries_checked": len(entries),
        "broken_at": None,
        "reason": "chain intact",
    }
