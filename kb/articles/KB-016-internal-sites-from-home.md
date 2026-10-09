---
id: KB-016
title: Can't reach internal sites while working from home
category: network_vpn
tools: lookup_user
---

## Symptoms
- Internal websites, the intranet, or shared drives do not load from home.
- Public websites work fine.

## Quick checks
1. Is the VPN connected? Internal resources need VPN from outside the office.
2. Run `lookup_user` and check `vpn_access`. If it is false, VPN was removed (often for a security block, see KB-031).

## Fix
1. Connect to VPN, then retry the site.
2. If VPN will not connect, follow KB-013.
3. If VPN connects but one internal site still fails, clear the browser cache or try a private window.

## Escalate when
- VPN is connected and no internal sites work.
