---
id: KB-023
title: Print jobs stuck in the queue
category: printing
tools: check_device_status
---

## Symptoms
- Documents sit in the print queue with "Error" or "Printing" and never come out.
- Other people can print to the same printer.

## Quick checks
1. Run `check_device_status` on the printer. If it is offline, follow KB-022 instead.

## Fix
1. Open Settings, Bluetooth & devices, Printers & scanners, select the printer, Open print queue, and cancel all documents.
2. Restart the laptop to restart the print spooler.
3. Print a test page.
4. If it still fails, remove the printer and add it again (KB-024).

## Escalate when
- Stuck jobs return for several users after a restart.
