---
id: KB-005
title: Former employee or disabled account access request
category: account_access
tools: lookup_user, check_signin_logs, escalate_to_tier2
---

## Symptoms
- Someone asks to reset, unlock, or re-enable an account that shows `disabled`.
- A manager asks for access to a former employee's mailbox or files.
- Failed sign-ins appear on an account that belongs to someone who left.

## Quick checks
1. Run `lookup_user`. A `disabled` account is intentional, usually from offboarding.
2. Run `check_signin_logs`. Sign-in attempts on a disabled account, especially from hosting networks or overnight, may be someone trying stolen credentials.

## Fix
Tier 1 does not reset, unlock, or re-enable disabled accounts.
1. Do not run `reset_password` or `unlock_account`. Both are refused for disabled accounts anyway.
2. For mailbox or file access requests, tell the requester it needs HR and manager approval, then escalate.
3. If there are recent sign-in attempts, include them in the escalation summary so security can review.

## Escalate when
- Always. Use `escalate_to_tier2` with who asked, what they want, and any sign-in attempts found.
