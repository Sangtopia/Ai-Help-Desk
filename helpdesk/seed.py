"""Build the mock IT environment for a fictional company, Brightline Logistics.

All people, emails, and devices are made up. The data is shaped to cover
common Tier 1 scenarios: locked accounts, false-positive spam, phishing,
low disk space, offline devices, and a disabled (former) employee.

Run with:  python -m helpdesk.seed
"""

from datetime import UTC, datetime, timedelta
from pathlib import Path

from helpdesk.db import SCHEMA, connect, db_path

DOMAIN = "brightline.example"

# (id, name, email local part, department, title, is_vip)
USERS = [
    (1, "Dana Whitfield", "dana.whitfield", "Executive", "Chief Executive Officer", 1),
    (2, "Marcus Reyes", "marcus.reyes", "Finance", "Chief Financial Officer", 1),
    (3, "Priya Nair", "priya.nair", "IT", "IT Manager", 0),
    (4, "Tom Becker", "tom.becker", "Finance", "Accountant", 0),
    (5, "Aisha Khan", "aisha.khan", "HR", "HR Generalist", 0),
    (6, "Leo Martins", "leo.martins", "Sales", "Account Executive", 0),
    (7, "Sofia Rossi", "sofia.rossi", "Marketing", "Marketing Coordinator", 0),
    (8, "James O'Connor", "james.oconnor", "Operations", "Warehouse Supervisor", 0),
    (9, "Mei Chen", "mei.chen", "Operations", "Logistics Analyst", 0),
    (10, "Ryan Brooks", "ryan.brooks", "Sales", "Account Executive (former)", 0),
    (11, "Grace Okafor", "grace.okafor", "Admin", "Receptionist", 0),
    (12, "Hannah Lee", "hannah.lee", "Finance", "Payroll Specialist", 0),
]

# user_id -> (status, failed_login_count, password age in days, must_change_password)
ACCOUNT_OVERRIDES = {
    4: ("locked", 5, 80, 0),
    10: ("disabled", 0, 200, 0),
    12: ("active", 0, 0, 1),
}

# user_id -> (quota_mb, used_mb); everyone else gets 50 GB with light usage
MAILBOX_OVERRIDES = {
    9: (51200, 50890),  # nearly full
}

# (message_id, recipient user_id, sender, subject, hours ago, reason)
QUARANTINE = [
    ("Q-1001", 5, "enrollment@healthplan-partner.example", "Open enrollment documents for 2027", 3, "spam"),
    ("Q-1002", 5, "deals@giftcard-rewards.example", "You have won a $500 gift card!!", 20, "spam"),
    ("Q-1003", 5, "it-support@brightIine-help.example", "Urgent: verify your payroll login", 6, "phishing"),
    ("Q-1004", 4, "billing@harborview-supplies.example", "Invoice #4471 - October pallets", 2, "spam"),
    ("Q-1005", 4, "scanner@docs-share.example", "Scanned document 0931.zip", 30, "malware"),
    ("Q-1006", 1, "news@freight-weekly.example", "This week in freight: rates climb again", 48, "bulk"),
    ("Q-1007", 6, "orders@lakeside-foods.example", "RE: Quote for 40 pallets", 1, "spam"),
]

# (hostname, user_id, kind, os, online, hours since check-in, disk total, disk free)
DEVICES = [
    ("BL-LT-0101", 1, "laptop", "Windows 11 Pro", 1, 0.1, 512, 310),
    ("BL-LT-0102", 2, "laptop", "Windows 11 Pro", 1, 0.2, 512, 220),
    ("BL-LT-0103", 3, "laptop", "Windows 11 Pro", 1, 0.1, 1024, 640),
    ("BL-LT-0104", 4, "laptop", "Windows 11 Pro", 1, 0.5, 256, 98),
    ("BL-LT-0105", 5, "laptop", "Windows 11 Pro", 1, 0.3, 256, 120),
    ("BL-LT-0106", 6, "laptop", "Windows 11 Pro", 1, 0.2, 256, 9),  # low disk
    ("BL-LT-0107", 7, "laptop", "Windows 11 Pro", 0, 24 * 12, 256, 140),  # stale
    ("BL-DT-0108", 8, "desktop", "Windows 11 Pro", 0, 2, 512, 400),  # recently offline
    ("BL-LT-0109", 9, "laptop", "macOS 15", 1, 0.4, 512, 75),
    ("BL-LT-0110", 10, "laptop", "Windows 11 Pro", 0, 24 * 40, 256, 160),
    ("BL-DT-0111", 11, "desktop", "Windows 11 Pro", 1, 0.1, 256, 180),
    ("BL-LT-0112", 12, "laptop", "Windows 11 Pro", 1, 0.2, 256, 130),
    ("BL-PR-FL1", None, "printer", "Printer firmware 4.2", 1, 0.1, None, None),
    ("BL-PR-FL2", None, "printer", "Printer firmware 4.2", 0, 5, None, None),
]


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def build_database(path: Path | None = None) -> Path:
    """Create a fresh database at `path`, replacing any existing one."""
    path = Path(path or db_path())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.unlink(missing_ok=True)
    now = datetime.now(UTC)

    conn = connect(path)
    try:
        conn.executescript(SCHEMA)
        for user_id, name, local, department, title, is_vip in USERS:
            email = f"{local}@{DOMAIN}"
            conn.execute(
                "INSERT INTO users VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, name, email, department, title, is_vip),
            )
            status, failed, age_days, must_change = ACCOUNT_OVERRIDES.get(user_id, ("active", 0, 30, 0))
            conn.execute(
                "INSERT INTO accounts VALUES (?, ?, ?, ?, ?)",
                (user_id, status, failed, _iso(now - timedelta(days=age_days)), must_change),
            )
            quota, used = MAILBOX_OVERRIDES.get(user_id, (51200, 8000 + user_id * 900))
            conn.execute("INSERT INTO mailboxes VALUES (?, ?, ?)", (email, quota, used))

        emails = {user_id: f"{local}@{DOMAIN}" for user_id, _, local, *_ in USERS}
        for message_id, user_id, sender, subject, hours_ago, reason in QUARANTINE:
            conn.execute(
                "INSERT INTO quarantine (message_id, recipient, sender, subject, received_at, reason) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (message_id, emails[user_id], sender, subject, _iso(now - timedelta(hours=hours_ago)), reason),
            )

        for hostname, user_id, kind, os_name, online, hours_ago, total, free in DEVICES:
            conn.execute(
                "INSERT INTO devices VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (hostname, user_id, kind, os_name, online, _iso(now - timedelta(hours=hours_ago)), total, free),
            )
        conn.commit()
    finally:
        conn.close()
    return path


if __name__ == "__main__":
    print(f"Built mock IT environment at {build_database()}")
