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

## Triage

Every ticket first goes through one Claude call with structured output, validated by a Pydantic model: category, priority (P1–P4), whether the user is blocked from working, a one-line summary, a social-engineering flag, and a confidence level. The ticket is passed in as untrusted data, so instructions written inside it are classified, never followed. Priority is judged by impact, not tone: an angry ticket about a slow laptop stays P3.

## Agent and guardrails

After triage, the agent gets the ticket, the triage result, the top knowledge base articles and the tools, then loops: call a tool, read the result, decide the next step. It finishes with a validated `Resolution` (outcome, reply to the user, internal note for the technician, cited articles, confidence).

Every guardrail is enforced in code, so none of them depend on the model following instructions:

| Guardrail | How it works |
| --- | --- |
| Approval gate | Read-only tools run automatically. `reset_password`, `unlock_account`, `release_email` and `block_sign_in` are queued until a technician approves them, then run and are re-checked at that moment. |
| Identity check | Resets and unlocks only for the ticket sender's own account; email releases only from the sender's own mailbox. Violations are refused outright, never queued. |
| Audit log | Every tool call by the agent, the system or a technician is recorded with who, what, when, why (each tool call requires a `reason`) and the outcome. |
| Prompt-injection defense | Tickets are scanned for injection phrases and triage flags social engineering. Flagged tickets are blocked and sent to security before the agent or any tool sees them. |
| Escalation rules | P1 and low-confidence tickets are always escalated to Tier 2, even if the agent didn't escalate them itself. |

The tests include a scripted "hijacked" model that tries to reset the CEO's password from someone else's ticket, to show the code blocks it regardless of what the model does.

Run `python -m helpdesk.agent` to work four demo tickets end to end: a lockout, a quarantined email, a prompt-injection attempt and a push-fatigue account compromise.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m helpdesk.seed        # builds data/helpdesk.db
python -m helpdesk.kb build    # builds the search index in data/chroma
pytest
```

Copy `.env.example` to `.env` and add your Anthropic API key, then run `python -m helpdesk.triage` to triage five sample tickets.

Try a search: `python -m helpdesk.kb search "vpn won't connect"`
