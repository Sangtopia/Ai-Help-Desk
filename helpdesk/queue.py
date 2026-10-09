"""Read helpers for the technician queue and the user portal."""

import json

from helpdesk.db import session


def list_users() -> list[dict]:
    with session() as conn:
        rows = conn.execute("SELECT id, name, email, title FROM users ORDER BY name").fetchall()
    return [dict(row) for row in rows]


def next_ticket_id() -> str:
    with session() as conn:
        count = conn.execute("SELECT COUNT(*) FROM tickets").fetchone()[0]
    return f"T-{1001 + count}"


def _ticket(row) -> dict:
    ticket = dict(row)
    ticket["triage"] = json.loads(ticket["triage"]) if ticket["triage"] else None
    ticket["resolution"] = json.loads(ticket["resolution"]) if ticket["resolution"] else None
    return ticket


def list_tickets(sender: str | None = None) -> list[dict]:
    """Newest first, with the count of pending approvals on each."""
    query = ("SELECT t.*, (SELECT COUNT(*) FROM approvals a WHERE a.ticket_id = t.id AND a.status = 'pending') "
             "AS pending FROM tickets t")
    params: tuple = ()
    if sender:
        query += " WHERE t.sender = ?"
        params = (sender,)
    with session() as conn:
        rows = conn.execute(query + " ORDER BY t.created_at DESC, t.id DESC", params).fetchall()
    return [_ticket(row) for row in rows]


def get_approvals(ticket_id: str) -> list[dict]:
    with session() as conn:
        rows = conn.execute("SELECT * FROM approvals WHERE ticket_id = ? ORDER BY id", (ticket_id,)).fetchall()
    approvals = []
    for row in rows:
        approval = dict(row)
        approval["arguments"] = json.loads(approval["arguments"])
        approval["result"] = json.loads(approval["result"]) if approval["result"] else None
        approvals.append(approval)
    return approvals
