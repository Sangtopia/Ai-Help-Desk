---
id: KB-007
title: Expected email stuck in spam quarantine
category: email
tools: check_spam_quarantine, release_email
---

## Symptoms
- User is waiting for an email (invoice, quote, HR document) that never arrived.
- The sender says it was sent and did not bounce.

## Quick checks
1. Ask the user to check their Junk Email folder first.
2. Run `check_spam_quarantine` for the user's mailbox and match the sender and subject they expect.
3. Look at the quarantine reason and the `releasable` flag:
   - `spam` or `bulk`: can be released if the user confirms they expected it.
   - `phishing` or `malware`: never release. Follow KB-008.
4. Check the sender address carefully for look-alike domains (for example a capital I in place of a lowercase l).

## Fix
1. Confirm with the user that the specific message is expected and from a known sender.
2. Run `release_email` with the message id (needs tech approval).
3. Ask the user to confirm it arrived in their inbox.
4. If the same legitimate sender is quarantined often, note it so Tier 2 can review the filter.

## Escalate when
- The message the user wants is marked `phishing` or `malware` and they insist it is legitimate.
- Many users are missing mail from the same sender.
