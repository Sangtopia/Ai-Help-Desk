---
id: KB-009
title: Outlook not syncing or stuck on Updating
category: email
tools: lookup_user, check_device_status
---

## Symptoms
- Outlook says "Disconnected", "Trying to connect", or "Updating this folder" for a long time.
- New emails show on the phone or in Outlook on the web but not in Outlook on the laptop.

## Quick checks
1. Ask the user to open Outlook on the web. If mail is there, the mailbox is fine and the problem is the laptop's Outlook.
2. Run `lookup_user` to check mailbox usage. A full mailbox stops syncing (KB-010).
3. Run `check_device_status` to confirm the laptop is online.
4. Check that Outlook is not in Work Offline mode (Send / Receive tab).

## Fix
1. Close and reopen Outlook.
2. Turn off Work Offline if it is on.
3. Restart the laptop to clear stuck connections.
4. If it is still stuck, rebuild the Outlook profile: Control Panel, Mail, Show Profiles, Add a new profile, set it as default, and open Outlook. The mailbox will re-download.

## Escalate when
- Outlook on the web also does not show new mail.
- Several users report the same issue at the same time (possible service outage).
