"""
Tamper-evidence tests for the hash-chained audit trail.

The README calls this "hash-chained, tamper-evident." That is a security claim,
and until now nothing demonstrated that the chain actually *detects* tampering
— only that it reported "chain intact" on an untampered file, which any
function that returns True would also do.

These tests write a real chain to a temp file and then modify it the way an
attacker would: editing a record in place, reordering, deleting, and inserting.
Each must be caught, and caught with the right reason.
"""

from __future__ import annotations

import json

import pytest

from backend.core import audit


@pytest.fixture
def chain(tmp_path, monkeypatch):
    """A real 3-entry chain in an isolated file."""
    log = tmp_path / "audit_log.jsonl"
    monkeypatch.setattr(audit, "AUDIT_LOG_PATH", str(log))
    return log


async def _append(scan_id: str, code_hash: str, verdict: str):
    return await audit.append_entry(scan_id, code_hash, verdict)


@pytest.fixture
def populated(chain, anyio_backend):
    import anyio

    async def build():
        await _append("scan-1", "a" * 64, "pass")
        await _append("scan-2", "b" * 64, "fail")
        await _append("scan-3", "c" * 64, "pass")

    anyio.run(build)
    return chain


def _entries(path):
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def _rewrite(path, entries):
    path.write_text("".join(json.dumps(e) + "\n" for e in entries))


# --------------------------------------------------------------------------- #
# Happy path
# --------------------------------------------------------------------------- #

def test_a_freshly_written_chain_verifies(populated):
    report = audit.verify_chain()
    assert report["valid"] is True
    assert report["entries_checked"] == 3
    assert report["broken_at"] is None
    assert report["reason"] == "chain intact"


def test_first_entry_links_to_genesis(populated):
    first = _entries(populated)[0]
    assert first["prev_hash"] == audit.GENESIS_PREV_HASH


def test_each_entry_links_to_its_predecessor(populated):
    entries = _entries(populated)
    for prev, cur in zip(entries, entries[1:]):
        assert cur["prev_hash"] == prev["entry_hash"]


def test_empty_chain_is_vacuously_valid(chain):
    report = audit.verify_chain()
    assert report["valid"] is True
    assert report["entries_checked"] == 0


# --------------------------------------------------------------------------- #
# Tamper detection — the actual security claim
# --------------------------------------------------------------------------- #

def test_editing_a_record_in_place_is_detected(populated):
    """The classic attack: flip a verdict and leave everything else alone."""
    entries = _entries(populated)
    entries[1]["verdict"] = "pass"  # was "fail"
    _rewrite(populated, entries)

    report = audit.verify_chain()
    assert report["valid"] is False
    assert report["broken_at"] == 1
    assert "entry_hash mismatch" in report["reason"]


def test_editing_the_code_hash_is_detected(populated):
    """Swapping which code a verdict refers to must not be silent."""
    entries = _entries(populated)
    entries[0]["code_hash"] = "f" * 64
    _rewrite(populated, entries)

    report = audit.verify_chain()
    assert report["valid"] is False
    assert report["broken_at"] == 0


def test_deleting_a_record_is_detected(populated):
    """Removing an inconvenient entry breaks the prev_hash link."""
    entries = _entries(populated)
    del entries[1]
    _rewrite(populated, entries)

    report = audit.verify_chain()
    assert report["valid"] is False
    assert "prev_hash mismatch" in report["reason"]


def test_reordering_records_is_detected(populated):
    entries = _entries(populated)
    entries[1], entries[2] = entries[2], entries[1]
    _rewrite(populated, entries)

    report = audit.verify_chain()
    assert report["valid"] is False
    assert "prev_hash mismatch" in report["reason"]


def test_appending_a_forged_record_is_detected(populated):
    """An attacker who does not know the chain state cannot append cleanly."""
    entries = _entries(populated)
    entries.append(
        {
            "scan_id": "forged",
            "timestamp": 1.0,
            "code_hash": "d" * 64,
            "verdict": "pass",
            "prev_hash": "0" * 64,      # wrong link
            "entry_hash": "e" * 64,     # wrong hash
        }
    )
    _rewrite(populated, entries)

    report = audit.verify_chain()
    assert report["valid"] is False
    assert report["broken_at"] == 3


def test_rehashing_a_tampered_record_still_breaks_the_link(populated):
    """A smarter attacker recomputes the edited record's own hash.

    That defeats check (a) but not check (b): the *next* record's prev_hash
    still points at the old value, so the chain is what provides the
    tamper-evidence, not the per-record hash alone. This is the test that
    justifies calling it a chain.
    """
    entries = _entries(populated)
    entries[0]["verdict"] = "fail"
    entries[0]["entry_hash"] = audit._hash_entry(entries[0])
    _rewrite(populated, entries)

    report = audit.verify_chain()
    assert report["valid"] is False
    # Entry 0 now self-verifies, so the break surfaces at entry 1's link.
    assert report["broken_at"] == 1
    assert "prev_hash mismatch" in report["reason"]


def test_report_names_the_scan_that_broke(populated):
    entries = _entries(populated)
    entries[2]["verdict"] = "fail"
    _rewrite(populated, entries)

    report = audit.verify_chain()
    assert report["valid"] is False
    assert report["scan_id"] == "scan-3"


@pytest.fixture
def anyio_backend():
    return "asyncio"
