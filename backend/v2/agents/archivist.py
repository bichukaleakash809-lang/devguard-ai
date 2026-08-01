"""
archivist.py — §6's Archivist: capability negotiation, then prior knowledge.

Two responsibilities, and the first one is the interesting one.

**Capability negotiation** (§4 step 4). §5's trap: *"`search_documents` /
`grep_documents` are **automatically hidden when the catalog has no documents**
— i.e. on a clean instance and during incident #1. Code must negotiate
capabilities and degrade deliberately, never throw."*

So the Archivist's job on incident #1 is to *not find anything*, and to say so
in a way that is distinguishable from an error. That distinction is the whole
point: "there is no prior runbook for this" and "the document search broke" lead
to completely different downstream behaviour, and a system that conflates them
will happily report a clean bill of health when its retrieval is down.

`AgentDecision.DEGRADED` carries that distinction, and D0 already confirmed the
trap is real: the live server offered 18 tools, and both document tools were
among the absent ones (integration finding 4).

**Prior knowledge.** Anything the documents *do* return is human-authored text
from a shared catalog, so it is `DATAHUB_DOCUMENT` + `UNTRUSTED_TEXT` by
construction — the Evidence model refuses to let it be anything else — and it
goes through the Sentinel before any agent reads it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional

from backend.v2.datahub_client import Capabilities, DataHubMCPClient
from backend.v2.evidence import (
    Evidence, EvidenceBuilder, EvidenceConfidence, EvidenceSource, EvidenceTrust,
)
from backend.v2.handoff import (
    AGENT_TOOL_ALLOWLISTS, AgentDecision, AgentHandoff, ToolCallRecord, now,
)
from backend.v2.proofpack import ProofPack
from backend.v2.sentinel import ScreenedText, Sentinel

DOCUMENT_TOOLS = frozenset({"search_documents", "grep_documents"})


@dataclass(frozen=True)
class PriorKnowledge:
    """What the Archivist found, and — equally important — how hard it could look."""

    documents_available: bool
    """False when the catalog has no documents and the tools are hidden."""

    documents: tuple[ScreenedText, ...]
    negotiated_tools: frozenset[str]
    missing_from_contract: frozenset[str]

    @property
    def has_prior_incident(self) -> bool:
        return bool(self.documents)

    @property
    def summary(self) -> str:
        """§8's 'PREVIOUS VERIFIED INCIDENT' line, or an explicit miss."""
        if not self.documents_available:
            return ("NO PRIOR KNOWLEDGE — document retrieval is unavailable on this "
                    "catalog (no documents exist, so the tools are hidden). This is "
                    "an explicit miss, not a clean result.")
        if not self.documents:
            return "NO PRIOR KNOWLEDGE — document retrieval ran and matched nothing."
        return f"PREVIOUS VERIFIED INCIDENT — {len(self.documents)} document(s) retrieved."


