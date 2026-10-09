---
id: KB-018
title: Device offline or not checking in to management
category: devices_hardware
tools: check_device_status, lookup_user, escalate_to_tier2
---

## Symptoms
- Device shows offline in management, or has not checked in for days.
- Updates and security policies are not reaching the laptop.

## Quick checks
1. Run `check_device_status` and look at `online`, `last_checkin`, and `warnings`.
   - Offline for a few hours: user may simply have it shut down.
   - No check-in for more than 7 days: needs follow-up.
2. Run `lookup_user` for the assigned user. A disabled user with an outstanding laptop means the device was never returned.

## Fix
1. Contact the user and ask them to power on the laptop, connect to the internet, and stay signed in for 30 minutes.
2. Restart the laptop to restart the management agent.
3. Re-run `check_device_status` to confirm a fresh check-in.

## Escalate when
- The user cannot locate the device (follow KB-021).
- The device belongs to a former employee and has not been returned.
- The device is online but still not checking in after a restart.
