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
| `escalate_to_tier2(ticket_id, summary)` | Hands the ticket to Tier 2 with a summary |

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m helpdesk.seed   # builds data/helpdesk.db
pytest
```
