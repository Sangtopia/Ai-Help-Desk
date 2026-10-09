"""API tests. Tickets are created with the scripted model, so no Claude calls are made."""

import pytest
from fastapi.testclient import TestClient

from helpdesk import agent, api, tools
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


def test_ticket_list_and_detail(client):
    locked_out_ticket()
    tickets = client.get("/api/tickets").json()
    assert [(t["id"], t["name"], t["pending"]) for t in tickets] == [("T-1001", "Tom Becker", 1)]

    detail = client.get("/api/tickets/T-1001").json()
    assert detail["ticket"]["triage"]["priority"] == "P2"
    assert detail["customer"]["user"]["name"] == "Tom Becker"
    assert detail["approvals"][0]["tool"] == "unlock_account"
    assert any(e["action"] == "unlock_account" and e["outcome"] == "pending_approval" for e in detail["audit"])


def test_unknown_ticket_is_404(client):
    assert client.get("/api/tickets/T-9999").status_code == 404


def test_approve_through_api(client):
    approval_id = locked_out_ticket()
    response = client.post(f"/api/approvals/{approval_id}", json={"approve": True, "technician": "priya"})
    assert response.status_code == 200
    assert tools.lookup_user(TOM)["account"]["status"] == "active"
    assert client.get("/api/tickets").json()[0]["status"] == "resolved"
    # Deciding twice is a conflict, not a second execution.
    assert client.post(f"/api/approvals/{approval_id}", json={"approve": True, "technician": "priya"}).status_code == 409


def test_approval_needs_a_technician_name(client):
    approval_id = locked_out_ticket()
    assert client.post(f"/api/approvals/{approval_id}", json={"approve": True, "technician": ""}).status_code == 422


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


def test_reset_clears_tickets(client):
    locked_out_ticket()
    client.post("/api/reset")
    assert client.get("/api/tickets").json() == []
