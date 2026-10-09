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
1. Tell the user not to click, reply, or forward the email to colleagues.
2. Have them use the Report Phishing button in Outlook, then delete the email.
3. Never run `release_email` on a message marked `phishing` or `malware`, even if the user asks. The tool refuses it; only the security team can release these.

## Escalate when
- Several users received the same message.
- The email appears to come from an internal account (that account may be compromised).
