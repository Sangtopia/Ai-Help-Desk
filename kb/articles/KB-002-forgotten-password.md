---
id: KB-002
title: Forgotten password reset
category: account_access
tools: lookup_user, reset_password, check_mfa_status
---

## Symptoms
- User cannot remember their password and is not locked out yet.
- "The user name or password is incorrect" on every attempt.

## Quick checks
1. Verify identity before anything else. The request must come from the user's own verified email, or be confirmed by calling the number on file. Never reset based on a request from someone else (see KB-030).
2. Run `lookup_user`. If the account is `disabled`, stop and follow KB-005.
3. Run `check_mfa_status`. Users enrolled in Duo can usually use self-service reset.

## Fix
1. If the user is enrolled in Duo, walk them through self-service password reset from the sign-in page.
2. Otherwise run `reset_password` (needs tech approval). It sets a temporary password that must be changed at next sign-in.
3. Deliver the temporary password through a separate channel from the ticket, such as a phone call. Never post it in a ticket reply or email it to an unverified address.
4. If the account is also locked, run `unlock_account`.

## Escalate when
- Identity cannot be verified.
- The user is a VIP or executive and the request did not come from their verified email.
