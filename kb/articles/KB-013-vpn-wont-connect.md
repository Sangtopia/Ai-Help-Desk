---
id: KB-013
title: VPN won't connect
category: network_vpn
tools: lookup_user, check_mfa_status, check_signin_logs, check_device_status
---

## Symptoms
- VPN client shows "Connection failed", "Login failed", or spins forever.
- User is asked for a Duo push that never arrives.

## Quick checks
1. Confirm the user has internet without VPN (open any public website). If not, see KB-014.
2. Run `lookup_user` and check:
   - account status is `active` (not `locked` or `disabled`),
   - `vpn_access` is true. If `sign_in_blocked` is true, the account was blocked for security reasons; do not try to work around it (see KB-031).
3. Run `check_mfa_status`. VPN requires Duo. If the user is not enrolled, follow KB-004.
4. Run `check_signin_logs` to see whether VPN attempts are reaching the server and what result they get (`failed_password`, `mfa_denied`).

## Fix
1. Wrong password or locked: follow KB-001 or KB-002.
2. Duo push not arriving: open Duo Mobile on the phone and pull down to refresh; check the phone's notifications are allowed for Duo.
3. Client errors with good credentials: quit and reopen the VPN client, then restart the laptop.
4. On hotel or public Wi-Fi, accept the Wi-Fi's sign-in page in a browser first, then connect VPN.

## Escalate when
- Account and Duo are fine, attempts reach the server, and it still fails.
- Many users cannot connect (possible VPN outage, P1 if it blocks a whole team).
