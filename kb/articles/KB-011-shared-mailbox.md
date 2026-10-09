---
id: KB-011
title: Shared mailbox not showing in Outlook
category: email
tools: lookup_user, escalate_to_tier2
---

## Symptoms
- A shared mailbox such as billing@ or orders@ does not appear in the Outlook folder list.
- User can see the mailbox but cannot send as it.

## Quick checks
1. Confirm the user was actually granted access. New access can take up to an hour to appear.
2. Ask whether it shows in Outlook on the web (Add shared folder or mailbox).

## Fix
1. Restart Outlook. Shared mailboxes are added automatically after the permission applies.
2. If it still does not appear, add it manually: File, Account Settings, Change, More Settings, Advanced, Add.
3. Sending as the shared mailbox requires a separate "Send As" permission; adding the mailbox alone is not enough.

## Escalate when
- The user was never granted access: needs mailbox owner approval, then Tier 2 makes the change (see KB-006).
