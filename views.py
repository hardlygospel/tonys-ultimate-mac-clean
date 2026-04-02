"""
Five views + shared drawing components (banner, statusbar, proc list).
System info and process detail popups.
Help text.
"""
from __future__ import annotations

import curses
import os
from datetime import datetime
from typing import Any

import psutil

from .palette import ca
from .data import (
    history, format_bytes, format_packets,
    get_process_detail,
)
from .drawing import (
    safe_addstr, draw_box, sparkline,
    draw_hbar, draw_vgraph, draw_core_grid,
)
from .popups import show_popup


# ── Help text ────────────────────────────────────────────────

HELP_LINES: list[str] = [
    "╔════════════════════════════════════════════════════╗",
    "║       Tony Mac Stats  v4.0  —  Key Reference       ║",
    "╚════════════════════════════════════════════════════╝", "",
    "── Views ───────────────────────────────────────────────",
    "  Tab        Cycle to next view",
    "  1          Overview  (CPU + MEM graphs, cores, disk)",
    "  2          Network   (TX/RX graphs, interface table)",
    "  3          CPU Deep  (full-width CPU + all cores)",
    "  4          Full Net  (4 graphs: bytes + packets + disk IO)",
    "  5          Processes (compact list, max rows)",
    "  G          Toggle between last graph view and list", "",
    "── Navigation ──────────────────────────────────────────",
    "  ↑ / ↓       Move selection",
    "  PgUp/PgDn   Jump one page",
    "  Home/End     Jump to top/bottom", "",
    "── Themes (38 total) ───────────────────────────────────",
    "  t           Next theme",
    "  T           Previous theme",
    "  Ctrl+T      Theme picker menu", "",
    "── Process Actions ─────────────────────────────────────",
    "  K           Kill   (SIGKILL — immediate force)",
    "  Z           Pause  (SIGSTOP — suspend)",
    "  R           Resume (SIGCONT — continue)",
    "  Enter / I   Process detail popup", "",
    "── Sort (list/process view) ────────────────────────────",
    "  c   CPU%    m   Memory%    p   PID    n   Name", "",
    "── Other ───────────────────────────────────────────────",
    "  H    This help screen",
    "  S    System overview popup",
    "  F    Filter / search processes by name",
    "  r    Force data refresh now",
    "  q    Quit Tony Mac Stats", "",
    "── Themes ──────────────────────────────────────────────",
    "  Dark:   Synthwave  Matrix  Ocean  Dracula  Blood Moon",
    "          Neon City  Hacker  Deep Space  Midnight  Ember",
    "          Cobalt  Forest  Retro Terminal  Twilight  Amber",
    "  Pastel: Cotton Candy  Mint Breeze  Lavender Mist",
    "          Peach Fuzz  Sakura  Baby Blue  Blush  Butter",
    "          Seafoam  Wisteria  Lemon Drop  Coral",
    "          Lilac Dream  Morning Mist",
    "  Other:  Arctic  Monochrome  Neon Pink  Sunset",
    "          Neon Aqua  Pastel Rainbow  Dusk  Tangerine  Rose Gold", "",
    "Tip: Graphs auto-scale to peak value.",
    "Tip: No sudo needed — processes you can't access are skipped.",
    "Tip: Use a 256-colour terminal (xterm-256color) for full themes.",
]


# ── Shared banner / statusbar ────────────────────────────────

VIEW_NAMES: list[str] = ["Overview", "Network", "CPU Deep", "Full Net", "Processes"]


def draw_banner(scr: Any, h: int, w: int, theme_name: str,
                view_idx: int) -> None:
    now = datetime.now().strftime("%H:%M:%S")
    vname = VIEW_NAMES[view_idx] if view_idx < len(VIEW_NAMES) else ""
    line = f"  ◈  Tony Mac Stats  ◈  {theme_name}  ◈  {vname}  (Tab=next  t=theme  H=help)"
    safe_addstr(scr, 0, 0, " " * (w - 1), ca("header"))
    safe_addstr(scr, 0, 2, line[:w - len(now) - 4], ca("header"))
    safe_addstr(scr, 0, w - len(now) - 2, now, ca("header"))


