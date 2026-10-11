"""Shared Claude client setup and model selection."""

import os
from collections.abc import Callable
from dataclasses import dataclass
from functools import cache

import anthropic
from dotenv import load_dotenv

from helpdesk.models import Triage

MODEL = "claude-opus-5-5"
HAIKU = "claude-haiku-5-5"

# Server-side fallback: if the model declines a request, the API retries it on a
# fallback model chosen by refusal category inside the same call.
FALLBACK_BETA = "server-side-fallback-2026-07-01"


@cache
def get_client() -> anthropic.Anthropic:
    load_dotenv()  # reads ANTHROPIC_API_KEY (and ANTHROPIC_BASE_URL, if set) from .env
    return anthropic.Anthropic()


# ---------- which model handles each call ----------

def needs_strong_model(t: Triage) -> bool:
    """Conservative routing: Opus for anything urgent, security-related, vague, or uncertain."""
    return (
        t.priority in ("P1", "P2")
        or t.category in ("security", "other")
        or t.confidence != "high"
        or t.possible_social_engineering
    )


def needs_strong_model_wide(t: Triage) -> bool:
    """Wider routing: Opus only for P1, security, or a low-confidence triage."""
    return t.priority == "P1" or t.category == "security" or t.confidence == "low" or t.possible_social_engineering


@dataclass(frozen=True)
class ModelPolicy:
    """The model for each kind of call. The agent model is chosen per ticket from its triage."""

    name: str
    triage: str
    agent: Callable[[Triage], str]
    blocked_reply: str


POLICIES = {
    p.name: p
    for p in [
        ModelPolicy("opus", MODEL, lambda t: MODEL, MODEL),
        ModelPolicy("haiku-triage", HAIKU, lambda t: MODEL, MODEL),
        ModelPolicy("haiku", HAIKU, lambda t: HAIKU, HAIKU),
        ModelPolicy("routed", HAIKU, lambda t: MODEL if needs_strong_model(t) else HAIKU, HAIKU),
        ModelPolicy("routed-wide", HAIKU, lambda t: MODEL if needs_strong_model_wide(t) else HAIKU, HAIKU),
        # Added after the first runs showed Haiku's misses were mostly in triage (category,
        # priority, blocking), not in the agent loop: keep triage on Opus, run the agent on Haiku.
        ModelPolicy("opus-triage", MODEL, lambda t: HAIKU, HAIKU),
    ]
}


def model_policy() -> ModelPolicy:
    """The policy named by HELPDESK_MODEL_POLICY (default "opus", every call on MODEL)."""
    load_dotenv()
    name = os.environ.get("HELPDESK_MODEL_POLICY", "opus")
    if name not in POLICIES:
        raise ValueError(f"Unknown HELPDESK_MODEL_POLICY {name!r}; choose from {', '.join(POLICIES)}")
    return POLICIES[name]
