"""Click through the Streamlit app headlessly. Tickets are created with the scripted model, so no API calls."""

import pytest
from streamlit.testing.v1 import AppTest

from helpdesk import agent, tools
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


def open_app() -> AppTest:
    app = AppTest.from_file("../app.py", default_timeout=60)
    app.run()
    assert not app.exception
    return app


def test_submit_view_renders_with_examples():
    app = open_app()
    assert app.title[0].value == "Brightline IT Help Desk"
    app.selectbox[0].select("Locked out (Tom)").run()
    assert app.text_input[0].value == "locked out"
    assert not app.exception


def test_technician_can_approve_from_the_queue():
    ticket = Ticket(id="T-1001", sender=TOM, subject="locked out", body="My account is locked")
    client = ScriptedClient(make_triage(), [[tool_call("unlock_account", user_id=4)], make_resolution()])
    approval_id = agent.handle_ticket(ticket, client).approval_ids[0]

    app = open_app()
    app.sidebar.radio[0].set_value("Technician queue").run()
    assert not app.exception
    assert app.metric[0].value == "1"  # awaiting approval

    app.button(key=f"approve-{approval_id}").click().run()
    assert not app.exception
    assert tools.lookup_user(TOM)["account"]["status"] == "active"
    assert app.metric[3].value == "1"  # resolved
