"""Tools the help desk agent can call against the mock IT environment.

Every tool returns a JSON-serializable dict with an "ok" key, so the agent
reads failures the same way it reads successes instead of handling exceptions.
Approval gates, identity checks, and audit logging are layered on top of
these in agent.py and guardrails.py; the tools themselves only enforce rules a real
directory or mail system would (e.g. disabled accounts can't be reset).
"""

import secrets
import string
from collections import Counter
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from helpdesk.db import session

LOW_DISK_PERCENT = 10
STALE_CHECKIN = timedelta(days=7)
UNRELEASABLE_REASONS = {"phishing", "malware"}


def _now() -> datetime:
    return datetime.now(UTC)


def _error(message: str) -> dict:
    return {"ok": False, "error": message}


def _temp_password(length: int = 14) -> str:
    alphabet = string.ascii_letters + string.digits
    while True:
        password = "".join(secrets.choice(alphabet) for _ in range(length))
        if any(c.islower() for c in password) and any(c.isupper() for c in password) and any(
            c.isdigit() for c in password
        ):
            return password


def _hours_label(start: int, end: int) -> str:
    return f"{start:02d}:00-{end:02d}:00"


def lookup_user(email: str) -> dict:
    """Find a user by email, with account status, mailbox usage, and devices."""
    with session() as conn:
        user = conn.execute(
            "SELECT u.*, a.status, a.failed_login_count, a.password_last_set, a.must_change_password, "
            "a.sign_in_blocked, a.vpn_access "
            "FROM users u JOIN accounts a ON a.user_id = u.id WHERE u.email = ?",
            (email.strip(),),
        ).fetchone()
        if user is None:
            return _error(f"No user found with email {email}")
        mailbox = conn.execute("SELECT quota_mb, used_mb FROM mailboxes WHERE email = ?", (user["email"],)).fetchone()
        devices = [
            row["hostname"]
            for row in conn.execute("SELECT hostname FROM devices WHERE user_id = ? ORDER BY hostname", (user["id"],))
        ]

    return {
        "ok": True,
        "user": {
            "user_id": user["id"],
            "name": user["name"],
            "email": user["email"],
            "department": user["department"],
            "title": user["title"],
            "is_vip": bool(user["is_vip"]),
            "timezone": user["timezone"],
            "usual_hours": _hours_label(user["work_start"], user["work_end"]),
        },
        "account": {
            "status": user["status"],
            "failed_login_count": user["failed_login_count"],
            "password_last_set": user["password_last_set"],
            "must_change_password": bool(user["must_change_password"]),
            "sign_in_blocked": bool(user["sign_in_blocked"]),
            "vpn_access": bool(user["vpn_access"]),
        },
        "mailbox": {
            "quota_mb": mailbox["quota_mb"],
            "used_mb": mailbox["used_mb"],
            "percent_used": round(100 * mailbox["used_mb"] / mailbox["quota_mb"], 1),
        },
        "devices": devices,
    }


def reset_password(user_id: int) -> dict:
    """Set a temporary password that must be changed at next sign-in."""
    with session() as conn:
        account = conn.execute("SELECT status FROM accounts WHERE user_id = ?", (user_id,)).fetchone()
        if account is None:
            return _error(f"No account for user_id {user_id}")
        if account["status"] == "disabled":
            return _error("Account is disabled; re-enabling requires Tier 2 and HR approval")
        temp_password = _temp_password()
        conn.execute(
            "UPDATE accounts SET password_last_set = ?, must_change_password = 1 WHERE user_id = ?",
            (_now().isoformat(timespec="seconds"), user_id),
        )

    result = {
        "ok": True,
        "user_id": user_id,
        "temporary_password": temp_password,
        "must_change_password": True,
        "account_status": account["status"],
    }
    if account["status"] == "locked":
        result["note"] = "Account is still locked; run unlock_account before the user can sign in"
    return result


