---
id: KB-026
title: Microsoft 365 apps asking to sign in or activate
category: software
tools: lookup_user
---

## Symptoms
- Word, Excel, or Outlook show "Unlicensed product" or "Sign in to activate".
- Apps keep asking for the password in a loop.

## Quick checks
1. Run `lookup_user`. A locked account or a recent password reset causes repeated sign-in prompts.
2. Confirm the user is signing in with their company email, not a personal Microsoft account.

## Fix
1. In any Office app: File, Account, sign out, close all Office apps, reopen, and sign in with the company email.
2. If prompts loop after a password change, restart the laptop so Windows picks up the new password.
3. Settings, Accounts, Access work or school: remove any old or duplicate accounts.

## Escalate when
- The user signs in correctly and still sees "Unlicensed product" (license may not be assigned).
