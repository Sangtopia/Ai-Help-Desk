"""API tests. Tickets are created with the scripted model, so no Claude calls are made."""

import json

import pytest
from fastapi.testclient import TestClient

from helpdesk import agent, api, demo, tools
from helpdesk.db import session
from helpdesk.models import Ticket
from helpdesk.seed import build_database
from tests.test_agent import ScriptedClient, make_resolution, make_triage, tool_call

TOM = "tom.becker@brightline.example"


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    path = tmp_path / "helpdesk.db"
    monkeypatch.setenv("HELPDESK_DB", str(path))
    build_database(path)
    monkeypatch.setattr(agent, "search_kb", lambda query: {"ok": True, "results": []})


@pytest.fixture
def client():
    with TestClient(api.app) as test_client:
        yield test_client


def locked_out_ticket() -> int:
    ticket = Ticket(id="T-1001", sender=TOM, subject="locked out", body="My account is locked")
    scripted = ScriptedClient(make_triage(), [[tool_call("unlock_account", user_id=4)], make_resolution()])
    return agent.handle_ticket(ticket, scripted).approval_ids[0]


def test_index_and_assets_are_served(client):
    assert "Brightline Help Desk" in client.get("/").text
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/static/app.css").status_code == 200


SAM = "Sam Ortiz"  # Tier 1


def test_ticket_list_and_detail(client):
    locked_out_ticket()
    tickets = client.get("/api/tickets", params={"technician": SAM}).json()
    assert [(t["id"], t["name"], t["pending"], t["assignee"]) for t in tickets] == [("T-1001", "Tom Becker", 1, SAM)]

    detail = client.get("/api/tickets/T-1001", params={"technician": SAM}).json()
    assert detail["ticket"]["triage"]["priority"] == "P2"
    assert detail["customer"]["user"]["name"] == "Tom Becker"
    assert detail["approvals"][0]["tool"] == "unlock_account"
    assert any(e["action"] == "unlock_account" and e["outcome"] == "pending_approval" for e in detail["audit"])


def test_unknown_ticket_is_404(client):
    assert client.get("/api/tickets/T-9999", params={"technician": SAM}).status_code == 404


def test_listing_requires_a_known_technician(client):
    assert client.get("/api/tickets", params={"technician": "mallory"}).status_code == 400


def test_approve_through_api(client):
    approval_id = locked_out_ticket()
    response = client.post(f"/api/approvals/{approval_id}", json={"approve": True, "technician": SAM})
    assert response.status_code == 200
    assert tools.lookup_user(TOM)["account"]["status"] == "active"
    ticket = client.get("/api/tickets", params={"technician": SAM}).json()[0]
    assert (ticket["status"], ticket["resolved_by"]) == ("resolved", SAM)
    # Deciding twice is a conflict, not a second execution.
    assert client.post(f"/api/approvals/{approval_id}", json={"approve": True, "technician": SAM}).status_code == 409


def test_approval_needs_a_known_technician(client):
    approval_id = locked_out_ticket()
    assert client.post(f"/api/approvals/{approval_id}", json={"approve": True, "technician": ""}).status_code == 400


def test_create_ticket_rejects_unknown_sender(client):
    response = client.post("/api/tickets", json={"sender": "stranger@evil.example", "subject": "hi", "body": "reset"})
    assert response.status_code == 400


def test_create_ticket_runs_the_agent(client, monkeypatch):
    scripted = ScriptedClient(make_triage(category="printing", priority="P4", user_blocked=False),
                              [make_resolution(outcome="resolved")])
    monkeypatch.setattr(agent, "get_client", lambda: scripted)
    monkeypatch.setattr("helpdesk.triage.get_client", lambda: scripted)
    response = client.post("/api/tickets", json={"sender": TOM, "subject": "printer", "body": "How do I add one?"})
    assert response.status_code == 200
    assert response.json()["ticket_id"] == "T-1001"
    assert response.json()["status"] == "resolved"


def test_rules_count_guardrail_activity(client):
    locked_out_ticket()
    stats = client.get("/api/rules").json()
    assert stats["approval_gate"] == 1
    assert stats["audit_log"] > 0


def test_reset_clears_tickets(client, monkeypatch, tmp_path):
    monkeypatch.setattr(demo, "SNAPSHOT", tmp_path / "missing.json")
    locked_out_ticket()
    client.post("/api/reset")
    assert client.get("/api/tickets", params={"technician": SAM}).json() == []


def test_reset_restores_the_demo_snapshot(client, monkeypatch, tmp_path):
    """Export a snapshot from a scripted run, then check reset replays it with recent timestamps."""
    locked_out_ticket()
    with session() as conn:
        data = {table: [dict(r) for r in conn.execute(f"SELECT * FROM {table}")] for table in demo.TABLES}
    snapshot = tmp_path / "snapshot.json"
    snapshot.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(demo, "SNAPSHOT", snapshot)

    client.post("/api/reset")
    tickets = client.get("/api/tickets", params={"technician": SAM}).json()
    assert [(t["id"], t["pending"], t["assignee"]) for t in tickets] == [("T-1001", 1, SAM)]
    assert tools.lookup_user(TOM)["account"]["status"] == "locked"  # environment is freshly seeded
    assert client.get("/api/tickets/T-1001", params={"technician": SAM}).json()["approvals"][0]["status"] == "pending"


def test_ticket_limits(monkeypatch):
    limiter = api.TicketLimiter(per_day=3, per_visitor_per_hour=2)
    assert limiter.allow("a") is None and limiter.allow("a") is None
    assert "hourly" in limiter.allow("a")
    assert limiter.allow("b") is None
    assert "today" in limiter.allow("c")


def test_create_ticket_returns_429_over_the_limit(client, monkeypatch):
    limiter = api.TicketLimiter(per_day=1, per_visitor_per_hour=0)
    limiter.allow("someone else")  # uses up today's only ticket
    monkeypatch.setattr(api, "limiter", limiter)
    response = client.post("/api/tickets", json={"sender": TOM, "subject": "printer", "body": "help"})
    assert response.status_code == 429
    assert "limit" in response.json()["detail"]


def test_health(client):
    assert client.get("/api/health").json() == {"ok": True}
