---
id: KB-003
title: Temporary password not working or must change password at sign-in
category: account_access
tools: lookup_user, unlock_account
---

## Symptoms
- User was given a temporary password but it is rejected.
- Sign-in keeps asking to change the password, then fails.
- New hire cannot sign in on day one.

## Quick checks
1. Run `lookup_user` and check `must_change_password` and account status.
2. Ask whether they are typing it on the Windows sign-in screen or a web page. The change-password prompt works best on the laptop sign-in screen while connected to the office network or VPN.
3. Check for typing issues: Caps Lock, keyboard language, confusing characters (l vs I, 0 vs O).

## Fix
1. Have the user sign in on the Windows sign-in screen and set a new password when prompted.
2. The new password must be at least 14 characters and not reuse a recent password.
3. If too many attempts locked the account, run `unlock_account` and try again.
4. If the temporary password truly does not work, issue a new one following KB-002.

## Escalate when
- The account shows `active` with no change required, yet no password works.
