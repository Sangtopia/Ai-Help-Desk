"""Shared Claude client setup."""

from functools import cache

import anthropic
from dotenv import load_dotenv

MODEL = "claude-opus-5-5"

# Server-side fallback: if the model declines a request, the API retries it on a
# fallback model chosen by refusal category inside the same call.
FALLBACK_BETA = "server-side-fallback-2026-07-01"


@cache
def get_client() -> anthropic.Anthropic:
    load_dotenv()  # reads ANTHROPIC_API_KEY from .env
    return anthropic.Anthropic()