class Archivist:
    """§6: LLM + tools; allowlist `search_documents`, `grep_documents`, tool-list.

    Runs without a model here. Retrieval and capability negotiation are both
    mechanical, and §6 explicitly endorses not putting a model where one is not
    needed. When the Diagnostician's reasoning step lands (D5), the retrieved
    text is what it consumes — fenced, never as instruction.
    """

    NAME = "archivist"

    def __init__(self, client: DataHubMCPClient, builder: EvidenceBuilder,
                 pack: ProofPack, sentinel: Optional[Sentinel] = None) -> None:
        self._client = client
        self._builder = builder
        self._pack = pack
        self._sentinel = sentinel or Sentinel()

    # ------------------------------------------------------------------ step 4

    def negotiate(self) -> tuple[Capabilities, Evidence]:
        """§4 step 4: list the tools and record the capability set as evidence."""
        caps = self._client.capabilities
        raw_ref = self._pack.write(
            "archivist/capabilities.json",
            {
                "serverInfo": {"name": caps.server_name, "version": caps.server_version},
                "protocolVersion": caps.protocol_version,
                "tool_count": len(caps.tools),
                "tools": sorted(caps.tool_names),
                "input_schemas": {n: caps.describe(n) for n in sorted(caps.tool_names)},
            },
            note="The negotiated capability set for THIS run. Not a constant.",
        )
        evidence = self._builder.make(
            source=EvidenceSource.RUNTIME,
            trust=EvidenceTrust.TRUSTED_SYSTEM,
            confidence=EvidenceConfidence.OBSERVED,
            claim=f"MCP server offered {len(caps.tools)} tools; "
                  f"document tools {'present' if self._docs_available(caps) else 'hidden'}",
            raw_ref=raw_ref,
        )
        return caps, evidence

    @staticmethod
    def _docs_available(caps: Capabilities) -> bool:
        return bool(DOCUMENT_TOOLS & caps.tool_names)

    # ------------------------------------------------------------------ step 8

    def retrieve(self, query: str) -> tuple[PriorKnowledge, list[Evidence], list[ToolCallRecord]]:
        caps = self._client.capabilities
        available = self._docs_available(caps)
        records: list[ToolCallRecord] = []
        evidence: list[Evidence] = []
        screened: list[ScreenedText] = []

        if available:
            for tool in sorted(DOCUMENT_TOOLS & caps.tool_names):
                # Finding 18: read the live schema rather than assuming `query`.
                schema = caps.describe(tool)
                args = self._arguments_for(schema, query)
                result = self._client.call(self.NAME, tool, args)
                ref = self._pack.write(
                    f"archivist/{tool}.json",
                    {"arguments": args, "ok": result.ok, "text": result.text,
                     "error": result.error},
                    note="Raw document-retrieval response.",
                )
                records.append(result.record(ref))
                if result.ok and result.text:
                    for field, text in self._extract_documents(result.text):
                        screened.append(self._sentinel.screen(field, text))

            for doc in screened:
                evidence.append(self._builder.make(
                    source=EvidenceSource.DATAHUB_DOCUMENT,
                    # The Evidence model would reject anything else here; stated
                    # explicitly so the intent is legible at the call site too.
                    trust=EvidenceTrust.UNTRUSTED_TEXT,
                    confidence=EvidenceConfidence.OBSERVED,
                    claim=f"retrieved prior document {doc.field} "
                          f"(injection screen: {doc.risk.value})",
                    raw_ref=self._pack.write(
                        f"archivist/document-{doc.field}.txt", doc.original,
                        note="UNTRUSTED. Fenced before entering any prompt.",
                    ),
                ))
        else:
            # The deliberate degradation. Recorded as RUNTIME evidence because
            # "the tools were not offered" is an observed fact about this run,
            # and the Diagnostician must be able to see that retrieval was
            # unavailable rather than merely empty.
            evidence.append(self._builder.make(
                source=EvidenceSource.RUNTIME,
                trust=EvidenceTrust.TRUSTED_SYSTEM,
                confidence=EvidenceConfidence.OBSERVED,
                claim="document retrieval unavailable — search_documents/grep_documents "
                      "are not offered by this catalog (§5's documented behaviour)",
                raw_ref=self._pack.write(
                    "archivist/documents-unavailable.txt",
                    "search_documents and grep_documents are absent from the negotiated "
                    "tool set.\n\n"
                    "Per 05_DATAHUB_MASTER §5 these tools are hidden automatically when "
                    "the catalog holds no documents. This is expected on incident #1 and "
                    "is reported as DEGRADED, never as a clean 'no prior incidents'.\n\n"
                    f"negotiated tools ({len(caps.tools)}): {sorted(caps.tool_names)}\n",
                    note="Explicit miss. Not an error, and not a clean result.",
                ),
            ))

        knowledge = PriorKnowledge(
            documents_available=available,
            documents=tuple(screened),
            negotiated_tools=caps.tool_names,
            missing_from_contract=caps.missing_from(
                AGENT_TOOL_ALLOWLISTS[self.NAME] | DOCUMENT_TOOLS
            ),
        )
        return knowledge, evidence, records

    def run(self, query: str, *, to_agent: str = "cartographer"):
        started = now()
        caps_evidence_pair = self.negotiate()
        knowledge, evidence, records = self.retrieve(query)
        all_evidence = [caps_evidence_pair[1], *evidence]

        decision = (AgentDecision.OK if knowledge.documents_available
                    else AgentDecision.DEGRADED)
        handoff = AgentHandoff(
            from_agent=self.NAME, to_agent=to_agent,
            incident_id=self._builder._incident_id,
            evidence_ids=tuple(e.id for e in all_evidence),
            decision=decision,
            rationale=knowledge.summary,
            started_at=started, ended_at=now(),
            tokens=0, model=None,
            tool_calls=tuple(records),
        )
        return knowledge, all_evidence, handoff

    # ------------------------------------------------------------------ helpers

    @staticmethod
    def _arguments_for(schema: dict, query: str) -> dict:
        """Build arguments from the LIVE schema (finding 18).

        Picks the first required string property and passes the query as its
        value. Crude, but it is driven by what the server says it wants rather
        than by what the contract said it would want, which is the point.
        """
        props = (schema or {}).get("properties", {})
        required = (schema or {}).get("required", [])
        for name in required:
            if props.get(name, {}).get("type") == "string":
                return {name: query}
        for name in ("query", "search", "text", "pattern"):
            if name in props:
                return {name: query}
        return {"query": query}

    @staticmethod
    def _extract_documents(text: str) -> list[tuple[str, str]]:
        """Pull (label, body) pairs out of a document-search response."""
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return [("document-0", text)]
        docs = payload.get("documents") or payload.get("results") or []
        out: list[tuple[str, str]] = []
        for i, doc in enumerate(docs if isinstance(docs, list) else []):
            if isinstance(doc, dict):
                label = doc.get("urn") or doc.get("title") or f"document-{i}"
                body = json.dumps(doc, indent=2)
            else:
                label, body = f"document-{i}", str(doc)
            out.append((str(label).replace("/", "_").replace(":", "_"), body))
        return out
