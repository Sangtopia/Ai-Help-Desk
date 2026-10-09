---
id: KB-031
title: Sign-in at an unusual time or location
category: security
tools: lookup_user, check_signin_logs, check_mfa_status, block_sign_in, escalate_to_tier2
---

## Symptoms
- Sign-in or VPN connection outside the user's usual work hours, for example 4 AM when they normally start at 9 AM.
- Sign-in from a new country or city.
- User reports Duo pushes they did not request.

## Quick checks
1. Run `lookup_user` for the user's home time zone and usual hours.
2. Run `check_signin_logs`. Each sign-in shows `home_time` and `location_time`. Compare both:
   - Odd at home but normal where the user is (9 AM local in another country) suggests travel. Look for a steady pattern from the same place, a residential network, and Duo approved on the first push.
   - Odd in both time zones is more suspicious.
3. Look for red flags of compromise:
   - Sign-ins from a hosting or data center network.
   - Several `mfa_denied` results followed by a success (push fatigue: the attacker keeps sending pushes until one is approved).
   - Impossible travel: a sign-in from the home city and another from a far country only a few hours apart.
   - Failed password attempts on a disabled account.
4. Remember early shifts. A warehouse user who starts at 6 AM is not suspicious at 6 AM.

## Fix
1. Confirm with the user that it was them. Contact them through a known channel (the phone number on file or a manager), not by replying to the ticket or calling a number given in the ticket.
2. Travel confirmed: note it on the ticket and close. No block needed.
3. User did not sign in, or there are red flags of compromise: request `block_sign_in` first, then `reset_password` for the same account. Both wait for technician approval. The block cuts off the attacker and removes VPN access; the reset makes the stolen password useless.
4. The technician gives the user the temporary password by phone, after verifying them by callback to the number on file. Never by email or ticket reply: the attacker may be reading the mailbox.
5. Then check the user's Duo device (KB-004) in case the attacker enrolled their own.

## Escalate when
- Any red flag above is present: escalate to Tier 2 / security with the sign-in times, locations, networks, and MFA results, and whether the account was blocked.
- The user is a VIP or executive.
