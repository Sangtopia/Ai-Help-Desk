---
id: KB-021
title: Lost or stolen laptop
category: devices_hardware
tools: lookup_user, check_device_status, block_sign_in, escalate_to_tier2
---

## Symptoms
- User reports their company laptop or phone lost or stolen.

## Quick checks
1. This is P1. Act right away.
2. Run `lookup_user` to find the user's devices, then `check_device_status` for the last check-in time.
3. Ask when and where it was last seen, and whether it was locked.

## Fix
1. If the device may be in someone else's hands and was not locked, run `block_sign_in` (needs tech approval) so the saved session cannot be used, then plan a password reset once the user is verified.
2. Ask the user to file a police report if stolen.

## Escalate when
- Always. Use `escalate_to_tier2` so the device can be remotely locked or wiped, with the last check-in time and what data might be on it.
