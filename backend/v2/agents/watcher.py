"""
watcher.py — §6's Watcher. Deterministic, no model, RuntimeEvidenceProvider only.

§6 classifies Watcher as `deterministic` with the tool allowlist
`RuntimeEvidenceProvider only`. That is not a simplification for convenience: an
LLM cannot make an exit code more true, and putting one on the detection path
would mean the *one* piece of evidence §7 will not let us do without could be
hallucinated. Detection is the last place in this system that should be
probabilistic.

What this produces is `RUNTIME` + `TRUSTED_SYSTEM` + `OBSERVED` evidence — the
only source in §7 that can establish that something actually happened, as
opposed to that a catalog says something is a certain way.
"""

from __future__ import annotations

import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence

from backend.v2.evidence import (
    EvidenceBuilder, EvidenceConfidence, EvidenceSource, EvidenceTrust,
)
from backend.v2.handoff import AgentDecision, AgentHandoff, now
from backend.v2.proofpack import ProofPack

#: dbt reports a failing model in a stable shape. Parsed rather than pattern-
#: matched loosely, because the captured column name is what the Cartographer
#: resolves to a URN — a sloppy match here sends the whole loop at the wrong
#: asset.
_DBT_ERROR = re.compile(
    r"\[ERROR\]:\s+in model (?P<model>\S+) \((?P<path>[^)]+)\)", re.MULTILINE
)
_MISSING_COLUMN = re.compile(r'column "(?P<column>[^"]+)" does not exist')
_DBT_TOTALS = re.compile(
    r"Done\. PASS=(?P<passed>\d+) WARN=(?P<warn>\d+) ERROR=(?P<error>\d+) "
    r"SKIP=(?P<skip>\d+)"
)


def _readable_command(command: Sequence[str]) -> str:
    """Render a command so the evidence reads the same on any machine.

    The interpreter is usually an absolute path into whatever virtualenv the
    operator happens to be using. Baking that into an evidence claim makes the
    artifact non-reproducible and leaks nothing useful — a judge reading
    `dbt run` learns everything `.../scratchpad/dhvenv/bin/dbt run` would tell
    them, and can actually re-run it.
    """
    argv = list(command)
    if argv and argv[0].startswith("/"):
        argv[0] = Path(argv[0]).name
    return " ".join(argv)


@dataclass(frozen=True)
class RuntimeFailure:
    """A parsed, structured failure. Never free text across a boundary (§7)."""

    command: str
    exit_code: int
    failing_model: Optional[str]
    failing_model_path: Optional[str]
    missing_column: Optional[str]
    passed: int
    errored: int
    skipped: int
    stdout_tail: str

    @property
    def is_failure(self) -> bool:
        return self.exit_code != 0 or self.errored > 0


class RuntimeEvidenceProvider:
    """Runs a real command and reports exactly what happened.

    Note there is no "expected failure" mode and no simulation switch. If the
    command passes, `observe` says it passed. A provider that could be told what
    to find would make every RUNTIME evidence item worthless.
    """

    def __init__(self, *, cwd: str | Path = ".", timeout_s: float = 600.0) -> None:
        self.cwd = Path(cwd)
        self.timeout_s = timeout_s

    def observe(self, command: Sequence[str], *, env: Optional[dict] = None) -> RuntimeFailure:
        completed = subprocess.run(
            list(command), cwd=self.cwd, env=env, capture_output=True,
            text=True, timeout=self.timeout_s,
        )
        combined = completed.stdout + completed.stderr
        clean = re.sub(r"\x1b\[[0-9;]*m", "", combined)

        model = path = column = None
        if (m := _DBT_ERROR.search(clean)):
            model, path = m.group("model"), m.group("path")
        if (m := _MISSING_COLUMN.search(clean)):
            column = m.group("column")

        passed = errored = skipped = 0
        if (m := _DBT_TOTALS.search(clean)):
            passed = int(m.group("passed"))
            errored = int(m.group("error"))
            skipped = int(m.group("skip"))

        return RuntimeFailure(
            command=_readable_command(command),
            exit_code=completed.returncode,
            failing_model=model,
            failing_model_path=path,
            missing_column=column,
            passed=passed, errored=errored, skipped=skipped,
            stdout_tail=clean[-8000:],
        )


class Watcher:
    """Turns an observed failure into typed evidence and a handoff."""

    NAME = "watcher"

    def __init__(self, builder: EvidenceBuilder, pack: ProofPack) -> None:
        self._builder = builder
        self._pack = pack

    def run(self, failure: RuntimeFailure, *, to_agent: str = "cartographer"):
        started = now()
        t0 = time.monotonic()

        raw_ref = self._pack.write(
            "watcher/dbt-run.txt",
            f"$ {failure.command}\nexit code: {failure.exit_code}\n\n{failure.stdout_tail}",
            note="Raw output of the command the Watcher observed.",
        )

        items = [self._builder.make(
            source=EvidenceSource.RUNTIME,
            trust=EvidenceTrust.TRUSTED_SYSTEM,
            confidence=EvidenceConfidence.OBSERVED,
            claim=f"`{failure.command}` exited {failure.exit_code} "
                  f"(PASS={failure.passed} ERROR={failure.errored} SKIP={failure.skipped})",
            raw_ref=raw_ref,
        )]

        if failure.failing_model:
            items.append(self._builder.make(
                source=EvidenceSource.RUNTIME,
                trust=EvidenceTrust.TRUSTED_SYSTEM,
                confidence=EvidenceConfidence.OBSERVED,
                claim=f"model {failure.failing_model} failed to build "
                      f"({failure.failing_model_path})",
                raw_ref=raw_ref,
            ))
        if failure.missing_column:
            items.append(self._builder.make(
                source=EvidenceSource.RUNTIME,
                trust=EvidenceTrust.TRUSTED_SYSTEM,
                confidence=EvidenceConfidence.OBSERVED,
                claim=f'database reports column "{failure.missing_column}" does not exist',
                raw_ref=raw_ref,
            ))
        if failure.skipped:
            # The quiet one, and the reason this incident is drift rather than an
            # outage: a SKIPped model leaves a stale table behind that nothing
            # downstream complains about. Recorded as its own claim so the
            # Diagnostician can reason about it separately.
            items.append(self._builder.make(
                source=EvidenceSource.RUNTIME,
                trust=EvidenceTrust.TRUSTED_SYSTEM,
                confidence=EvidenceConfidence.OBSERVED,
                claim=f"{failure.skipped} downstream model(s) SKIPped — not rebuilt, "
                      f"not dropped, therefore stale",
                raw_ref=raw_ref,
            ))

        decision = AgentDecision.OK if failure.is_failure else AgentDecision.INSUFFICIENT_EVIDENCE
        rationale = (
            f"Observed a real failure in {failure.command}."
            if failure.is_failure else
            "The command succeeded. There is nothing to diagnose, and inventing "
            "one would be a LAW 3 violation."
        )
        handoff = AgentHandoff(
            from_agent=self.NAME, to_agent=to_agent,
            incident_id=self._builder._incident_id,
            evidence_ids=tuple(e.id for e in items),
            decision=decision, rationale=rationale,
            started_at=started, ended_at=now(),
            tokens=0, model=None,  # deterministic: no model, no tokens
        )
        _ = t0
        return items, handoff
