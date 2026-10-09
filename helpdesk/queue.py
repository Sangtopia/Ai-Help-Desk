"""Read helpers for the technician inbox and the user portal."""

import json

from helpdesk.db import session


def list_users() -> list[dict]:
    with session() as conn:
        rows = conn.execute("SELECT id, name, email, title, department FROM users ORDER BY name").fetchall()
    return [dict(row) for row in rows]


def next_ticket_id() -> str:
    with session() as conn:
        count = conn.execute("SELECT COUNT(*) FROM tickets").fetchone()[0]
    return f"T-{1001 + count}"


TICKET_QUERY = """
SELECT t.*, u.name,
       (SELECT COUNT(*) FROM approvals a WHERE a.ticket_id = t.id AND a.status = 'pending') AS pending,
       COALESCE((SELECT MAX(created_at) FROM audit_log l WHERE l.ticket_id = t.id), t.created_at) AS last_activity
FROM tickets t LEFT JOIN users u ON u.email = t.sender
"""


def _ticket(row) -> dict:
    ticket = dict(row)
    ticket["triage"] = json.loads(ticket["triage"]) if ticket["triage"] else None
    ticket["resolution"] = json.loads(ticket["resolution"]) if ticket["resolution"] else None
    return ticket


def list_tickets(sender: str | None = None) -> list[dict]:
    """Most recently active first, with the count of pending approvals on each."""
    query, params = TICKET_QUERY, ()
    if sender:
        query, params = query + " WHERE t.sender = ?", (sender,)
    with session() as conn:
        rows = conn.execute(query + " ORDER BY last_activity DESC, t.id DESC", params).fetchall()
    return [_ticket(row) for row in rows]


def get_ticket(ticket_id: str) -> dict | None:
    with session() as conn:
        row = conn.execute(TICKET_QUERY + " WHERE t.id = ?", (ticket_id,)).fetchone()
    return _ticket(row) if row else None


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


def rule_stats() -> dict:
    """How often each guardrail has fired, from the audit log."""
    queries = {
        "approval_gate": "SELECT COUNT(*) FROM audit_log WHERE outcome = 'pending_approval'",
        "identity_check": "SELECT COUNT(*) FROM audit_log WHERE actor = 'agent' AND outcome = 'blocked'",
        "injection_block": "SELECT COUNT(*) FROM audit_log WHERE action = 'block_ticket'",
        "escalation_rules": "SELECT COUNT(*) FROM audit_log WHERE actor = 'system' AND action = 'escalate_to_tier2' "
                            "AND reason LIKE 'Escalation rule%'",
        "audit_log": "SELECT COUNT(*) FROM audit_log",
    }
    with session() as conn:
        return {name: conn.execute(sql).fetchone()[0] for name, sql in queries.items()}
