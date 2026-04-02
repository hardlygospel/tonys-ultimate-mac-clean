"""
Main application loop — input handling, view dispatch, state management.
"""
from __future__ import annotations

import curses
import os
import signal
import time
from typing import Any

from .palette import THEMES, THEME_NAMES, init_colours, ca
from .data import collect_system, collect_processes
from .drawing import safe_addstr
from .popups import (
    show_popup, show_confirm, show_filter_popup, show_menu_popup,
)
from .views import (
    HELP_LINES, VIEW_NAMES, VIEWS, NUM_VIEWS,
    draw_banner, draw_statusbar, filter_procs,
    view_processes,
    show_sys_popup, show_proc_popup,
)


def main(scr: Any) -> None:
    """Curses main loop — called by curses.wrapper()."""
    try:
        curses.curs_set(0)
    except curses.error:
        pass

    try:
        curses.halfdelay(6)  # 0.6s timeout
    except curses.error:
        pass

    # ── State ────────────────────────────────────────────────
    theme_idx = 0
    theme = THEMES[theme_idx]
    init_colours(theme)

    view_idx = 0
    sort_key = "cpu"

    sort_fns = {
        "cpu":  lambda p: float(p.get("cpu_percent") or 0),
        "mem":  lambda p: float(p.get("memory_percent") or 0),
        "pid":  lambda p: int(p.get("pid") or 0),
        "name": lambda p: (p.get("name") or "").lower(),
    }
    sort_reverse = {"cpu": True, "mem": True, "pid": False, "name": False}

    procs = collect_processes()
    si = collect_system()
    procs.sort(key=sort_fns[sort_key], reverse=sort_reverse[sort_key])

    sel = 0
    scroll = 0
    filt = ""
    last_tick = 0.0
    TICK_INTERVAL = 2.0

    def visible() -> list[dict]:
        return filter_procs(procs, filt)

    # ── Loop ─────────────────────────────────────────────────
    while True:
        # Data refresh
        now = time.time()
        if now - last_tick >= TICK_INTERVAL:
            try:
                procs = collect_processes()
                si = collect_system()
                procs.sort(key=sort_fns[sort_key], reverse=sort_reverse[sort_key])
            except Exception:
                pass
            last_tick = now

        # Draw
        h, w = scr.getmaxyx()
        if h < 8 or w < 40:
            scr.erase()
            safe_addstr(scr, 0, 0, "Terminal too small — resize and try again",
                        ca("row_highlight"))
            scr.refresh()
            time.sleep(0.3)
            k = scr.getch()
            if k in (ord("q"), ord("Q")):
                break
            continue

        try:
            scr.erase()
            draw_banner(scr, h, w, theme.name, view_idx)

            if view_idx == 4:
                view_processes(scr, si, procs, sel, scroll, filt, sort_key)
            else:
                VIEWS[view_idx](scr, si, procs, sel, scroll, filt)
                extra = "K:Kill  Z:Pause  R:Resume  I:Detail  F:Filter"
                draw_statusbar(scr, h, w, extra)

            scr.refresh()
        except curses.error:
            pass
        except Exception:
            pass

        # Input
        try:
            k = scr.getch()
        except curses.error:
            continue

        if k == -1:
            continue  # halfdelay timeout → loop, redraw

        vis = visible()
        vpc = len(vis)
        lh = max(1, h - 6)

        # Quit
        if k in (ord("q"), ord("Q")):
            break

        # Navigation
        elif k == curses.KEY_DOWN:
            if sel < vpc - 1:
                sel += 1
            if sel >= scroll + lh:
                scroll = sel - lh + 1
        elif k == curses.KEY_UP:
            if sel > 0:
                sel -= 1
            if sel < scroll:
                scroll = sel
        elif k == curses.KEY_NPAGE:
            sel = min(sel + lh, max(0, vpc - 1))
            scroll = min(scroll + lh, max(0, vpc - lh))
        elif k == curses.KEY_PPAGE:
            sel = max(sel - lh, 0)
            scroll = max(scroll - lh, 0)
        elif k == curses.KEY_HOME:
            sel = scroll = 0
        elif k == curses.KEY_END:
            sel = max(0, vpc - 1)
            scroll = max(0, vpc - lh)

        # View switching
        elif k in (9, ord("\t")):  # Tab = next view
            view_idx = (view_idx + 1) % NUM_VIEWS
        elif k == ord("1"):
            view_idx = 0
        elif k == ord("2"):
            view_idx = 1
        elif k == ord("3"):
            view_idx = 2
        elif k == ord("4"):
            view_idx = 3
        elif k == ord("5"):
            view_idx = 4
        elif k in (ord("g"), ord("G")):
            view_idx = 0 if view_idx != 0 else 4

        # Theme cycling
        elif k == ord("t"):
            theme_idx = (theme_idx + 1) % len(THEME_NAMES)
            theme = THEMES[theme_idx]
            init_colours(theme)
        elif k == ord("T"):
            theme_idx = (theme_idx - 1) % len(THEME_NAMES)
            theme = THEMES[theme_idx]
            init_colours(theme)
        elif k == 20:  # Ctrl+T
            new = show_menu_popup(scr, THEME_NAMES, "Choose Theme", theme_idx)
            theme_idx = new
            theme = THEMES[theme_idx]
            init_colours(theme)

        # Sort
        elif k == ord("c"):
            sort_key = "cpu"
            procs.sort(key=sort_fns["cpu"], reverse=True)
            sel = scroll = 0
        elif k == ord("m"):
            sort_key = "mem"
            procs.sort(key=sort_fns["mem"], reverse=True)
            sel = scroll = 0
        elif k == ord("p"):
            sort_key = "pid"
            procs.sort(key=sort_fns["pid"])
            sel = scroll = 0
        elif k == ord("n"):
            sort_key = "name"
            procs.sort(key=sort_fns["name"])
            sel = scroll = 0

        # Actions
        elif k in (ord("h"), ord("H")):
            show_popup(scr, HELP_LINES, "Help — Tony Mac Stats")
        elif k in (ord("s"), ord("S")):
            show_sys_popup(scr, si)
        elif k in (ord("f"), ord("F")):
            filt = show_filter_popup(scr, filt)
            sel = scroll = 0
        elif k == ord("r"):
            last_tick = 0.0  # force refresh

        elif k in (10, 13, ord("i"), ord("I")):
            if vis and sel < len(vis):
                pid = vis[sel].get("pid")
                if pid:
                    show_proc_popup(scr, pid)

        elif k == ord("K"):
            if vis and sel < len(vis):
                p = vis[sel]
                pid = p.get("pid")
                nm = p.get("name", "?")
                if pid and show_confirm(scr, f"KILL (SIGKILL)  {nm}  [PID {pid}]?"):
                    try:
                        os.kill(pid, signal.SIGKILL)
                    except Exception as e:
                        show_popup(scr, [str(e)], "Error")
                    last_tick = 0.0

        elif k == ord("Z"):
            if vis and sel < len(vis):
                p = vis[sel]
                pid = p.get("pid")
                nm = p.get("name", "?")
                if pid and show_confirm(scr, f"PAUSE (SIGSTOP)  {nm}  [PID {pid}]?"):
                    try:
                        os.kill(pid, signal.SIGSTOP)
                    except Exception as e:
                        show_popup(scr, [str(e)], "Error")

        elif k == ord("R"):
            if vis and sel < len(vis):
                pid = vis[sel].get("pid")
                if pid:
                    try:
                        os.kill(pid, signal.SIGCONT)
                    except Exception as e:
                        show_popup(scr, [str(e)], "Error")


def run() -> None:
    """Entry point — wraps curses setup/teardown."""
    try:
        curses.wrapper(main)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    run()
