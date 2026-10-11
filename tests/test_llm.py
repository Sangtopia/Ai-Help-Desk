import pytest

from helpdesk.llm import HAIKU, MODEL, POLICIES, model_policy, needs_strong_model, needs_strong_model_wide
from helpdesk.models import Triage


def triage(**overrides) -> Triage:
    fields = {"category": "printing", "priority": "P3", "user_blocked": False, "summary": "s",
              "possible_social_engineering": False, "confidence": "high"} | overrides
    return Triage(**fields)


def test_default_policy_is_all_opus(monkeypatch):
    monkeypatch.delenv("HELPDESK_MODEL_POLICY", raising=False)
    policy = model_policy()
    assert (policy.triage, policy.agent(triage()), policy.blocked_reply) == (MODEL, MODEL, MODEL)


def test_unknown_policy_is_an_error(monkeypatch):
    monkeypatch.setenv("HELPDESK_MODEL_POLICY", "gpt")
    with pytest.raises(ValueError):
        model_policy()


@pytest.mark.parametrize("overrides", [
    {"priority": "P1"}, {"priority": "P2"}, {"category": "security"}, {"category": "other"},
    {"confidence": "medium"}, {"confidence": "low"}, {"possible_social_engineering": True},
])
def test_conservative_routing_sends_hard_tickets_to_opus(overrides):
    assert needs_strong_model(triage(**overrides))
    assert POLICIES["routed"].agent(triage(**overrides)) == MODEL


def test_routine_ticket_goes_to_haiku():
    assert POLICIES["routed"].agent(triage()) == HAIKU
    assert POLICIES["routed-wide"].agent(triage()) == HAIKU


@pytest.mark.parametrize("overrides, strong", [
    ({"priority": "P2"}, False), ({"confidence": "medium"}, False), ({"category": "other"}, False),
    ({"priority": "P1"}, True), ({"category": "security"}, True), ({"confidence": "low"}, True),
])
def test_wide_routing_keeps_only_p1_security_and_low_confidence_on_opus(overrides, strong):
    assert needs_strong_model_wide(triage(**overrides)) is strong
