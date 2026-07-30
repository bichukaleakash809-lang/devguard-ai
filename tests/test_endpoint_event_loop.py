"""
Blocking file I/O must not run on the event loop.

FastAPI runs `async def` handlers directly on the loop, so any synchronous work
inside one stalls *every other in-flight request* for its whole duration — not
just the caller's. A single-worker deployment (the default for `uvicorn
backend.main:app`) has exactly one loop, so this is a whole-service stall.

THE DEFECT THESE TESTS EXIST FOR
--------------------------------
`GET /audit-log` was fixed for this earlier by moving `count_entries` and
`read_tail` into `asyncio.to_thread`. `GET /audit-log/verify` was not:

    @router.get("/audit-log/verify")
    async def verify_audit_log():
        report = audit.verify_chain()      # <- synchronous, on the loop

`verify_chain()` is inherently O(N) — verifying a hash chain means hashing every
record, and no amount of cleverness changes that. It is not the cost that is the
bug; it is the cost being paid on the event loop. Measured on real files:

      entries        file   verify_chain()
          100     0.03 MB      0.656 ms
        1,000     0.29 MB      6.207 ms
       10,000     2.88 MB     70.066 ms
       50,000    14.44 MB    352.938 ms

So one compliance check against a 50k-entry log froze the loop for ~350 ms, and
every concurrent scan, SLO poll and WebSocket frame waited it out. The audit log
only grows, so this degrades monotonically for the life of a deployment.

These tests assert the property directly: while the handler runs, the loop must
still be able to make progress.
"""

from __future__ import annotations

import asyncio
import json
import time

import pytest

from backend.api import router as api_router
from backend.core import audit


@pytest.fixture
def big_log(tmp_path, monkeypatch):
    """A chain large enough that a synchronous verify is unmistakable."""
    log = tmp_path / "audit_log.jsonl"
    monkeypatch.setattr(audit, "AUDIT_LOG_PATH", str(log))

    prev = audit.GENESIS_PREV_HASH
    with open(log, "w") as fh:
        for i in range(8000):
            e = {
                "scan_id": f"s{i}",
                "timestamp": 1.0,
                "code_hash": "a" * 64,
                "verdict": "pass",
                "prev_hash": prev,
            }
            e["entry_hash"] = audit._hash_entry(e)
            fh.write(json.dumps(e) + "\n")
            prev = e["entry_hash"]
    return log


async def _loop_starvation(coro) -> tuple[float, object]:
    """Run `coro` while a ticker tries to wake every millisecond.

    Returns the longest gap the ticker observed. If `coro` blocks the loop, the
    ticker cannot run at all for that whole span and the gap approaches the
    handler's full duration. If the work is off-thread, the ticker keeps its
    ~1 ms cadence throughout.
    """
    worst = 0.0
    stop = False
    running = asyncio.Event()

    async def ticker():
        nonlocal worst
        last = time.perf_counter()
        running.set()
        while not stop:
            await asyncio.sleep(0.001)
            now = time.perf_counter()
            worst = max(worst, now - last)
            last = now

    t = asyncio.ensure_future(ticker())
    # The ticker MUST be scheduled and have taken its baseline before the work
    # starts. Without this the ticker's first `last = perf_counter()` happens
    # after the blocking call has already finished, so it measures nothing and
    # the test passes vacuously — which is exactly what this harness did on its
    # first run against the known-blocking handler.
    await running.wait()
    await asyncio.sleep(0.005)
    worst = 0.0  # discard startup jitter; only the work window counts

    try:
        result = await coro
    finally:
        stop = True
        await t
    return worst, result


# --------------------------------------------------------------------------- #
# GET /audit-log/verify
# --------------------------------------------------------------------------- #

def test_verify_endpoint_does_not_block_the_event_loop(big_log):
    """The defect, measured rather than asserted by inspection.

    The handler's own duration is irrelevant here — what must stay small is how
    long the loop was unable to do anything else.
    """
    async def scenario():
        started = time.perf_counter()
        worst, report = await _loop_starvation(api_router.verify_audit_log())
        return worst, time.perf_counter() - started, report

    worst, elapsed, report = asyncio.run(scenario())

    assert report["valid"] is True
    assert report["entries_checked"] == 8000
    # Generous bound: the point is orders of magnitude, not a tight budget. A
    # synchronous verify parks the loop for essentially the whole `elapsed`.
    assert worst < 0.050, (
        f"the event loop was blocked for {worst * 1000:.1f} ms while "
        f"/audit-log/verify ran ({elapsed * 1000:.1f} ms total) — the chain walk "
        "is happening on the loop, so every concurrent request stalled with it"
    )


def test_verify_endpoint_still_returns_the_real_report(big_log):
    """Moving work off-thread must not change what the endpoint reports."""
    report = asyncio.run(api_router.verify_audit_log())
    direct = audit.verify_chain()
    assert report == direct


def test_verify_endpoint_still_raises_409_on_a_broken_chain(big_log):
    """The tamper path must survive the refactor — this is the security claim."""
    from fastapi import HTTPException

    entries = [json.loads(l) for l in big_log.read_text().splitlines() if l.strip()]
    entries[4000]["verdict"] = "fail"
    big_log.write_text("".join(json.dumps(e) + "\n" for e in entries))

    with pytest.raises(HTTPException) as exc:
        asyncio.run(api_router.verify_audit_log())
    assert exc.value.status_code == 409
    assert exc.value.detail["valid"] is False
    assert exc.value.detail["broken_at"] == 4000


# --------------------------------------------------------------------------- #
# GET /audit-log — already off-thread; guard against regression
# --------------------------------------------------------------------------- #

def test_audit_log_endpoint_does_not_block_the_event_loop(big_log):
    """This one was fixed earlier. Assert it stays fixed."""
    async def scenario():
        return await _loop_starvation(api_router.get_audit_log(limit=100))

    worst, body = asyncio.run(scenario())
    assert body["count"] == 8000
    assert len(body["entries"]) == 100
    assert worst < 0.050, (
        f"GET /audit-log blocked the loop for {worst * 1000:.1f} ms — the "
        "to_thread offload regressed"
    )


def test_a_trivially_small_log_is_still_correct(tmp_path, monkeypatch):
    """Offloading must not break the empty and near-empty cases."""
    log = tmp_path / "audit_log.jsonl"
    monkeypatch.setattr(audit, "AUDIT_LOG_PATH", str(log))
    log.write_text("")

    report = asyncio.run(api_router.verify_audit_log())
    assert report["valid"] is True
    assert report["entries_checked"] == 0
