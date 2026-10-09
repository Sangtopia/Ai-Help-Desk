---
id: KB-001
title: Account locked after failed sign-ins
category: account_access
tools: lookup_user, check_signin_logs, unlock_account, reset_password
---

## Symptoms
- User sees "Your account has been locked" or "too many sign-in attempts".
- Outlook, Teams, and VPN all stop accepting the password at the same time.
- Often happens right after a password change, when an old password is still saved on a phone or second device.

## Quick checks
1. Run `lookup_user` and confirm the account status is `locked` (not `disabled`).
2. Run `check_signin_logs` and look at the failed attempts:
   - From a corporate or the user's usual home network during work hours: almost always the user or a saved old password.
   - From a hosting network, another country, or overnight: treat as a possible attack and follow KB-031 instead of unlocking.
3. Confirm the request came from the user's own verified email or a callback to a known number.

## Fix
1. Run `unlock_account`.
2. If the user does not remember the password, run `reset_password` (needs tech approval) and have them change it at next sign-in.
3. Ask the user to update the saved password on their phone mail app and any other device, or the account will lock again.

## Escalate when
- Failed attempts come from unfamiliar locations or hosting networks.
- The account locks again within an hour of unlocking even after saved passwords are updated.
