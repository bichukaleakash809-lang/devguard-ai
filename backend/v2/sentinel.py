"""
sentinel.py — §6's Sentinel, on the catalog-text side.

§6 gives Sentinel two jobs; this module is the first one: *"Fence and screen
**all** catalog-sourced text for injection."* (Scanning the proposed fix is the
Surgeon-side job and lands with the Surgeon in D6.)

§11.2 is the requirement being met: *"all catalog free-text is UNTRUSTED_TEXT,
fenced in prompts, never instruction. **No tool call may be selected on the
basis of catalog free-text.**"*

Design note worth stating plainly, because overclaiming here would be its own
LAW 3 problem: **detection is a signal, not a defence.** The pattern list below
will miss novel phrasings, and it is not what makes DevGuard safe. What makes
DevGuard safe is architectural — the agent that reads this text
(Diagnostician) holds zero tools, so text that successfully manipulates its
reasoning still cannot cause an action. The screen exists to *surface* attempts
as evidence (§11.7's demo beat), and to refuse to let untrusted text stand alone
as justification. `backend/core/ai_agent.py` already ships the fencing primitive
used here; it is reused rather than reimplemented.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Iterable

# Imported from the leaf module, not from ai_agent: the definitions are shared
# (never duplicated), but fencing a catalog string must not require the
# OpenTelemetry and LLM stack that ai_agent pulls in.
from backend.core.untrusted import UNTRUSTED_CONTENT_RULE, fence_untrusted

__all__ = [
    "InjectionRisk", "InjectionFinding", "ScreenedText", "Sentinel",
    "UNTRUSTED_CONTENT_RULE", "fence_untrusted",
]


class InjectionRisk(str, Enum):
    NONE = "NONE"
    SUSPICIOUS = "SUSPICIOUS"
    """Contains instruction-shaped language. Worth surfacing; not proof."""
    LIKELY = "LIKELY"
    """Contains a recognised injection pattern aimed at an agent."""


#: (name, pattern, risk). Ordered most-specific first.
#:
#: Every pattern here is aimed at *instruction-shaped text in a metadata field*.
#: A dataset description has no legitimate reason to address the reader as an
#: agent, which is what makes these worth flagging at all.
_PATTERNS: tuple[tuple[str, re.Pattern, InjectionRisk], ...] = (
    ("override-previous",
     re.compile(r"(?i)\b(ignore|disregard|forget|override)\b[^.\n]{0,40}\b"
                r"(previous|prior|above|earlier|all)\b[^.\n]{0,20}\b"
                r"(instruction|prompt|rule|direction|context)s?\b"),
     InjectionRisk.LIKELY),
    ("role-reassignment",
     re.compile(r"(?i)\b(you are now|act as|from now on,? you|new (system )?prompt|"
                r"system\s*:\s*)"),
     InjectionRisk.LIKELY),
    ("action-directive",
     re.compile(r"(?i)\b(mark|set|tag|classify|approve|certify|flag)\b[^.\n]{0,30}\b"
                r"(this|the)\b[^.\n]{0,30}\b"
                r"(dataset|table|column|asset|model|change|fix)\b"),
     InjectionRisk.LIKELY),
    ("suppress-findings",
     re.compile(r"(?i)\b(do not|don't|never)\b[^.\n]{0,30}\b"
                r"(report|raise|flag|alert|escalate|log)\b"),
     InjectionRisk.LIKELY),
    ("exfiltration",
     re.compile(r"(?i)\b(reveal|print|output|send|post|leak|exfiltrate)\b[^.\n]{0,30}\b"
                r"(token|secret|credential|api[_ ]?key|password|environment)"),
     InjectionRisk.LIKELY),
    ("tool-naming",
     re.compile(r"(?i)\b(call|invoke|run|use)\b[^.\n]{0,20}\b"
                r"(add_tags|update_description|save_document|add_owners|"
                r"add_structured_properties|raiseIncident)\b"),
     InjectionRisk.LIKELY),
    ("imperative-to-agent",
     re.compile(r"(?i)\b(assistant|agent|ai|llm|model|claude|gpt)\b[^.\n]{0,20}[:,]\s*\w"),
     InjectionRisk.SUSPICIOUS),
    ("fence-breakout",
     re.compile(r"<<<\s*(END\s+)?UNTRUSTED|```\s*system|\[/?INST\]|<\|im_(start|end)\|>"),
     InjectionRisk.SUSPICIOUS),
)


@dataclass(frozen=True)
class InjectionFinding:
    pattern: str
    risk: InjectionRisk
    excerpt: str
    field: str


@dataclass(frozen=True)
class ScreenedText:
    """Catalog text, after screening, in the only form agents may consume."""

    field: str
    original: str
    findings: tuple[InjectionFinding, ...]

    @property
    def risk(self) -> InjectionRisk:
        if any(f.risk is InjectionRisk.LIKELY for f in self.findings):
            return InjectionRisk.LIKELY
        if self.findings:
            return InjectionRisk.SUSPICIOUS
        return InjectionRisk.NONE

    @property
    def fenced(self) -> str:
        """The ONLY representation that may enter a prompt.

        There is no accessor that returns the raw string for prompt use. Making
        the unsafe path unavailable is more reliable than documenting that it
        should not be taken.
        """
        return fence_untrusted(self.field, self.original)


class Sentinel:
    """Screens catalog free-text. Holds no DataHub tools, by §6's table."""

    NAME = "sentinel"

    def screen(self, field: str, text: str | None) -> ScreenedText:
        text = text or ""
        findings: list[InjectionFinding] = []
        for name, pattern, risk in _PATTERNS:
            for match in pattern.finditer(text):
                start = max(0, match.start() - 30)
                findings.append(InjectionFinding(
                    pattern=name, risk=risk, field=field,
                    excerpt=text[start:match.end() + 30].replace("\n", " ").strip(),
                ))
        return ScreenedText(field=field, original=text, findings=tuple(findings))

    def screen_all(self, fields: Iterable[tuple[str, str | None]]) -> tuple[ScreenedText, ...]:
        return tuple(self.screen(name, value) for name, value in fields)

    @staticmethod
    def build_prompt_context(screened: Iterable[ScreenedText]) -> str:
        """Assemble fenced catalog text for a prompt, rule first.

        The security rule is prepended rather than appended because it must be
        read before the untrusted content, not after it.
        """
        blocks = [s.fenced for s in screened]
        return UNTRUSTED_CONTENT_RULE + "\n\n" + "\n\n".join(blocks)
