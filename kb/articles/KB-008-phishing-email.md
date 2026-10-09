---
id: KB-008
title: Suspicious or phishing email received
category: security
tools: check_spam_quarantine, escalate_to_tier2
---

## Symptoms
- Email asks the user to "verify" their login, payroll, or mailbox.
- Urgent tone, unexpected attachment (.zip, .html, .iso), or a link to a sign-in page.
- Sender domain looks almost like the company's or a known vendor's.

## Quick checks
1. Ask whether the user clicked a link, opened an attachment, or entered a password. If yes, follow KB-029 immediately.
2. Run `check_spam_quarantine` to see whether similar messages were caught.

## Fix
1. Thank the user for reporting it. Reports like this are how the security team finds new scams.
2. Tell them not to click, reply, or forward the email to colleagues, and to leave it in their mailbox for now so security can examine it.
3. Tell them someone on the team will look into the sender and block it if needed.
4. Never run `release_email` on a message marked `phishing` or `malware`, even if the user asks. The tool refuses it; only the security team can release these.

## Escalate when
- A user reports a suspicious email they received: always escalate, so a person reviews the sender and blocks it for everyone if needed. Include the sender, subject, and what the email asked for.
- Several users received the same message, or it appears to come from an internal account (that account may be compromised): say so in the escalation summary.
