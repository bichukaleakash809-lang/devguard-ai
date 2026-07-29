# The SigNoz MCP Decision

**Track:** T2, §6.5 of `docs/01_PLATFORM_MASTER.md`
**Date:** 2026-07-29
**Decision:** Take the second branch — **state precisely what happens.** The
differentiator claim is withdrawn until a real round trip exists.

---

## The question

`docs/01_PLATFORM_MASTER.md` §6.5 requires this to be resolved one way or the
other, and offers exactly two branches:

> - wire `_call_tool` to the real schema, capture a real request/response round
>   trip in `evidence/`, and keep the differentiator claim — now backed by
>   evidence; **or**
> - if a real MCP path is genuinely unavailable, **rewrite the README claim** to
>   say precisely what happens: agents consume their own telemetry through an
>   in-process telemetry shadow, with an MCP adapter ready behind a stable
>   interface.

The contract adds: *"An overclaim discovered by a judge costs more than the
feature was worth."*

## What the T0 audit found

Three separate problems (`docs/AUDIT.md` §3.B), all confirmed by reading the
code and reproduced at runtime:

1. **The transport is invented.** `_call_tool` POSTs
   `{"tool": ..., "arguments": ...}` to `/mcp/tools/call`. Standard MCP is
   JSON-RPC 2.0. The file carried its own TODO saying the shape was never
   verified.
2. **The default endpoint pointed at DevGuard itself.**
   `SIGNOZ_MCP_URL` defaulted to `http://localhost:8000` — the backend's own
   port under docker-compose. Out of the box, the "SigNoz MCP client" issued a
   real HTTP request to DevGuard, received a 404, and fell back. It has never
   spoken to SigNoz.
3. **The fallback misreported its own provenance.** `get_recent_cost_trend`
   returned `available=True` on failure, and the caller read that as "live" —
   so an in-process estimate was surfaced to users as retrieved SigNoz
   telemetry. Fixed in T1 phase 3 by adding an explicit `source` field.

## Why branch one is impossible here

Not a matter of effort. Every path to a SigNoz instance is closed in this
environment:

- **Every container registry is blocked by egress policy.** Docker Hub's CDN,
  GitHub Container Registry, Quay, Amazon ECR Public, and `registry.k8s.io` all
  return `403 to CONNECT` from the egress gateway. No SigNoz image can be
  pulled. Raw evidence: `docs/audit-evidence/t2/registry-egress-block.txt`.
- **SigNoz Cloud is unreachable.** `ingest.us.signoz.cloud` and `signoz.io`
  both fail to connect.

The Docker *daemon* itself is fine — it was not running, and starting it was
part of this track. The blocker is purely the registry egress policy.

Per LAW 5 ("de-risk before you build") the honest response to an unprovable
capability is to stop claiming it, not to build further on top of it.

## What was changed

- `SIGNOZ_MCP_URL` now defaults to **empty**, not to DevGuard's own port.
  "Not configured" is an explicit state rather than a wrong guess that fails
  quietly.
- New `MCPNotConfiguredError`, raised **before any network I/O** when no
  endpoint is set. "There is no server" and "the server did not answer" are
  different facts and are no longer reported identically.
- New `SignozMCPClient.is_configured()` and `capability_report()`. The latter
  is the honest stand-in for capability negotiation: it reports
  `verified_against_real_server: False` and `tool_list: None` rather than a
  hard-coded list of tool names nobody has confirmed exist.
- New `GET /telemetry-status` endpoint, so the claim is inspectable at runtime
  instead of being taken on trust from a README.
- The module docstring now leads with the status in plain language.
- `README.md` (T1 phase 5) already states the integration is unverified.

## What is true, and may be claimed

> DevGuard's agents consume their own telemetry as a decision input — recent
> spend, error rate, and per-CWE failure history — through an in-process
> telemetry shadow, behind a stable typed interface with a SigNoz MCP adapter
> ready to be wired. The MCP path itself is not yet verified against a live
> server.

That is accurate, and the self-observation behaviour it describes is real: the
router does change model tier based on measured spend.

## What may NOT be claimed until evidence exists

- "Agents query their own SigNoz telemetry via MCP"
- "MCP-based self-observation"
- Anything implying a verified SigNoz MCP integration

## What would close this out

1. Reach a SigNoz instance (needs the registry egress policy relaxed, or an
   external host).
2. Start the SigNoz MCP server and **enumerate its tools**; commit the list.
3. Point `_call_tool` at the real transport — likely an MCP SDK
   `ClientSession`, not the current HTTP envelope.
4. Capture one real request/response round trip into `docs/audit-evidence/`.
5. Reinstate the claim in the README, now backed by that artifact.

Only `_call_tool` and the three `_parse_*` methods need to change. Nothing
downstream depends on either — that part of the original design was sound.
