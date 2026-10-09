---
id: KB-029
title: Clicked a phishing link or entered a password on a suspicious site
category: security
tools: lookup_user, check_signin_logs, block_sign_in, reset_password, escalate_to_tier2
---

## Symptoms
- User clicked a link in a suspicious email and typed their password or approved a Duo push.
- User opened an unexpected attachment.

## Quick checks
1. This is P1. Treat the password as stolen.
2. Run `check_signin_logs` for sign-ins after the time the user clicked, especially from hosting networks, other countries, or with Duo pushes the user did not request.

## Fix
1. Tell the user not to delete the email (security will want it) and to disconnect from Wi-Fi if they opened an attachment.
2. If the sign-in logs show suspicious activity, run `block_sign_in` (needs tech approval).
3. Reset the password with `reset_password` (needs tech approval) after verifying the user by callback.
4. Remind the user to never approve a Duo push they did not start.

## Escalate when
- Always. Escalate with the time of the click, what was entered, and any suspicious sign-ins found.
