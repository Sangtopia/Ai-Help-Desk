# Ai-Help-Desk
AI IT help desk agent with triage, RAG, tool calling and human approval gates

## Mock IT environment

The agent works against a fake company, **Brightline Logistics**, stored in SQLite. All users, emails and devices are made up. It is designed to mirror real Tier 1 workflows without using any real client data.

| Tool | What it does |
| --- | --- |
| `lookup_user(email)` | Account status, failed logins, mailbox usage, assigned devices |
| `reset_password(user_id)` | Temporary password, must change at next sign-in |
| `unlock_account(user_id)` | Clears a failed-login lockout |
| `check_spam_quarantine(email)` | Lists held messages and whether each is releasable |
| `release_email(message_id)` | Delivers spam/bulk false positives; phishing and malware are blocked |
| `check_device_status(hostname)` | Online state, last check-in, disk space, warnings |
| `check_signin_logs(user_id)` | Recent sign-ins in both the user's home time and the local time where they happened |
| `check_mfa_status(user_id)` | Whether the user is enrolled in Duo, and on which device |
| `block_sign_in(user_id, reason)` | Blocks sign-in and VPN access for a possibly compromised account |
| `escalate_to_tier2(ticket_id, summary)` | Hands the ticket to Tier 2 with a summary |

The sign-in data separates a travelling employee (logging in at 9 AM in Lisbon, which is 4 AM in New York) from a compromised one (4 AM from a Singapore data center after three denied Duo pushes, hours after a New York sign-in). This mirrors how suspicious logins were checked on a real help desk: compare against the user's usual hours, account for travel, and confirm with the user before blocking.

## Knowledge base

31 short how-to articles in [kb/articles](kb/articles), written from Tier 1 help desk experience. Each one lists symptoms, quick checks, fix steps, the tools the agent may use, and when to escalate. Articles are split into chunks by section, embedded with Chroma's built-in local model, and searched with `search_kb(query)`, which returns whole articles so the agent can cite them by id.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m helpdesk.seed        # builds data/helpdesk.db
python -m helpdesk.kb build    # builds the search index in data/chroma
pytest
```

Try a search: `python -m helpdesk.kb search "vpn won't connect"`
