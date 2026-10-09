---
id: KB-012
title: Calendar invites not received or not updating
category: email
tools: check_spam_quarantine
---

## Symptoms
- User did not receive a meeting invite others got.
- Meeting time changes do not show on the user's calendar.
- Accepted meetings do not appear.

## Quick checks
1. Run `check_spam_quarantine`. External invites are sometimes quarantined as spam.
2. Check whether a delegate (such as an assistant) manages the calendar. Invites may be going to the delegate only.
3. Compare Outlook on the web with the desktop app.

## Fix
1. Release the invite if it is quarantined (KB-007).
2. If a delegate is set to receive invites, adjust delegate settings so the user also receives copies.
3. If only the desktop app is wrong, follow the Outlook sync steps (KB-009).
4. Ask the organizer to resend the invite.

## Escalate when
- Invites from one specific internal user never arrive (possible mail rule or transport issue).
