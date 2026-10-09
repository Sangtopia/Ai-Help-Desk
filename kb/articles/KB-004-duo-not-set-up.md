---
id: KB-004
title: Duo MFA not set up on a company laptop or new phone
category: account_access
tools: lookup_user, check_mfa_status, check_device_status
---

## Symptoms
- User is never asked for a Duo push, or is told "Your account is not enrolled".
- New hire's laptop was issued without Duo.
- User got a new phone and Duo pushes no longer arrive.

## Quick checks
1. Run `check_mfa_status`.
   - `enrolled: false`: Duo was never set up for this user.
   - `enrolled: true` but pushes do not arrive: usually a new or reset phone.
2. Run `check_device_status` on their laptop to confirm it is online and checking in.

## Fix
Not enrolled (common on laptops issued without Duo):
1. Schedule a short remote or in-person session. Duo enrollment needs the user present with their phone.
2. Install Duo Mobile on the user's phone from the app store.
3. Install the Duo client on the laptop if it is missing, then start enrollment and have the user scan the activation QR code.
4. Send a test push and confirm the user can approve it.

New phone:
1. Verify identity by callback to the number on file.
2. Re-activate Duo Mobile on the new device and send a test push.

Until enrollment is done, the user may be unable to use VPN. Note this in the ticket.

## Escalate when
- The user cannot be verified for a phone change.
- Duo shows pushes the user did not request (follow KB-031).