def draw_statusbar(scr: Any, h: int, w: int, extra: str = "") -> None:
    base = " q:Quit  Tab:View  t/T:Theme  H:Help  S:Sys  r:Refresh"
    bar = (base + "  " + extra) if extra else base
    safe_addstr(scr, h - 1, 0, " " * (w - 1), ca("status"))
    safe_addstr(scr, h - 1, 1, bar[:w - 2], ca("status"))


# ── Process list (shared across views) ───────────────────────

def filter_procs(procs: list[dict], filt: str) -> list[dict]:
    if not filt:
        return procs
    fl = filt.lower()
    return [p for p in procs if fl in (p.get("name") or "").lower()]


def draw_proc_list(scr: Any, oy: int, ox: int, bh: int, bw: int,
                   procs: list[dict], sel: int, scroll: int, filt: str,
                   title: str = "Top Processes") -> None:
    if bh < 3 or bw < 20:
        return
    draw_box(scr, oy, ox, bh, bw, title)
    visible = filter_procs(procs, filt)
    hdr = f"{'PID':>7}  {'NAME':<22}  {'CPU%':>6}  {'MEM%':>5}  {'THR':>4}  {'USER':<10}"
    safe_addstr(scr, oy + 1, ox + 1, hdr[:bw - 2], ca("title"))
    for i in range(bh - 3):
        idx = scroll + i
        row = oy + 2 + i
        if row >= oy + bh - 1:
            break
        if idx >= len(visible):
            break
        p = visible[idx]
        pid = p.get("pid") or 0
        name = (p.get("name") or "")[:22]
        cpu = float(p.get("cpu_percent") or 0)
        mem = float(p.get("memory_percent") or 0)
        thr = p.get("num_threads") or 0
        user = (p.get("username") or "?")[:10]
        line = f"{pid:>7}  {name:<22}  {cpu:>6.1f}  {mem:>5.2f}  {thr:>4}  {user:<10}"
        if idx == sel:
            aa = ca("row_selected")
        elif cpu > 50:
            aa = ca("row_highlight") | curses.A_BOLD
        else:
            aa = ca("row_normal")
        safe_addstr(scr, row, ox, " " * bw, aa)
        safe_addstr(scr, row, ox + 1, line[:bw - 2], aa)


# ══════════════════════════════════════════════════════════════
#  VIEW 1 — OVERVIEW
# ══════════════════════════════════════════════════════════════

