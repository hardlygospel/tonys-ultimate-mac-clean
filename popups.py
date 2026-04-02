"""
Popup system — scrollable info, confirmation, filter input, menu picker.
All popups switch to blocking input mode and restore timed mode on exit.
"""
from __future__ import annotations

import curses
import textwrap
from typing import Any

from .palette import ca
from .drawing import safe_addstr, draw_box


# ── Input mode management ────────────────────────────────────

def set_blocking(scr: Any) -> None:
    """Switch getch() to fully blocking (for popups)."""
    try:
        curses.nocbreak()
        curses.cbreak()
        scr.nodelay(False)
    except curses.error:
        pass


def set_timed(scr: Any) -> None:
    """Restore half-delay timed mode for main loop."""
    try:
        scr.nodelay(False)
        curses.halfdelay(6)  # 0.6s timeout
    except curses.error:
        pass


# ── Scrollable popup ─────────────────────────────────────────

def show_popup(scr: Any, lines: list[str], title: str = "Info") -> None:
    """Scrollable popup with word-wrap. PgUp/PgDn/↑↓ to scroll, Q/Esc to close."""
    sh, sw = scr.getmaxyx()
    pw = min(sw - 4, 90)
    wrapped: list[str] = []
    for line in lines:
        if not line.strip():
            wrapped.append("")
        else:
            for wl in textwrap.wrap(str(line), pw - 4):
                wrapped.append(wl)
    ph = min(len(wrapped) + 4, sh - 2)
    py = max(0, (sh - ph) // 2)
    px = max(0, (sw - pw) // 2)

    if ph < 4 or pw < 10 or py + ph > sh or px + pw > sw:
        return

    try:
        win = curses.newwin(ph, pw, py, px)
    except curses.error:
        return

    vis = max(1, ph - 4)
    scroll = 0

    set_blocking(scr)
    try:
        while True:
            try:
                win.erase()
                draw_box(win, 0, 0, ph, pw, title, ca("border"))
                for i in range(vis):
                    idx = scroll + i
                    if idx < len(wrapped):
                        safe_addstr(win, i + 2, 2, wrapped[idx], ca("row_normal"))
                safe_addstr(win, ph - 1, 2,
                            " ↑↓  PgUp/PgDn scroll   Q / Esc close "[:pw - 4],
                            ca("status"))
                win.refresh()
            except curses.error:
                pass

            try:
                k = win.getch()
            except curses.error:
                break

            if k in (ord("q"), ord("Q"), 27):
                break
            elif k == curses.KEY_DOWN:
                scroll = min(scroll + 1, max(0, len(wrapped) - vis))
            elif k == curses.KEY_UP:
                scroll = max(scroll - 1, 0)
            elif k == curses.KEY_NPAGE:
                scroll = min(scroll + vis, max(0, len(wrapped) - vis))
            elif k == curses.KEY_PPAGE:
                scroll = max(scroll - vis, 0)
    finally:
        set_timed(scr)
        try:
            del win
        except Exception:
            pass


# ── Confirmation dialog ──────────────────────────────────────

def show_confirm(scr: Any, msg: str) -> bool:
    """Confirmation dialog. Returns True if user presses Y."""
    sh, sw = scr.getmaxyx()
    pw, ph = min(64, sw - 4), 5
    py = max(0, sh // 2 - 2)
    px = max(0, sw // 2 - pw // 2)
    if py + ph > sh or px + pw > sw:
        return False
    try:
        win = curses.newwin(ph, pw, py, px)
    except curses.error:
        return False

    set_blocking(scr)
    result = False
    try:
        win.erase()
        draw_box(win, 0, 0, ph, pw, "Confirm", ca("border"))
        safe_addstr(win, 2, 2, msg[:pw - 4], ca("row_normal"))
        safe_addstr(win, 3, 2, "  Y = yes   any other key = cancel", ca("status"))
        win.refresh()
        k = win.getch()
        result = k in (ord("y"), ord("Y"))
    except curses.error:
        pass
    finally:
        set_timed(scr)
        try:
            del win
        except Exception:
            pass
    return result


# ── Filter input popup ───────────────────────────────────────

def show_filter_popup(scr: Any, current: str) -> str:
    """Filter input popup with cursor editing. Esc cancels, Enter confirms."""
    sh, sw = scr.getmaxyx()
    pw, ph = min(52, sw - 4), 3
    py = max(0, sh // 2)
    px = max(0, sw // 2 - pw // 2)
    if py + ph > sh or px + pw > sw:
        return current
    try:
        win = curses.newwin(ph, pw, py, px)
    except curses.error:
        return current

    set_blocking(scr)
    buf = list(current)
    prompt = " Search: "
    result = current
    try:
        curses.curs_set(1)
    except curses.error:
        pass

    try:
        while True:
            s = "".join(buf)
            try:
                win.erase()
                draw_box(win, 0, 0, ph, pw, "Filter Processes", ca("border"))
                safe_addstr(win, 1, 2, (prompt + s + " ")[:pw - 3], ca("row_normal"))
                cur_x = 2 + len(prompt) + len(s)
                if cur_x < pw - 1:
                    try:
                        win.move(1, cur_x)
                    except curses.error:
                        pass
                win.refresh()
            except curses.error:
                pass
            try:
                k = win.getch()
            except curses.error:
                break
            if k == 27:
                buf = list(current)
                break
            elif k in (10, 13):
                break
            elif k in (curses.KEY_BACKSPACE, 127, 8):
                if buf:
                    buf.pop()
            elif 32 <= k <= 126:
                buf.append(chr(k))
        result = "".join(buf)
    finally:
        try:
            curses.curs_set(0)
        except Exception:
            pass
        set_timed(scr)
        try:
            del win
        except Exception:
            pass
    return result


# ── Menu picker ──────────────────────────────────────────────

def show_menu_popup(scr: Any, items: list[str], title: str,
                    current: int) -> int:
    """Scrollable menu picker. Returns selected index (or current on cancel)."""
    sh, sw = scr.getmaxyx()
    pw = min(54, sw - 4)
    ph = min(len(items) + 4, sh - 2)
    py = max(0, (sh - ph) // 2)
    px = max(0, (sw - pw) // 2)
    if ph < 4 or py + ph > sh or px + pw > sw:
        return current
    try:
        win = curses.newwin(ph, pw, py, px)
    except curses.error:
        return current

    sel = current
    set_blocking(scr)
    vis = ph - 4
    try:
        while True:
            scroll = max(0, min(sel - vis // 2, max(0, len(items) - vis)))
            try:
                win.erase()
                draw_box(win, 0, 0, ph, pw, title, ca("border"))
                for i in range(vis):
                    idx = scroll + i
                    if idx >= len(items):
                        break
                    marker = "► " if idx == sel else "  "
                    aa = ca("row_selected") if idx == sel else ca("row_normal")
                    label = f"{marker}{idx + 1:>2}. {items[idx]}"
                    safe_addstr(win, i + 2, 2, label[:pw - 4], aa)
                safe_addstr(win, ph - 1, 2,
                            " ↑↓ navigate   Enter select   Esc cancel"[:pw - 4],
                            ca("status"))
                win.refresh()
            except curses.error:
                pass
            try:
                k = win.getch()
            except curses.error:
                sel = current
                break
            if k in (27, ord("q")):
                sel = current
                break
            elif k == curses.KEY_UP:
                sel = max(sel - 1, 0)
            elif k == curses.KEY_DOWN:
                sel = min(sel + 1, len(items) - 1)
            elif k in (10, 13):
                break
            elif ord("1") <= k <= ord("9"):
                n = k - ord("1")
                if n < len(items):
                    sel = n
                    break
    finally:
        set_timed(scr)
        try:
            del win
        except Exception:
            pass
    return sel
