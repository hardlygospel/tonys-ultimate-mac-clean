"""
Data collection — system metrics, process list, process detail.
History buffers for time-series graphing.
No sudo required — uses only public psutil APIs.
"""
from __future__ import annotations

import collections
import os
import time
from datetime import datetime, timedelta
from typing import Any

import psutil

# ── History buffers ──────────────────────────────────────────
HISTORY_DEPTH: int = 250

history: dict[str, collections.deque] = {
    key: collections.deque([0.0] * 10, maxlen=HISTORY_DEPTH)
    for key in [
        "cpu", "mem", "net_tx", "net_rx",
        "net_tx_pkt", "net_rx_pkt", "disk_read", "disk_write",
    ]
}

_prev_counters: dict[str, int] = {
    "net_bytes_sent": 0, "net_bytes_recv": 0,
    "net_pkts_sent": 0, "net_pkts_recv": 0,
    "disk_read": 0, "disk_write": 0,
}


# ── Helpers ──────────────────────────────────────────────────

def safe_delta(new: int, old: int) -> int:
    """Non-negative delta between counter values."""
    return max(0, int(new) - int(old))


def format_bytes(b: float) -> str:
    """Format bytes to human-readable string."""
    if b is None:
        return "0B"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if b < 1024.0:
            return f"{b:.1f}{unit}"
        b /= 1024.0
    return f"{b:.1f}PB"


def format_packets(n: int) -> str:
    """Format packet count with K/M suffixes."""
    n = n or 0
    if n < 1_000:
        return str(n)
    if n < 1_000_000:
        return f"{n / 1000:.1f}K"
    return f"{n / 1_000_000:.1f}M"


# ── System metrics ───────────────────────────────────────────

def collect_system() -> dict[str, Any]:
    """Collect all system metrics. Never raises — bad values become 0."""
    global _prev_counters

    # CPU
    try:
        cpu = psutil.cpu_percent(interval=None)
        cpus = psutil.cpu_percent(interval=None, percpu=True) or [cpu]
    except Exception:
        cpu, cpus = 0.0, [0.0]

    # Memory
    try:
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()
        mem_pct, mem_used, mem_total = mem.percent, mem.used, mem.total
        swap_pct = swap.percent
        swap_used = getattr(swap, "used", 0)
        swap_total = getattr(swap, "total", 0)
    except Exception:
        mem_pct = mem_used = mem_total = swap_pct = swap_used = swap_total = 0

    # Disk usage
    try:
        disk = psutil.disk_usage("/")
        disk_pct, disk_used, disk_total = disk.percent, disk.used, disk.total
    except Exception:
        disk_pct = disk_used = disk_total = 0

    # Disk I/O (not available on all systems — silent skip)
    drr = drw = 0
    try:
        dio = psutil.disk_io_counters()
        if dio:
            drr = safe_delta(dio.read_bytes, _prev_counters["disk_read"])
            drw = safe_delta(dio.write_bytes, _prev_counters["disk_write"])
            _prev_counters["disk_read"] = dio.read_bytes
            _prev_counters["disk_write"] = dio.write_bytes
    except Exception:
        pass

    # Network I/O
    ntx = nrx = ntxp = nrxp = 0
    net_sent_total = net_recv_total = 0
    net_errin = net_errout = net_dropin = net_dropout = 0
    try:
        net = psutil.net_io_counters()
        ntx = safe_delta(net.bytes_sent, _prev_counters["net_bytes_sent"])
        nrx = safe_delta(net.bytes_recv, _prev_counters["net_bytes_recv"])
        ntxp = safe_delta(net.packets_sent, _prev_counters["net_pkts_sent"])
        nrxp = safe_delta(net.packets_recv, _prev_counters["net_pkts_recv"])
        net_sent_total = net.bytes_sent
        net_recv_total = net.bytes_recv
        net_errin = getattr(net, "errin", 0)
        net_errout = getattr(net, "errout", 0)
        net_dropin = getattr(net, "dropin", 0)
        net_dropout = getattr(net, "dropout", 0)
        _prev_counters["net_bytes_sent"] = net.bytes_sent
        _prev_counters["net_bytes_recv"] = net.bytes_recv
        _prev_counters["net_pkts_sent"] = net.packets_sent
        _prev_counters["net_pkts_recv"] = net.packets_recv
    except Exception:
        pass

    # Per-interface stats (read-only, no sudo needed)
    ifaces: dict = {}
    try:
        ifaces = psutil.net_io_counters(pernic=True) or {}
    except Exception:
        pass

    # Network connections count
    conn_count = 0
    try:
        conn_count = len(psutil.net_connections(kind="inet"))
    except Exception:
        pass

    # Uptime
    try:
        boot = psutil.boot_time()
        up = timedelta(seconds=int(time.time() - boot))
        dd = up.days
        hh, r = divmod(up.seconds, 3600)
        mm, ss = divmod(r, 60)
        uptime_str = f"{dd}d {hh:02}h {mm:02}m {ss:02}s"
    except Exception:
        uptime_str = "?"

    # Load average
    try:
        load = os.getloadavg()
    except Exception:
        load = (0.0, 0.0, 0.0)

    cpu_count = psutil.cpu_count() or 1
    cpu_count_phys = psutil.cpu_count(logical=False) or 1

    # Append to histories
    history["cpu"].append(cpu)
    history["mem"].append(mem_pct)
    history["net_tx"].append(ntx)
    history["net_rx"].append(nrx)
    history["net_tx_pkt"].append(ntxp)
    history["net_rx_pkt"].append(nrxp)
    history["disk_read"].append(drr)
    history["disk_write"].append(drw)

    return dict(
        cpu=cpu, cpus=cpus,
        mem_pct=mem_pct, mem_used=mem_used, mem_total=mem_total,
        swap_pct=swap_pct, swap_used=swap_used, swap_total=swap_total,
        disk_pct=disk_pct, disk_used=disk_used, disk_total=disk_total,
        disk_read=drr, disk_write=drw,
        net_tx=ntx, net_rx=nrx,
        net_tx_pkt=ntxp, net_rx_pkt=nrxp,
        net_sent_total=net_sent_total, net_recv_total=net_recv_total,
        net_errin=net_errin, net_errout=net_errout,
        net_dropin=net_dropin, net_dropout=net_dropout,
        conn_count=conn_count, ifaces=ifaces,
        uptime=uptime_str, load=load,
        cpu_count=cpu_count, cpu_count_phys=cpu_count_phys,
    )