def unlock_account(user_id: int) -> dict:
    """Clear a lockout caused by failed sign-in attempts."""
    with session() as conn:
        account = conn.execute("SELECT status FROM accounts WHERE user_id = ?", (user_id,)).fetchone()
        if account is None:
            return _error(f"No account for user_id {user_id}")
        if account["status"] == "disabled":
            return _error("Account is disabled, not locked; re-enabling requires Tier 2 and HR approval")
        if account["status"] == "active":
            return {"ok": True, "user_id": user_id, "account_status": "active", "note": "Account was not locked"}
        conn.execute("UPDATE accounts SET status = 'active', failed_login_count = 0 WHERE user_id = ?", (user_id,))

    return {"ok": True, "user_id": user_id, "account_status": "active"}


def check_spam_quarantine(email: str) -> dict:
    """List messages currently held in quarantine for a mailbox."""
    with session() as conn:
        mailbox = conn.execute("SELECT email FROM mailboxes WHERE email = ?", (email.strip(),)).fetchone()
        if mailbox is None:
            return _error(f"No mailbox found for {email}")
        rows = conn.execute(
            "SELECT message_id, sender, subject, received_at, reason FROM quarantine "
            "WHERE recipient = ? AND status = 'quarantined' ORDER BY received_at DESC",
            (mailbox["email"],),
        ).fetchall()

    return {
        "ok": True,
        "email": mailbox["email"],
        "messages": [{**dict(row), "releasable": row["reason"] not in UNRELEASABLE_REASONS} for row in rows],
    }


def release_email(message_id: str) -> dict:
    """Deliver a quarantined message to the recipient's inbox."""
    with session() as conn:
        message = conn.execute(
            "SELECT recipient, subject, reason, status FROM quarantine WHERE message_id = ?", (message_id.strip(),)
        ).fetchone()
        if message is None:
            return _error(f"No quarantined message with id {message_id}")
        if message["status"] == "released":
            return _error(f"Message {message_id} was already released")
        if message["reason"] in UNRELEASABLE_REASONS:
            return _error(f"Message {message_id} was flagged as {message['reason']}; only the security team can release it")
        conn.execute("UPDATE quarantine SET status = 'released' WHERE message_id = ?", (message_id.strip(),))

    return {"ok": True, "message_id": message_id, "recipient": message["recipient"], "subject": message["subject"]}


def check_device_status(hostname: str) -> dict:
    """Report online state, last check-in, disk space, and any warnings for a device."""
    with session() as conn:
        device = conn.execute(
            "SELECT d.*, u.email AS assigned_to FROM devices d LEFT JOIN users u ON u.id = d.user_id "
            "WHERE d.hostname = ?",
            (hostname.strip(),),
        ).fetchone()
    if device is None:
        return _error(f"No device found with hostname {hostname}")

    last_checkin = datetime.fromisoformat(device["last_checkin"])
    warnings = []
    if _now() - last_checkin > STALE_CHECKIN:
        warnings.append(f"No check-in for {(_now() - last_checkin).days} days")
    result = {
        "ok": True,
        "hostname": device["hostname"],
        "kind": device["kind"],
        "os": device["os"],
        "assigned_to": device["assigned_to"],
        "online": bool(device["online"]),
        "last_checkin": device["last_checkin"],
    }
    if device["disk_total_gb"] is not None:
        percent_free = round(100 * device["disk_free_gb"] / device["disk_total_gb"], 1)
        result["disk"] = {
            "total_gb": device["disk_total_gb"],
            "free_gb": device["disk_free_gb"],
            "percent_free": percent_free,
        }
        if percent_free < LOW_DISK_PERCENT:
            warnings.append(f"Low disk space: {percent_free}% free")
    result["warnings"] = warnings
    return result


