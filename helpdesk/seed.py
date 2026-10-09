"""Build the mock IT environment for a fictional company, Brightline Logistics.

All people, emails, devices, and IP addresses are made up (IPs come from the
RFC 5737 documentation ranges). The data is shaped to cover common Tier 1
scenarios: locked accounts, false-positive spam, phishing, low disk space,
offline devices, a disabled (former) employee, users without Duo MFA, and
sign-in histories that separate a travelling employee from a compromised one.

Run with:  python -m helpdesk.seed
"""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from helpdesk.db import SCHEMA, connect, db_path

DOMAIN = "brightline.example"
NEW_YORK = "America/New_York"
CHICAGO = "America/Chicago"
HOME_CITIES = {NEW_YORK: ("New York", "US"), CHICAGO: ("Chicago", "US")}

# (id, name, email local part, department, title, is_vip, timezone, work_start, work_end)
USERS = [
    (1, "Dana Whitfield", "dana.whitfield", "Executive", "Chief Executive Officer", 1, NEW_YORK, 8, 18),
    (2, "Marcus Reyes", "marcus.reyes", "Finance", "Chief Financial Officer", 1, NEW_YORK, 9, 17),
    (3, "Priya Nair", "priya.nair", "IT", "IT Manager", 0, NEW_YORK, 8, 17),
    (4, "Tom Becker", "tom.becker", "Finance", "Accountant", 0, NEW_YORK, 9, 17),
    (5, "Aisha Khan", "aisha.khan", "HR", "HR Generalist", 0, NEW_YORK, 9, 17),
    (6, "Leo Martins", "leo.martins", "Sales", "Account Executive", 0, NEW_YORK, 9, 17),
    (7, "Sofia Rossi", "sofia.rossi", "Marketing", "Marketing Coordinator", 0, NEW_YORK, 9, 17),
    (8, "James O'Connor", "james.oconnor", "Operations", "Warehouse Supervisor", 0, CHICAGO, 6, 14),  # early shift
    (9, "Mei Chen", "mei.chen", "Operations", "Logistics Analyst", 0, CHICAGO, 8, 16),
    (10, "Ryan Brooks", "ryan.brooks", "Sales", "Account Executive (former)", 0, NEW_YORK, 9, 17),
    (11, "Grace Okafor", "grace.okafor", "Admin", "Receptionist", 0, NEW_YORK, 8, 16),
    (12, "Hannah Lee", "hannah.lee", "Finance", "Payroll Specialist", 0, NEW_YORK, 9, 17),
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

# Users whose company laptop never had Duo installed
MFA_NOT_ENROLLED = {11, 12}

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

CORPORATE_IP = "203.0.113.{}"
RESIDENTIAL_IP = "198.51.100.{}"


def _iso(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat(timespec="seconds")


def _most_recent_local(now: datetime, tz_name: str, hour: int, minute: int) -> datetime:
    """The latest moment before `now` when the clock in `tz_name` read hour:minute."""
    local_now = now.astimezone(ZoneInfo(tz_name))
    candidate = local_now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate > local_now:
        candidate -= timedelta(days=1)
    return candidate


def _normal_signins(user: tuple, now: datetime, days: range) -> list[tuple]:
    """One sign-in per weekday at the start of the user's shift, alternating office and home."""
    user_id, *_, tz_name, work_start, _ = user
    tz = ZoneInfo(tz_name)
    city, country = HOME_CITIES[tz_name]
    mfa = "none" if user_id in MFA_NOT_ENROLLED else "duo_push"
    today = now.astimezone(tz).date()
    rows = []
    for days_ago in days:
        day = today - timedelta(days=days_ago)
        if day.weekday() >= 5:
            continue
        at = datetime(day.year, day.month, day.day, work_start, (user_id * 7) % 40, tzinfo=tz)
        if (days_ago + user_id) % 2:
            app, ip, network = "m365", CORPORATE_IP.format(10), "corporate"
        else:
            app, ip, network = "vpn", RESIDENTIAL_IP.format(user_id + 20), "residential"
        rows.append((user_id, _iso(at), app, ip, network, city, country, tz_name, "success", mfa))
    return rows


def _signins(now: datetime) -> list[tuple]:
    rows = []
    for user in USERS:
        user_id = user[0]
        if user_id == 10:
            continue  # former employee: no legitimate activity
        # Leo has been travelling for the last three days, so his home history stops before that
        rows += _normal_signins(user, now, range(4 if user_id == 6 else 1, 15))

    # Leo Martins is on a work trip in Lisbon: odd hours for New York, normal hours where he is.
    lisbon = "Europe/Lisbon"
    for days_ago in range(0, 3):
        at = _most_recent_local(now, lisbon, 9, 5) - timedelta(days=days_ago)
        rows.append((6, _iso(at), "vpn", RESIDENTIAL_IP.format(66), "residential", "Lisbon", "PT", lisbon,
                     "success", "duo_push"))

    # Marcus Reyes is compromised: signed in from New York in the evening, then ~11 hours later
    # from a Singapore data center at 4 AM New York time, after denying three Duo pushes.
    attack = _most_recent_local(now, NEW_YORK, 4, 10)
    rows.append((2, _iso(attack - timedelta(hours=10, minutes=40)), "vpn", RESIDENTIAL_IP.format(22),
                 "residential", "New York", "US", NEW_YORK, "success", "duo_push"))
    for minutes, result in [(0, "mfa_denied"), (1, "mfa_denied"), (2, "mfa_denied"), (4, "success")]:
        rows.append((2, _iso(attack + timedelta(minutes=minutes)), "vpn", "192.0.2.77", "hosting",
                     "Singapore", "SG", "Asia/Singapore", result, "duo_push"))

    # Tom Becker locked himself out this morning.
    for minutes_ago in (40, 35, 31, 28, 25):
        rows.append((4, _iso(now - timedelta(minutes=minutes_ago)), "m365", CORPORATE_IP.format(10),
                     "corporate", "New York", "US", NEW_YORK, "failed_password", "none"))

    # Someone is trying the former employee's account overnight.
    probe = _most_recent_local(now, NEW_YORK, 3, 5)
    for minutes in (0, 2):
        rows.append((10, _iso(probe + timedelta(minutes=minutes)), "vpn", "192.0.2.140", "hosting",
                     "Amsterdam", "NL", "Europe/Amsterdam", "failed_password", "none"))
    return rows


def build_database(path: Path | None = None) -> Path:
    """Create a fresh database at `path`, replacing any existing one."""
    path = Path(path or db_path())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.unlink(missing_ok=True)
    now = datetime.now(UTC)

    conn = connect(path)
    try:
        conn.executescript(SCHEMA)
        for user_id, name, local, department, title, is_vip, tz_name, work_start, work_end in USERS:
            email = f"{local}@{DOMAIN}"
            conn.execute(
                "INSERT INTO users VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (user_id, name, email, department, title, is_vip, tz_name, work_start, work_end),
            )
            status, failed, age_days, must_change = ACCOUNT_OVERRIDES.get(user_id, ("active", 0, 30, 0))
            conn.execute(
                "INSERT INTO accounts (user_id, status, failed_login_count, password_last_set, must_change_password) "
                "VALUES (?, ?, ?, ?, ?)",
                (user_id, status, failed, _iso(now - timedelta(days=age_days)), must_change),
            )
            quota, used = MAILBOX_OVERRIDES.get(user_id, (51200, 8000 + user_id * 900))
            conn.execute("INSERT INTO mailboxes VALUES (?, ?, ?)", (email, quota, used))
            if user_id in MFA_NOT_ENROLLED:
                conn.execute("INSERT INTO mfa (user_id, enrolled) VALUES (?, 0)", (user_id,))
            else:
                conn.execute(
                    "INSERT INTO mfa VALUES (?, 1, 'duo_push', ?, ?)",
                    (user_id, f"Duo Mobile on {name.split()[0]}'s phone", _iso(now - timedelta(days=300))),
                )

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

        conn.executemany(
            "INSERT INTO signins (user_id, occurred_at, app, ip, network, city, country, timezone, result, mfa) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            _signins(now),
        )
        conn.commit()
    finally:
        conn.close()
    return path


if __name__ == "__main__":
    print(f"Built mock IT environment at {build_database()}")
