"""HTTP API and web interface for the help desk.

Run with:  uvicorn helpdesk.api:app --reload
Then open http://localhost:8000
"""

import os
import threading
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

import anthropic
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from helpdesk import demo, queue, tools
from helpdesk.agent import assign_ticket, decide_approval, escalate_ticket, handle_ticket, resolve_ticket
from helpdesk.db import db_path, migrate
from helpdesk.routing import can_access, route_unassigned
from helpdesk.guardrails import get_audit_log
from helpdesk.kb import build_index, index_dir
from helpdesk.models import Ticket, TicketResult
from helpdesk.seed import build_database

WEB_DIR = Path(__file__).resolve().parent.parent / "web"


class TicketLimiter:
    """Caps on new tickets for a public demo, since each one spends Anthropic credits. A cap of 0 is off."""

    def __init__(self, per_day: int, per_visitor_per_hour: int):
        self.per_day, self.per_visitor_per_hour = per_day, per_visitor_per_hour
        self._lock = threading.Lock()
        self._day, self._today = None, 0
        self._recent: dict[str, deque] = defaultdict(deque)

    def allow(self, visitor: str) -> str | None:
        """Count a new ticket, or return why it isn't allowed."""
        now, day = time.monotonic(), datetime.now(UTC).date()
        with self._lock:
            if day != self._day:
                self._day, self._today = day, 0
            if self.per_day and self._today >= self.per_day:
                return "The demo has reached today's ticket limit. Please try again tomorrow, or browse the example tickets."
            recent = self._recent[visitor]
            while recent and now - recent[0] > 3600:
                recent.popleft()
            if self.per_visitor_per_hour and len(recent) >= self.per_visitor_per_hour:
                return "You've reached this demo's hourly ticket limit. Please try again a bit later."
            self._today += 1
            recent.append(now)
        return None


limiter = TicketLimiter(int(os.environ.get("MAX_TICKETS_PER_DAY", "0")),
                        int(os.environ.get("MAX_TICKETS_PER_VISITOR_PER_HOUR", "0")))


def fresh_demo_data() -> None:
    """A clean fake company plus the pre-worked demo tickets."""
    build_database()
    demo.load()


@asynccontextmanager
async def lifespan(_: FastAPI):
    if not db_path().exists():
        fresh_demo_data()
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
def create_ticket(new: NewTicket, request: Request) -> TicketResult:
    """Runs triage and the agent synchronously; takes roughly 20-60 seconds."""
    if new.sender not in {u["email"] for u in queue.list_users()}:
        raise HTTPException(400, f"Unknown sender {new.sender}")
    # Behind a hosting proxy the visitor's address is the first X-Forwarded-For entry.
    visitor = request.headers.get("x-forwarded-for", "").split(",")[0].strip() or request.client.host
    if refused := limiter.allow(visitor):
        raise HTTPException(429, refused)
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
    fresh_demo_data()
    return {"ok": True}


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")
