---
id: KB-015
title: Slow network or slow file shares
category: network_vpn
tools: check_device_status
---

## Symptoms
- Opening files from shared drives takes a long time.
- Video calls freeze while other work is slow too.

## Quick checks
1. Ask whether only file shares are slow or everything (websites, Teams).
2. Working from home over VPN: shared drives are slower over VPN by design; large files are best opened from OneDrive or SharePoint.
3. Run `check_device_status`; very low disk space also makes the laptop feel slow (KB-017).

## Fix
1. Move closer to the Wi-Fi access point, or use a wired connection.
2. Pause large uploads or downloads (OneDrive sync, cloud backups).
3. Disconnect and reconnect VPN.
4. Restart the laptop if it has been up for days.

## Escalate when
- The whole office is slow at the same time.
- One specific share is slow for everyone.
