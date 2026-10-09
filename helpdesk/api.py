"""HTTP API and web interface for the help desk.

Run with:  uvicorn helpdesk.api:app --reload
Then open http://localhost:8000
"""

from contextlib import asynccontextmanager
from pathlib import Path

import anthropic
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from helpdesk import queue, tools
from helpdesk.agent import assign_ticket, decide_approval, escalate_ticket, handle_ticket, resolve_ticket
from helpdesk.db import db_path, migrate
from helpdesk.routing import can_access, route_unassigned
from helpdesk.guardrails import get_audit_log
from helpdesk.kb import build_index, index_dir
from helpdesk.models import Ticket, TicketResult
from helpdesk.seed import build_database

WEB_DIR = Path(__file__).resolve().parent.parent / "web"


@asynccontextmanager
async def lifespan(_: FastAPI):
    if not db_path().exists():
        build_database()
    migrate()
    route_unassigned()
    if not (index_dir() / "chroma.sqlite3").exists():
        build_index()
    yield


app = FastAPI(title="Brightline IT Help Desk", lifespan=lifespan)


class NewTicket(BaseModel):
    sender: str
    subject: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=5000)


class Decision(BaseModel):
    approve: bool
    technician: str


class Assignment(BaseModel):
    assignee: str | None  # a technician's name, or None to unassign
    technician: str  # who is making the change


class TechnicianAction(BaseModel):
    technician: str  # who is acting


def require_technician(name: str) -> None:
    if not queue.is_technician(name):
        raise HTTPException(400, f"Unknown technician {name!r}")


def check(result: dict) -> dict:
    if not result["ok"]:
        raise HTTPException(409, result["error"])
    return result


@app.get("/api/users")
def users() -> list[dict]:
    return queue.list_users()


@app.get("/api/technicians")
def technicians() -> list[dict]:
    return queue.TECHNICIANS


@app.get("/api/tickets")
def tickets(technician: str) -> list[dict]:
    """The tickets this technician may see: their tier and every tier below it."""
    require_technician(technician)
    return queue.list_tickets(max_tier=queue.technician_level(technician))


@app.get("/api/tickets/{ticket_id}")
def ticket_detail(ticket_id: str, technician: str) -> dict:
    require_technician(technician)
    ticket = queue.get_ticket(ticket_id)
    if ticket is None:
        raise HTTPException(404, f"No ticket {ticket_id}")
    if not can_access(technician, ticket["tier"]):
        raise HTTPException(403, f"{ticket_id} is a {queue.TIER_NAMES[ticket['tier']]} ticket")
    customer = tools.lookup_user(ticket["sender"])
    return {
        "ticket": ticket,
        "approvals": queue.get_approvals(ticket_id),
        "audit": get_audit_log(ticket_id),
        "customer": customer if customer["ok"] else None,
    }


@app.post("/api/tickets")
def create_ticket(new: NewTicket) -> TicketResult:
    """Runs triage and the agent synchronously; takes roughly 20-60 seconds."""
    if new.sender not in {u["email"] for u in queue.list_users()}:
        raise HTTPException(400, f"Unknown sender {new.sender}")
    ticket = Ticket(id=queue.next_ticket_id(), sender=new.sender, subject=new.subject.strip(), body=new.body.strip())
    try:
        return handle_ticket(ticket)
    except anthropic.APIError as error:
        raise HTTPException(502, f"Claude API error: {error}") from error


@app.post("/api/approvals/{approval_id}")
def decide(approval_id: int, decision: Decision) -> dict:
    require_technician(decision.technician)
    return check(decide_approval(approval_id, decision.technician, decision.approve))


@app.post("/api/tickets/{ticket_id}/assign")
def assign(ticket_id: str, assignment: Assignment) -> dict:
    require_technician(assignment.technician)
    if assignment.assignee is not None:
        require_technician(assignment.assignee)
    return check(assign_ticket(ticket_id, assignment.assignee, assignment.technician))


@app.post("/api/tickets/{ticket_id}/escalate")
def escalate(ticket_id: str, body: TechnicianAction) -> dict:
    require_technician(body.technician)
    return check(escalate_ticket(ticket_id, body.technician))


@app.post("/api/tickets/{ticket_id}/resolve")
def resolve(ticket_id: str, body: TechnicianAction) -> dict:
    require_technician(body.technician)
    return check(resolve_ticket(ticket_id, body.technician))


@app.get("/api/rules")
def rules() -> dict:
    return queue.rule_stats()


@app.post("/api/reset")
def reset() -> dict:
    build_database()
    return {"ok": True}


app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")
