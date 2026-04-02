"""
Drawing primitives — safe_addstr, draw_box, sparkline, horizontal bar,
vertical history graph, per-core CPU grid.
All writes are guarded — nothing in this module raises.
"""
from __future__ import annotations

import curses
from typing import Any, Optional

from .palette import ca
from .data import history

# ── Safe writing ─────────────────────────────────────────────

def safe_addstr(win: Any, y: int, x: int, txt: str, attr: int = 0) -> None:
    """Write text at (y,x) clipped to window bounds. Never raises."""
    try:
        mh, mw = win.getmaxyx()
        if y < 0 or y >= mh or x < 0 or x >= mw:
            return
        avail = mw - x
        if avail <= 0:
            return
        s = txt[:avail]
        if y == mh - 1 and x + len(s) >= mw:
            s = s[:mw - x - 1]
        if s:
            win.addstr(y, x, s, attr)
    except curses.error:
        pass


# ── Box drawing ──────────────────────────────────────────────

def draw_box(win: Any, oy: int, ox: int, bh: int, bw: int,
             title: str = "", attr: int = 0) -> None:
    """Draw a bordered box with optional title. All writes guarded."""
    mh, mw = win.getmaxyx()
    if oy < 0 or ox < 0 or bh < 2 or bw < 2:
        return
    if oy + bh > mh or ox + bw > mw:
        return
    a = attr or ca("border")

    def _ch(y: int, x: int, ch: int) -> None:
        try:
            if 0 <= y < mh and 0 <= x < mw:
                if y == mh - 1 and x == mw - 1:
                    return
                win.addch(y, x, ch, a)
        except curses.error:
            pass

    _ch(oy, ox, curses.ACS_ULCORNER)
    _ch(oy, ox + bw - 1, curses.ACS_URCORNER)
    _ch(oy + bh - 1, ox, curses.ACS_LLCORNER)
    _ch(oy + bh - 1, ox + bw - 1, curses.ACS_LRCORNER)
    for c in range(1, bw - 1):
        _ch(oy, ox + c, curses.ACS_HLINE)
        _ch(oy + bh - 1, ox + c, curses.ACS_HLINE)
    for r in range(1, bh - 1):
        _ch(oy + r, ox, curses.ACS_VLINE)
        _ch(oy + r, ox + bw - 1, curses.ACS_VLINE)
    if title:
        label = f" {title} "
        safe_addstr(win, oy, ox + 2, label[:bw - 4], ca("title") | curses.A_BOLD)


# ── Sparkline ────────────────────────────────────────────────

SPARK_CHARS: str = " ▁▂▃▄▅▆▇█"


def sparkline(hist_key: str, width: int) -> str:
    """Generate a sparkline string from history buffer."""
    if width <= 0:
        return ""
    vals = list(history[hist_key])[-width:]
    if not vals:
        return " " * width
    mx = max(vals) if max(vals) > 0 else 1.0
    return "".join(SPARK_CHARS[min(8, int(v / mx * 8))] for v in vals)


# ── Horizontal bar ───────────────────────────────────────────

def draw_hbar(win: Any, y: int, x: int, width: int, percent: float,
              attr: int = 0, suffix: str = "", suffix_attr: int = 0) -> None:
    """Draw a horizontal progress bar with optional suffix."""
    filled = max(0, min(width, int(width * percent / 100.0)))
    bar = "█" * filled + "░" * (width - filled)
    safe_addstr(win, y, x, bar, attr)
    if suffix:
        safe_addstr(win, y, x + width + 1, suffix, suffix_attr or ca("dim"))


# ── Vertical history graph ───────────────────────────────────

GRAPH_CHARS: str = " ▁▂▃▄▅▆▇█"


def draw_vgraph(win: Any, oy: int, ox: int, gw: int, gh: int,
                hist_key: str, title: str = "",
                bar_attr: int = 0, border_attr: int = 0,
                scale: str = "%", peak: Optional[float] = None) -> None:
    """Draw a bordered vertical history graph. Auto-scales to peak value."""
    mh, mw = win.getmaxyx()
    if gw < 4 or gh < 4 or oy < 0 or ox < 0:
        return
    if oy + gh > mh or ox + gw > mw:
        return

    draw_box(win, oy, ox, gh, gw, title, border_attr or ca("border"))

    inner_w = gw - 2
    inner_h = gh - 2

    vals = list(history[hist_key])[-inner_w:]
    real = [v for v in vals if v > 0]
    mx = peak if peak is not None else (max(real) if real else 1.0)
    if mx <= 0:
        mx = 1.0

    for ci, v in enumerate(vals):
        px = ox + 1 + ci
        if px >= ox + gw - 1 or px >= mw:
            continue
        fill = (v / mx) * inner_h

        for ri in range(inner_h):
            py = oy + gh - 2 - ri  # bottom-up
            if py <= oy or py >= oy + gh - 1:
                continue
            lo_f, hi_f = float(ri), float(ri + 1)

            if fill >= hi_f:
                safe_addstr(win, py, px, "█", bar_attr)
            elif fill > lo_f:
                idx = max(1, min(8, int((fill - lo_f) * 8 + 0.5)))
                safe_addstr(win, py, px, GRAPH_CHARS[idx], bar_attr)
            else:
                safe_addstr(win, py, px, "·", ca("dim"))

    # Scale labels
    if gw > 14:
        if mx >= 1_000_000:
            top = f"{mx / 1_000_000:5.1f}M{scale}"
        elif mx >= 1_000:
            top = f"{mx / 1000:5.1f}K{scale}"
        else:
            top = f"{mx:6.1f}{scale}"
        safe_addstr(win, oy + 1, ox + gw - len(top) - 1, top, ca("dim"))
        safe_addstr(win, oy + gh - 2, ox + gw - 6, "  0   ", ca("dim"))


# ── Per-core CPU grid ────────────────────────────────────────

def draw_core_grid(win: Any, oy: int, ox: int, bw: int, bh: int,
                   cpus: list[float]) -> None:
    """Draw compact per-core CPU bars in a grid layout."""
    col = ox
    row = oy
    bar_w = 8
    for i, pct in enumerate(cpus):
        lbl = f"C{i:<2} "
        needed = len(lbl) + bar_w + 7
        if col + needed > ox + bw:
            col = ox
            row += 1
        if row >= oy + bh:
            break
        safe_addstr(win, row, col, lbl, ca("dim"))
        col += len(lbl)
        filled = max(0, min(bar_w, int(bar_w * pct / 100.0)))
        safe_addstr(win, row, col, "█" * filled + "░" * (bar_w - filled), ca("bar_cpu"))
        safe_addstr(win, row, col + bar_w, f" {pct:4.0f}% ", ca("dim"))
        col += bar_w + 7
