---
id: KB-024
title: Add a network printer
category: printing
tools: check_device_status
---

## Symptoms
- User cannot see a printer in the print dialog.
- User moved desks or floors and needs the local printer.

## Quick checks
1. Find the printer hostname on the label on the printer (for example BL-PR-FL1).
2. Run `check_device_status` to confirm it is online.
3. The laptop must be in the office or on VPN.

## Fix
1. Settings, Bluetooth & devices, Printers & scanners, Add device.
2. If it is not listed, choose "Add manually" and enter the printer hostname.
3. Set it as the default printer if the user prints there most.
4. Print a test page.

## Escalate when
- The printer is online but cannot be added from any laptop.
