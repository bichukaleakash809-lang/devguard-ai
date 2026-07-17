"""
groq_client.py — Thin wrapper exposing a module-level groq_client object
with an async .chat.completions.create(...) interface, matching what
backend/core/ai_agent.py expects.

WHY THIS FILE EXISTS:
ai_agent.py was written assuming an async Groq client is importable as
rom groq_client import groq_client. The real Groq Python SDK exposes
AsyncGroq — we instantiate it once here, reading the API key from the
environment (GROQ_API_KEY), and expose it under the expected name.
"""

import os
from groq import AsyncGroq

_api_key = os.environ.get("GROQ_API_KEY")
if not _api_key:
    raise RuntimeError(
        "GROQ_API_KEY environment variable is not set. "
        "Set it with: $env:GROQ_API_KEY=\"your_key_here\" (PowerShell)"
    )

groq_client = AsyncGroq(api_key=_api_key)