# ── Process collection ───────────────────────────────────────

def collect_processes() -> list[dict[str, Any]]:
    """Collect process list. Never raises. No sudo — skips inaccessible procs."""
    out: list[dict[str, Any]] = []
    attrs = ["pid", "name", "status", "cpu_percent", "memory_percent", "num_threads"]
    for p in psutil.process_iter(attrs):
        try:
            info = {k: p.info.get(k) for k in attrs}
            try:
                info["username"] = p.username()
            except Exception:
                info["username"] = "?"
            out.append(info)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return out


def get_process_detail(pid: int) -> dict[str, str]:
    """Get deep info on one process. Never raises."""
    try:
        p = psutil.Process(pid)
        with p.oneshot():
            info: dict[str, str] = {
                "PID": str(p.pid),
                "Name": p.name(),
                "Status": p.status(),
            }
            try:    info["User"] = p.username()
            except: info["User"] = "?"
            try:    info["CPU %"] = f"{p.cpu_percent(interval=0.05):.1f}%"
            except: info["CPU %"] = "?"
            try:    info["Mem %"] = f"{p.memory_percent():.2f}%"
            except: info["Mem %"] = "?"
            try:
                mi = p.memory_info()
                info["RSS"] = format_bytes(mi.rss)
                info["VMS"] = format_bytes(mi.vms)
            except:
                info["RSS"] = info["VMS"] = "?"
            try:    info["Threads"] = str(p.num_threads())
            except: info["Threads"] = "?"
            try:    info["PPID"] = str(p.ppid())
            except: info["PPID"] = "?"
            try:    info["Nice"] = str(p.nice())
            except: info["Nice"] = "?"
            try:    info["Created"] = datetime.fromtimestamp(
                        p.create_time()).strftime("%Y-%m-%d %H:%M:%S")
            except: info["Created"] = "?"
            try:    info["Exe"] = p.exe() or "?"
            except: info["Exe"] = "?"
            try:    info["CWD"] = p.cwd() or "?"
            except: info["CWD"] = "?"
            try:    info["Cmdline"] = " ".join(p.cmdline())[:220] or "?"
            except: info["Cmdline"] = "?"
            try:    info["FDs"] = str(p.num_fds())
            except: info["FDs"] = "?"

            # Origin classification
            exe = info.get("Exe", "")
            if any(s in exe for s in ("/System/", "/usr/bin", "/usr/sbin",
                                       "/usr/libexec", "/sbin/")):
                origin = "macOS System — part of the OS, avoid killing"
            elif "/Applications/" in exe:
                origin = "App: " + exe.split("/Applications/")[1].split("/")[0]
            elif any(s in exe for s in ("/usr/local/", "/opt/homebrew/")):
                origin = "Homebrew / user-installed CLI"
            elif exe.startswith(("/private/var", "/var", "/tmp")):
                origin = "Temporary daemon or helper"
            elif info.get("User") == "root":
                origin = "Root daemon"
            else:
                origin = "User process"
            info["Origin"] = origin
        return info
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess) as e:
        return {"Error": str(e)}
