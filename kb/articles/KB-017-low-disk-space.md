---
id: KB-017
title: Laptop running low on disk space
category: devices_hardware
tools: check_device_status
---

## Symptoms
- "Low disk space" warnings.
- Windows updates fail; the laptop is slow; files will not save.

## Quick checks
1. Run `check_device_status` and look at `disk.percent_free`. Under 10% causes problems.

## Fix
1. Empty the Recycle Bin and the Downloads folder.
2. Run Disk Cleanup (or Settings, System, Storage, Temporary files) and remove temporary files and old Windows Update files.
3. Turn on OneDrive Files On-Demand so synced files stay in the cloud until opened.
4. Uninstall apps the user no longer needs.
5. Re-run `check_device_status` to confirm free space has improved.

## Escalate when
- Free space is still under 10% after cleanup (may need a larger drive or replacement laptop).
