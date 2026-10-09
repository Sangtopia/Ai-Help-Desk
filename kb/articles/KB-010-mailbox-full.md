---
id: KB-010
title: Mailbox full or over quota
category: email
tools: lookup_user
---

## Symptoms
- "Your mailbox is almost full" warnings.
- User can receive but not send, or senders get bounce-backs.
- Outlook stops syncing.

## Quick checks
1. Run `lookup_user` and check `mailbox.percent_used`. Above 90% causes warnings; at 100% sending stops.

## Fix
1. Empty Deleted Items and Junk Email.
2. Sort the inbox and Sent Items by size and delete or save large attachments to OneDrive.
3. Turn on Online Archive if the user needs to keep old mail. Move mail older than a year into the archive.
4. Ask the user to check `percent_used` again after the mailbox updates (can take up to an hour).

## Escalate when
- Mailbox is still over 95% after cleanup and the user's role needs a larger quota (needs manager approval).
