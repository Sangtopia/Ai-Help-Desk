"""Tier routing: decide which level of the help desk a ticket needs, then auto-assign it there.

Like the other guardrails, this is plain code: the model never chooses who handles a ticket.

  Tier 1 (help desk):  routine fixes waiting for approval, tickets waiting on the user, rejected actions
  Tier 2 (engineers):  escalations, P1 outages, and requests to block an account's sign-in
  Tier 3 (security):   blocked prompt-injection / social-engineering tickets and P1 security incidents

A technician sees and acts on tickets at their own tier and every tier below it.
"""

import json

from helpdesk.db import session
from helpdesk.guardrails import audit
from helpdesk.queue import TECHNICIANS, TIER_NAMES, technician_level


def required_tier(status: str, triage: dict | None, pending_tools: set[str]) -> int:
    triage = triage or {}
    if status == "blocked" or (triage.get("category") == "security" and triage.get("priority") == "P1"):
        return 3
    if status == "escalated" or triage.get("priority") == "P1" or "block_sign_in" in pending_tools:
        return 2
    return 1


def pick_technician(tier: int) -> str:
    """The technician at exactly this tier with the fewest open tickets."""
    with session() as conn:
        rows = conn.execute("SELECT assignee, COUNT(*) AS n FROM tickets WHERE status != 'resolved' "
                            "AND assignee IS NOT NULL GROUP BY assignee").fetchall()
    load = {row["assignee"]: row["n"] for row in rows}
    candidates = [t["name"] for t in TECHNICIANS if t["level"] == tier]
    return min(candidates, key=lambda name: (load.get(name, 0), name))


def assign_to_tier(ticket_id: str, tier: int, actor: str = "system", why: str = "") -> str:
    name = pick_technician(tier)
    with session() as conn:
        conn.execute("UPDATE tickets SET tier = ?, assignee = ? WHERE id = ?", (tier, name, ticket_id))
    audit(ticket_id, actor, "auto_assign", "executed", {"tier": tier, "assignee": name},
          why or f"Routed to {TIER_NAMES[tier]}")
    return name


def route_ticket(ticket_id: str) -> str:
    """Work out the tier a ticket needs from its current state and assign it there."""
    with session() as conn:
        ticket = conn.execute("SELECT status, triage FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        pending = {row["tool"] for row in conn.execute(
            "SELECT tool FROM approvals WHERE ticket_id = ? AND status = 'pending'", (ticket_id,))}
    triage = json.loads(ticket["triage"]) if ticket["triage"] else None
    tier = required_tier(ticket["status"], triage, pending)
    reasons = {3: "security review", 2: "needs an engineer", 1: "routine help desk work"}
    return assign_to_tier(ticket_id, tier, why=f"Routed to {TIER_NAMES[tier]}: {reasons[tier]}")


def can_access(technician: str, ticket_tier: int) -> bool:
    level = technician_level(technician)
    return level is not None and level >= ticket_tier


def route_unassigned() -> None:
    """Bring tickets created before tier routing existed up to date: route open ones, and credit
    resolved ones to whoever approved their last action (or the AI agent if nobody did)."""
    names = {t["name"].lower().replace(" ", "."): t["name"] for t in TECHNICIANS}  # "priya.nair" -> "Priya Nair"
    with session() as conn:
        open_ids = [row["id"] for row in conn.execute(
            "SELECT id FROM tickets WHERE assignee IS NULL AND status != 'resolved'")]
        for row in conn.execute("SELECT id, created_at FROM tickets WHERE status = 'resolved' AND resolved_by IS NULL"):
            decided = conn.execute("SELECT decided_by, decided_at FROM approvals WHERE ticket_id = ? "
                                   "AND decided_by IS NOT NULL ORDER BY decided_at DESC", (row["id"],)).fetchone()
            who = names.get(decided["decided_by"], decided["decided_by"]) if decided else "AI agent"
            when = decided["decided_at"] if decided else row["created_at"]
            conn.execute("UPDATE tickets SET assignee = ?, resolved_by = ?, resolved_at = ? WHERE id = ?",
                         (who, who, when, row["id"]))
    for ticket_id in open_ids:
        route_ticket(ticket_id)
