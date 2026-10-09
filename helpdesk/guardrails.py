"""Guardrails enforced in code around every agent action.

The system prompt asks the agent to behave, but nothing here depends on it
listening: even a fully hijacked agent cannot run a risky tool without a
technician's approval, cannot touch an account other than the sender's, and
leaves an audit record for every attempt.
"""

import json
import re
from datetime import UTC, datetime

from helpdesk.db import session

# Read-only tools run automatically; anything that changes an account or mailbox waits for a technician.
AUTO = "auto"
NEEDS_APPROVAL = "needs_approval"
TOOL_POLICY = {
    "lookup_user": AUTO,
    "check_signin_logs": AUTO,
    "check_mfa_status": AUTO,
    "check_spam_quarantine": AUTO,
    "check_device_status": AUTO,
    "search_kb": AUTO,
    "escalate_to_tier2": AUTO,  # handing off is always safe
    "reset_password": NEEDS_APPROVAL,
    "unlock_account": NEEDS_APPROVAL,
    "release_email": NEEDS_APPROVAL,
    "block_sign_in": NEEDS_APPROVAL,
}

# Phrases aimed at the help desk system rather than at a human technician.
INJECTION_PATTERNS = [
    r"\b(ignore|disregard|forget|override)\b[^.\n]{0,40}\b(instructions?|rules|prompts?|polic(y|ies)|guardrails?)\b",
    r"\b(system|developer|admin)\s+(prompt|note|message|override|mode|instruction)",
    r"\b(note|message|instructions?)\s+(to|for)\s+(the\s+)?(ai|assistant|agent|bot|model)\b",
    r"\byou are now\b",
    r"\b(jailbreak|pretend (you are|to be))\b",
    r"\b(approve|auto-?approve) (this|the|all)\b[^.\n]{0,30}\b(reset|request|action)",
]


def scan_for_injection(text: str) -> list[str]:
    """Return the suspicious phrases found in ticket text (empty if none)."""
    return [m.group(0) for p in INJECTION_PATTERNS for m in re.finditer(p, text, flags=re.I)]


def _user_email(user_id: int) -> str | None:
    with session() as conn:
        row = conn.execute("SELECT email FROM users WHERE id = ?", (user_id,)).fetchone()
    return row["email"] if row else None


def _message_recipient(message_id: str) -> str | None:
    with session() as conn:
        row = conn.execute("SELECT recipient FROM quarantine WHERE message_id = ?", (message_id,)).fetchone()
    return row["recipient"] if row else None


def check_identity(sender: str, tool: str, args: dict) -> str | None:
    """Return why an action is blocked, or None if the sender may request it.

    The ticket's sender address is treated as verified (it came through the
    company mail system), so it is the only identity that counts, whatever the
    ticket text claims.
    """
    sender = sender.strip().lower()
    if tool in ("reset_password", "unlock_account"):
        target = _user_email(args["user_id"])
        if target is None:
            return f"No user with user_id {args['user_id']}"
        if target.lower() != sender:
            return f"Identity check failed: ticket came from {sender} but the action targets {target}"
    if tool == "release_email":
        recipient = _message_recipient(args["message_id"])
        if recipient is None:
            return f"No quarantined message with id {args['message_id']}"
        if recipient.lower() != sender:
            return f"Identity check failed: message {args['message_id']} belongs to {recipient}, not {sender}"
    return None


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def audit(ticket_id: str, actor: str, action: str, outcome: str, arguments: dict | None = None,
          reason: str | None = None, result: dict | None = None) -> None:
    """Record who did what, when, why, and what happened."""
    with session() as conn:
        conn.execute(
            "INSERT INTO audit_log (ticket_id, actor, action, arguments, reason, outcome, result, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (ticket_id, actor, action, json.dumps(arguments) if arguments is not None else None, reason, outcome,
             json.dumps(result) if result is not None else None, _now()),
        )


def get_audit_log(ticket_id: str) -> list[dict]:
    with session() as conn:
        rows = conn.execute("SELECT * FROM audit_log WHERE ticket_id = ? ORDER BY id", (ticket_id,)).fetchall()
    return [dict(row) for row in rows]


def queue_approval(ticket_id: str, tool: str, args: dict, reason: str) -> int:
    with session() as conn:
        cursor = conn.execute(
            "INSERT INTO approvals (ticket_id, tool, arguments, reason, created_at) VALUES (?, ?, ?, ?, ?)",
            (ticket_id, tool, json.dumps(args), reason, _now()),
        )
    return cursor.lastrowid