def check_signin_logs(user_id: int, days: int = 14) -> dict:
    """Recent sign-ins, with each one shown in the user's home time and the local time where it happened.

    The tool reports facts and simple flags; deciding whether a pattern means travel or
    compromise is left to the agent (and to a human for anything risky).
    """
    since = (_now() - timedelta(days=days)).isoformat(timespec="seconds")
    with session() as conn:
        user = conn.execute("SELECT timezone, work_start, work_end FROM users WHERE id = ?", (user_id,)).fetchone()
        if user is None:
            return _error(f"No user with user_id {user_id}")
        rows = conn.execute(
            "SELECT * FROM signins WHERE user_id = ? AND occurred_at >= ? ORDER BY occurred_at DESC",
            (user_id, since),
        ).fetchall()

    home_tz = ZoneInfo(user["timezone"])

    def in_hours(dt: datetime) -> bool:
        return user["work_start"] <= dt.hour < user["work_end"]

    signins = []
    for row in rows:
        at = datetime.fromisoformat(row["occurred_at"])
        home_time = at.astimezone(home_tz)
        location_time = at.astimezone(ZoneInfo(row["timezone"]))
        signins.append({
            "occurred_at": row["occurred_at"],
            "home_time": home_time.strftime("%a %H:%M"),
            "location_time": location_time.strftime("%a %H:%M"),
            "location": f"{row['city']}, {row['country']}",
            "app": row["app"],
            "ip": row["ip"],
            "network": row["network"],
            "result": row["result"],
            "mfa": row["mfa"],
            "outside_usual_hours_home": not in_hours(home_time),
            "outside_usual_hours_location": not in_hours(location_time),
        })

    results = Counter(s["result"] for s in signins)
    return {
        "ok": True,
        "user_id": user_id,
        "home_timezone": user["timezone"],
        "usual_hours": _hours_label(user["work_start"], user["work_end"]),
        "summary": {
            "total": len(signins),
            "failed_password": results["failed_password"],
            "mfa_denied": results["mfa_denied"],
            "locations": sorted({s["location"] for s in signins}),
            "hosting_network_signins": sum(s["network"] == "hosting" for s in signins),
        },
        "signins": signins,
    }


def check_mfa_status(user_id: int) -> dict:
    """Whether the user is enrolled in Duo MFA, and on which device."""
    with session() as conn:
        mfa = conn.execute("SELECT * FROM mfa WHERE user_id = ?", (user_id,)).fetchone()
    if mfa is None:
        return _error(f"No user with user_id {user_id}")
    return {
        "ok": True,
        "user_id": user_id,
        "enrolled": bool(mfa["enrolled"]),
        "method": mfa["method"],
        "device": mfa["device"],
        "enrolled_at": mfa["enrolled_at"],
    }


def block_sign_in(user_id: int, reason: str) -> dict:
    """Block all sign-ins and VPN access for a possibly compromised account."""
    if not reason.strip():
        return _error("A reason is required to block sign-in")
    with session() as conn:
        account = conn.execute(
            "SELECT status, sign_in_blocked FROM accounts WHERE user_id = ?", (user_id,)
        ).fetchone()
        if account is None:
            return _error(f"No account for user_id {user_id}")
        if account["status"] == "disabled":
            return _error("Account is already disabled")
        if account["sign_in_blocked"]:
            return {"ok": True, "user_id": user_id, "note": "Sign-in was already blocked"}
        conn.execute("UPDATE accounts SET sign_in_blocked = 1, vpn_access = 0 WHERE user_id = ?", (user_id,))

    return {
        "ok": True,
        "user_id": user_id,
        "sign_in_blocked": True,
        "vpn_access": False,
        "reason": reason.strip(),
        "note": "Unblocking requires Tier 2 after the user's identity is confirmed through a known contact method",
    }


def escalate_to_tier2(ticket_id: str, summary: str) -> dict:
    """Hand a ticket to Tier 2 with a written summary of what was found and tried."""
    if not summary.strip():
        return _error("Escalation summary cannot be empty")
    created_at = _now().isoformat(timespec="seconds")
    with session() as conn:
        cursor = conn.execute(
            "INSERT INTO escalations (ticket_id, summary, created_at) VALUES (?, ?, ?)",
            (ticket_id, summary.strip(), created_at),
        )
    return {"ok": True, "escalation_id": cursor.lastrowid, "ticket_id": ticket_id, "created_at": created_at}