def view_overview(scr: Any, si: dict, procs: list, sel: int,
                  scroll: int, filt: str) -> None:
    h, w = scr.getmaxyx()
    content_h = h - 2

    top_h = max(6, content_h * 2 // 5)
    mid_h = max(4, content_h // 5)
    list_y = 1 + top_h + mid_h
    list_h = max(3, h - list_y - 1)

    lw = w // 2
    rw = w - lw

    # CPU graph (left)
    draw_vgraph(scr, 1, 0, lw, top_h, "cpu",
                f"CPU {si['cpu']:5.1f}%  load {si['load'][0]:.2f}",
                ca("bar_cpu"), ca("border"))
    safe_addstr(scr, top_h, 2,
                f" {si['cpu_count']} logical / {si['cpu_count_phys']} physical  "
                f"load {si['load'][1]:.2f} {si['load'][2]:.2f} ",
                ca("dim"))

    # MEM graph (right)
    draw_vgraph(scr, 1, lw, rw, top_h, "mem",
                f"MEM {si['mem_pct']:5.1f}%  {format_bytes(si['mem_used'])}/{format_bytes(si['mem_total'])}",
                ca("bar_mem"), ca("border"))
    safe_addstr(scr, top_h, lw + 2,
                f" Swap {si['swap_pct']:.1f}%  {format_bytes(si['swap_used'])}/{format_bytes(si['swap_total'])} ",
                ca("dim"))

    # Per-core grid (left)
    draw_box(scr, 1 + top_h, 0, mid_h, lw, "Per-Core CPU")
    draw_core_grid(scr, 2 + top_h, 1, lw - 2, mid_h - 2,
                   si.get("cpus", [si["cpu"]]))

    # Disk & Net stats panel (right)
    draw_box(scr, 1 + top_h, lw, mid_h, rw, "Disk & Network")
    r = 2 + top_h
    dp = si["disk_pct"]
    safe_addstr(scr, r, lw + 2, f"Disk {dp:4.1f}%", ca("bar_disk"))
    draw_hbar(scr, r, lw + 10, max(4, rw - 26), dp, ca("bar_disk"),
              f" {format_bytes(si['disk_used'])}/{format_bytes(si['disk_total'])}", ca("dim"))
    safe_addstr(scr, r + 1, lw + 2,
                f"↑ TX  {format_bytes(si['net_tx']):>10}/s"
                f"  {format_packets(si['net_tx_pkt'])} pkt/s", ca("bar_net"))
    safe_addstr(scr, r + 2, lw + 2,
                f"↓ RX  {format_bytes(si['net_rx']):>10}/s"
                f"  {format_packets(si['net_rx_pkt'])} pkt/s", ca("bar_alt"))
    if mid_h > 4:
        sl = min(rw - 8, 28)
        safe_addstr(scr, r + 3, lw + 2, "↑ " + sparkline("net_tx", sl), ca("bar_net"))
    if mid_h > 5:
        safe_addstr(scr, r + 4, lw + 2, "↓ " + sparkline("net_rx", sl if mid_h > 4 else 28),
                    ca("bar_alt"))
    if mid_h > 6:
        safe_addstr(scr, r + 5, lw + 2,
                    f"Conns:{si['conn_count']}  "
                    f"R:{format_bytes(si['disk_read'])}/s W:{format_bytes(si['disk_write'])}/s",
                    ca("dim"))

    draw_proc_list(scr, list_y, 0, list_h, w, procs, sel, scroll, filt)


# ══════════════════════════════════════════════════════════════
#  VIEW 2 — NETWORK
# ══════════════════════════════════════════════════════════════

def view_network(scr: Any, si: dict, procs: list, sel: int,
                 scroll: int, filt: str) -> None:
    h, w = scr.getmaxyx()
    content_h = h - 2
    graph_h = max(7, content_h * 2 // 5)
    iface_h = max(5, content_h // 4)
    list_y = 1 + graph_h + iface_h
    list_h = max(3, h - list_y - 1)
    lw = w // 2
    rw = w - lw

    # TX graph (left)
    draw_vgraph(scr, 1, 0, lw, graph_h, "net_tx",
                f"Net TX  {format_bytes(si['net_tx'])}/s",
                ca("bar_net"), ca("border"), "B/s")
    safe_addstr(scr, graph_h, 2,
                f" sent:{format_bytes(si['net_sent_total'])}  pkt:{format_packets(si['net_tx_pkt'])}/s ",
                ca("dim"))

    # RX graph (right)
    draw_vgraph(scr, 1, lw, rw, graph_h, "net_rx",
                f"Net RX  {format_bytes(si['net_rx'])}/s",
                ca("bar_alt"), ca("border"), "B/s")
    safe_addstr(scr, graph_h, lw + 2,
                f" recv:{format_bytes(si['net_recv_total'])}  pkt:{format_packets(si['net_rx_pkt'])}/s ",
                ca("dim"))

    # Interface table
    draw_box(scr, 1 + graph_h, 0, iface_h, w, "Network Interfaces")
    irow = 2 + graph_h
    safe_addstr(scr, irow, 2,
                f"{'Interface':<14} {'TX Total':>12} {'RX Total':>12}"
                f" {'TX pkt':>9} {'RX pkt':>9}  {'Flags':<10}",
                ca("title"))
    irow += 1
    ifaces = si.get("ifaces") or {}
    if_stats_obj = psutil.net_if_stats() if hasattr(psutil, "net_if_stats") else {}
    for iname, stats in list(ifaces.items())[:iface_h - 3]:
        if irow >= 1 + graph_h + iface_h - 1:
            break
        speed = ""
        try:
            ifs = if_stats_obj.get(iname)
            if ifs:
                speed = f"{'UP' if ifs.isup else 'dn'} {ifs.speed}Mb"
        except Exception:
            pass
        safe_addstr(scr, irow, 2,
                    f"{iname:<14} {format_bytes(stats.bytes_sent):>12} {format_bytes(stats.bytes_recv):>12}"
                    f" {format_packets(stats.packets_sent):>9} {format_packets(stats.packets_recv):>9}  {speed:<10}",
                    ca("row_normal"))
        irow += 1
    er = 1 + graph_h + iface_h - 2
    safe_addstr(scr, er, 2,
                f"Errors ↑{si['net_errout']} ↓{si['net_errin']}  "
                f"Drops ↑{si['net_dropout']} ↓{si['net_dropin']}  "
                f"Connections: {si['conn_count']}",
                ca("dim"))

    draw_proc_list(scr, list_y, 0, list_h, w, procs, sel, scroll, filt)


# ══════════════════════════════════════════════════════════════
#  VIEW 3 — CPU DEEP DIVE
# ══════════════════════════════════════════════════════════════

def view_cpu_deep(scr: Any, si: dict, procs: list, sel: int,
                  scroll: int, filt: str) -> None:
    h, w = scr.getmaxyx()
    content_h = h - 2
    cpu_h = max(7, content_h * 2 // 5)
    core_h = max(4, content_h // 5)
    bot_h = max(4, content_h // 5)
    list_y = 1 + cpu_h + core_h + bot_h
    list_h = max(3, h - list_y - 1)
    lw = w // 2
    rw = w - lw

    # Full-width CPU history
    draw_vgraph(scr, 1, 0, w, cpu_h, "cpu",
                f"CPU History  {si['cpu']:5.1f}%  "
                f"load {si['load'][0]:.2f} {si['load'][1]:.2f} {si['load'][2]:.2f}",
                ca("bar_cpu"), ca("border"))
    safe_addstr(scr, cpu_h, 2,
                f" {si['cpu_count']} logical / {si['cpu_count_phys']} physical cores  "
                f"uptime {si['uptime']} ",
                ca("dim"))

    # Full-width per-core
    draw_box(scr, 1 + cpu_h, 0, core_h, w, "Per-Core CPU Utilisation")
    draw_core_grid(scr, 2 + cpu_h, 1, w - 2, core_h - 2,
                   si.get("cpus", [si["cpu"]]))

    # Bottom left: MEM graph
    draw_vgraph(scr, 1 + cpu_h + core_h, 0, lw, bot_h, "mem",
                f"MEM {si['mem_pct']:5.1f}%",
                ca("bar_mem"), ca("border"))

    # Bottom right: Network quick stats
    draw_box(scr, 1 + cpu_h + core_h, lw, bot_h, rw, "Network Quick")
    nr = 2 + cpu_h + core_h
    safe_addstr(scr, nr, lw + 2, f"↑ TX  {format_bytes(si['net_tx']):>10}/s", ca("bar_net"))
    safe_addstr(scr, nr + 1, lw + 2, f"↓ RX  {format_bytes(si['net_rx']):>10}/s", ca("bar_alt"))
    if bot_h > 3:
        sl = min(rw - 6, 24)
        safe_addstr(scr, nr + 2, lw + 2, "↑ " + sparkline("net_tx", sl), ca("bar_net"))
    if bot_h > 4:
        safe_addstr(scr, nr + 3, lw + 2, "↓ " + sparkline("net_rx", sl), ca("bar_alt"))
    if bot_h > 5:
        safe_addstr(scr, nr + 4, lw + 2,
                    f"Conns:{si['conn_count']}  "
                    f"Disk R:{format_bytes(si['disk_read'])}/s", ca("dim"))

    draw_proc_list(scr, list_y, 0, list_h, w, procs, sel, scroll, filt)


# ══════════════════════════════════════════════════════════════
#  VIEW 4 — FULL NETWORK / FOUR GRAPHS
# ══════════════════════════════════════════════════════════════

def view_full_net(scr: Any, si: dict, procs: list, sel: int,
                  scroll: int, filt: str) -> None:
    h, w = scr.getmaxyx()
    content_h = h - 2
    top_h = max(6, content_h * 2 // 5)
    mid_h = max(4, content_h // 5)
    list_y = 1 + top_h + mid_h
    list_h = max(3, h - list_y - 1)

    # Four equal-width graphs across the top
    qw = [w // 4, w // 4, w // 4, w - 3 * (w // 4)]
    ox = 0
    configs = [
        ("net_tx",     f"TX B/s  {format_bytes(si['net_tx'])}/s",          "bar_net",  "B/s"),
        ("net_rx",     f"RX B/s  {format_bytes(si['net_rx'])}/s",          "bar_alt",  "B/s"),
        ("net_tx_pkt", f"TX pkt  {format_packets(si['net_tx_pkt'])}/s",    "bar_disk", "pkt"),
        ("net_rx_pkt", f"RX pkt  {format_packets(si['net_rx_pkt'])}/s",    "bar_mem",  "pkt"),
    ]
    for i, (key, title, slot, sc) in enumerate(configs):
        draw_vgraph(scr, 1, ox, qw[i], top_h, key, title,
                    ca(slot), ca("border"), sc)
        ox += qw[i]

    # Middle row: Stats panel | Disk Read | Disk Write
    lw2 = w // 3
    draw_box(scr, 1 + top_h, 0, mid_h, lw2, "Net Stats")
    r = 2 + top_h
    safe_addstr(scr, r, 2, f"Sent Total : {format_bytes(si['net_sent_total'])}", ca("bar_net"))
    safe_addstr(scr, r + 1, 2, f"Recv Total : {format_bytes(si['net_recv_total'])}", ca("bar_alt"))
    safe_addstr(scr, r + 2, 2, f"Errors ↑{si['net_errout']} ↓{si['net_errin']}", ca("row_highlight"))
    if mid_h > 4:
        safe_addstr(scr, r + 3, 2, f"Drops  ↑{si['net_dropout']} ↓{si['net_dropin']}", ca("dim"))
    if mid_h > 5:
        safe_addstr(scr, r + 4, 2, f"Conns  {si['conn_count']}", ca("dim"))

    rw2 = (w - lw2) // 2
    rw3 = w - lw2 - rw2
    draw_vgraph(scr, 1 + top_h, lw2, rw2, mid_h, "disk_read",
                f"Disk R  {format_bytes(si['disk_read'])}/s",
                ca("bar_disk"), ca("border"), "B/s")
    draw_vgraph(scr, 1 + top_h, lw2 + rw2, rw3, mid_h, "disk_write",
                f"Disk W  {format_bytes(si['disk_write'])}/s",
                ca("bar_mem"), ca("border"), "B/s")

    draw_proc_list(scr, list_y, 0, list_h, w, procs, sel, scroll, filt)


# ══════════════════════════════════════════════════════════════
#  VIEW 5 — COMPACT PROCESS LIST
# ══════════════════════════════════════════════════════════════

def view_processes(scr: Any, si: dict, procs: list, sel: int,
                   scroll: int, filt: str, sort_key: str) -> None:
    h, w = scr.getmaxyx()

    # Compact stat bar (3 rows)
    bw = max(6, min(12, (w - 70) // 4 + 6))
    x = 1

    # Row 1: bars + sparklines
    for lbl, pct, hk, slot in [
        (f"CPU{si['cpu']:4.0f}%", si["cpu"], "cpu", "bar_cpu"),
        (f"MEM{si['mem_pct']:4.0f}%", si["mem_pct"], "mem", "bar_mem"),
        (f"DSK{si['disk_pct']:4.0f}%", si["disk_pct"], None, "bar_disk"),
    ]:
        safe_addstr(scr, 1, x, lbl, ca("title"))
        x += len(lbl) + 1
        filled = int(bw * pct / 100.0)
        safe_addstr(scr, 1, x, "█" * filled + "░" * (bw - filled), ca(slot))
        x += bw + 1
        if hk:
            sl = sparkline(hk, min(10, max(0, w - x - 55)))
            safe_addstr(scr, 1, x, "▸" + sl, ca("graph"))
            x += 12

    safe_addstr(scr, 1, x, f"up:{si['uptime']}", ca("status"))

    # Row 2: network
    x = 1
    safe_addstr(scr, 2, x, f"↑TX {format_bytes(si['net_tx']):>8}/s", ca("bar_net"))
    x += 20
    safe_addstr(scr, 2, x, f"↓RX {format_bytes(si['net_rx']):>8}/s", ca("bar_alt"))
    x += 20
    safe_addstr(scr, 2, x, f"Pkt↑{format_packets(si['net_tx_pkt'])}/s", ca("dim"))
    x += 14
    safe_addstr(scr, 2, x, f"Pkt↓{format_packets(si['net_rx_pkt'])}/s", ca("dim"))
    x += 14
    safe_addstr(scr, 2, x, f"Conns:{si['conn_count']}", ca("dim"))

    # Row 3: disk + load
    cpus = si.get("cpus", [si["cpu"]])
    avg = sum(cpus) / len(cpus) if cpus else 0
    safe_addstr(scr, 3, 1,
                f"DiskR:{format_bytes(si['disk_read'])}/s  DiskW:{format_bytes(si['disk_write'])}/s"
                f"  Load:{si['load'][0]:.2f}/{si['load'][1]:.2f}/{si['load'][2]:.2f}"
                f"  Cores:{si['cpu_count']}  AvgCore:{avg:.1f}%"
                f"  Err↑{si['net_errout']} ↓{si['net_errin']}",
                ca("dim"))

    safe_addstr(scr, 4, 0, "─" * (w - 1), ca("border"))

    hdr = (f"{'PID':>7}  {'NAME':<25}  {'STATUS':<8}"
           f"  {'CPU%':>6}  {'MEM%':>5}  {'THR':>4}  {'USER':<12}")
    safe_addstr(scr, 5, 0, " " * (w - 1), ca("title"))
    safe_addstr(scr, 5, 1, hdr[:w - 2], ca("title"))

    visible = filter_procs(procs, filt)
    for i in range(h - 8):
        idx = scroll + i
        row = 6 + i
        if row >= h - 1:
            break
        if idx >= len(visible):
            safe_addstr(scr, row, 0, " " * (w - 1), 0)
            continue
        p = visible[idx]
        pid = p.get("pid") or 0
        name = (p.get("name") or "")[:25]
        st = (p.get("status") or "")[:8]
        cpu = float(p.get("cpu_percent") or 0)
        mem = float(p.get("memory_percent") or 0)
        thr = p.get("num_threads") or 0
        user = (p.get("username") or "?")[:12]
        line = (f"{pid:>7}  {name:<25}  {st:<8}"
                f"  {cpu:>6.1f}  {mem:>5.2f}  {thr:>4}  {user:<12}")
        if idx == sel:
            aa = ca("row_selected")
        elif cpu > 50:
            aa = ca("row_highlight") | curses.A_BOLD
        else:
            aa = ca("row_normal")
        safe_addstr(scr, row, 0, " " * (w - 1), aa)
        safe_addstr(scr, row, 1, line[:w - 2], aa)

    sort_hint = f"Sort:{sort_key.upper()}  c/m/p/n=sort  K=kill  Z=pause  R=resume  I=detail  F=filter"
    draw_statusbar(scr, h, w, sort_hint)


# ── System info popup ────────────────────────────────────────

def show_sys_popup(scr: Any, si: dict) -> None:
    lo = si["load"]
    lines = [
        "Tony Mac Stats — System Overview", "═" * 50, "",
        f"  Host       : {os.uname().nodename}",
        f"  OS         : {os.uname().sysname} {os.uname().release}",
        f"  Arch       : {os.uname().machine}", "",
        f"  CPU        : {si['cpu']:.1f}%  ({si['cpu_count']} logical / "
        f"{si['cpu_count_phys']} physical cores)",
        f"  Load Avg   : {lo[0]:.2f}  {lo[1]:.2f}  {lo[2]:.2f}  (1m 5m 15m)",
        f"  Memory     : {format_bytes(si['mem_used'])} / {format_bytes(si['mem_total'])}"
        f"  ({si['mem_pct']:.1f}%)",
        f"  Swap       : {format_bytes(si['swap_used'])} / {format_bytes(si['swap_total'])}"
        f"  ({si['swap_pct']:.1f}%)",
        f"  Disk (/)   : {format_bytes(si['disk_used'])} / {format_bytes(si['disk_total'])}"
        f"  ({si['disk_pct']:.1f}%)",
        f"  Disk Read  : {format_bytes(si['disk_read'])}/s",
        f"  Disk Write : {format_bytes(si['disk_write'])}/s", "",
        f"  Net TX     : {format_bytes(si['net_tx'])}/s  ({format_packets(si['net_tx_pkt'])} pkt/s)",
        f"  Net RX     : {format_bytes(si['net_rx'])}/s  ({format_packets(si['net_rx_pkt'])} pkt/s)",
        f"  Net Errors : ↑{si['net_errout']}  ↓{si['net_errin']}",
        f"  Net Drops  : ↑{si['net_dropout']}  ↓{si['net_dropin']}",
        f"  Connections: {si['conn_count']}",
        f"  Uptime     : {si['uptime']}", "",
        "── Network Interfaces ──────────────────────────────",
    ]
    for iname, stats in (si.get("ifaces") or {}).items():
        lines.append(
            f"  {iname:<14}  TX:{format_bytes(stats.bytes_sent):>10}"
            f"  RX:{format_bytes(stats.bytes_recv):>10}"
            f"  pTX:{format_packets(stats.packets_sent):>6}"
            f"  pRX:{format_packets(stats.packets_recv):>6}")
    show_popup(scr, lines, "System Overview")


# ── Process detail popup ─────────────────────────────────────

def show_proc_popup(scr: Any, pid: int) -> None:
    d = get_process_detail(pid)
    lines = [f"Process Detail — PID {pid}", "═" * 52, ""]
    for k, v in d.items():
        if k != "Origin":
            lines.append(f"  {k:<12}: {v}")
    lines += [
        "", "─" * 52, "Origin / Classification", "─" * 52,
        f"  {d.get('Origin', 'Unknown')}", "",
        "Safety notes:",
        "  System processes (/System /usr /sbin) are part of macOS.",
        "  Use Z (SIGSTOP) to pause, R to resume.",
        "  K (SIGKILL) cannot be caught — last resort only.",
    ]
    show_popup(scr, lines, f"Process: {d.get('Name', '?')}")


# ── View dispatch table ──────────────────────────────────────

VIEWS = [
    view_overview,    # 0
    view_network,     # 1
    view_cpu_deep,    # 2
    view_full_net,    # 3
    view_processes,   # 4 (takes extra sort_key arg)
]

NUM_VIEWS: int = len(VIEWS)
