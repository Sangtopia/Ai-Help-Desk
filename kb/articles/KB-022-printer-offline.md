---
id: KB-022
title: Printer offline
category: printing
tools: check_device_status
---

## Symptoms
- Print jobs fail with "Printer offline".
- Nobody on the floor can print to the same printer.

## Quick checks
1. Run `check_device_status` on the printer hostname (for example BL-PR-FL2).
   - `online: false` for everyone: the printer itself is the problem.
   - `online: true`: the issue is the user's laptop (KB-023).
2. Ask someone near the printer to check its screen for errors: paper jam, out of paper or toner, door open.

## Fix
1. Clear the error shown on the printer.
2. Power the printer off for 30 seconds and back on.
3. Check its network cable is connected and the link light is on.
4. Re-run `check_device_status` until it shows online, then ask the user to print a test page.
5. Meanwhile, users can print to another printer (KB-024).

## Escalate when
- The printer stays offline after a power cycle with no error shown (possible network or hardware fault).
