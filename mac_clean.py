#!/usr/bin/env python3

"""
mac_clean.py — Zero-intervention Mac deep clean.
Works from any shell (fish, zsh, bash). No sudo needed for most steps.
Usage: python3 mac_clean.py [--full]
"""

import os
import sys
import re
import json
import shutil
import subprocess
import threading
import time
from pathlib import Path
from datetime import datetime

# ══════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════

HOME      = Path.home()
DESKTOP   = HOME / "Desktop"
DOWNLOADS = HOME / "Downloads"
PICTURES  = HOME / "Pictures"
DOCUMENTS = HOME / "Documents"

# Organised destination roots
# All destinations live under ~/Downloads/Organised to avoid iCloud cross-volume copies.
# iCloud syncs ~/Desktop, ~/Documents, ~/Pictures — moves into those folders are slow
# byte-for-byte copies. ~/Downloads is local by default on macOS.
ORGANISED       = DOWNLOADS / "Organised"
SCREENSHOTS_DIR = ORGANISED / "Screenshots"
PDFS_DIR        = ORGANISED / "PDFs"
DOCS_DIR        = ORGANISED / "Documents"
INSTALLERS_DIR  = ORGANISED / "Installers"

MISC    = DESKTOP   / "Misc"
ARCHIVE = DOWNLOADS / "Archive"

DAYS_OLD_DOWNLOADS  = 30    # archive downloads older than this many days
DAYS_OLD_INSTALLERS = 90    # move installers untouched for this many days

FULL_MODE = "--full" in sys.argv

INSTALLER_EXTENSIONS = {".dmg", ".pkg", ".mpkg", ".iso"}
DOC_EXTENSIONS       = {".docx", ".doc", ".odt", ".rtf", ".pages"}

# Folders we never reorganise — files already in these are left alone
PROTECTED_DIRS = {
    SCREENSHOTS_DIR, PDFS_DIR, DOCS_DIR, INSTALLERS_DIR,
    ORGANISED,
    MISC, ARCHIVE,
    DESKTOP   / "Screenshots",
    PICTURES  / "Screenshots",   # old iCloud location from previous runs
    DOCUMENTS / "PDFs",
    DOCUMENTS / "Documents",
}


# ══════════════════════════════════════════════════════════════
# COLOURS
# ══════════════════════════════════════════════════════════════

G  = "\033[0;32m"
Y  = "\033[1;33m"
B  = "\033[0;36m"
D  = "\033[2m"
NC = "\033[0m"
BD = "\033[1m"


# ══════════════════════════════════════════════════════════════
# PROGRESS SPINNER
# Spins on a background thread, prints elapsed seconds, and
# accepts live per-file updates so you can see exactly what
# it's doing and know it hasn't hung.
# ══════════════════════════════════════════════════════════════

class Spinner:
    FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(self, label: str):
        self.label   = label
        self.current = ""
        self._stop   = threading.Event()
        self._lock   = threading.Lock()
        self._start  = time.time()
        self._t      = threading.Thread(target=self._spin, daemon=True)
        self._t.start()

    def _spin(self):
        i = 0
        while not self._stop.is_set():
            elapsed = int(time.time() - self._start)
            with self._lock:
                sub = f"  {D}{self.current}{NC}" if self.current else ""
            line = (f"  {B}{self.FRAMES[i % len(self.FRAMES)]}{NC} "
                    f"{self.label}  {D}[{elapsed}s]{NC}{sub}")
            sys.stdout.write(f"\r{line:<130}")
            sys.stdout.flush()
            i += 1
            time.sleep(0.08)

    def update(self, msg: str):
        with self._lock:
            self.current = msg

    def stop(self, result: str = "", success: bool = True):
        self._stop.set()
        self._t.join()
        elapsed = int(time.time() - self._start)
        icon = f"{G}✔{NC}" if success else f"{Y}⚠{NC}"
        line = f"  {icon} {self.label}"
        if result:
            line += f"  {D}→{NC} {result}"
        line += f"  {D}[{elapsed}s]{NC}"
        sys.stdout.write(f"\r{line:<130}\n")
        sys.stdout.flush()


def pbar(done: int, total: int, width: int = 28) -> str:
    """Simple ASCII progress bar."""
    if total == 0:
        return ""
    filled = int(width * done / total)
    return f"[{'█' * filled}{'░' * (width - filled)}] {done}/{total}"


# ══════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════

def header(title: str):
    print(f"\n{B}{BD}▸ {title}{NC}")
    print(f"{D}  {'─' * 52}{NC}")

def ok(msg):   print(f"  {G}✔{NC} {msg}")
def info(msg): print(f"  {B}→{NC} {msg}")
def warn(msg): print(f"  {Y}⚠{NC} {msg}")
def skip(msg): print(f"  {D}– {msg} (skipped){NC}")

def human(b: int) -> str:
    if b >= 1_073_741_824: return f"{b/1_073_741_824:.1f} GB"
    if b >= 1_048_576:     return f"{b/1_048_576:.1f} MB"
    if b >= 1_024:         return f"{b/1_024:.1f} KB"
    return f"{b} B"

def dir_size(p) -> int:
    total = 0
    try:
        for f in Path(p).rglob("*"):
            try: total += f.stat().st_size
            except: pass
    except: pass
    return total

def run(cmd: str, **kw):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, **kw)

DATE_PAT = re.compile(r"(\d{4})-(\d{2})-(\d{2})")

def file_date(f: Path):
    """Return (year_str, month_str) from filename, falling back to creation time."""
    m = DATE_PAT.search(f.name)
    if m:
        return m.group(1), m.group(2)
    try:
        ts = f.stat().st_birthtime
    except AttributeError:
        ts = f.stat().st_mtime
    dt = datetime.fromtimestamp(ts)
    return f"{dt.year:04d}", f"{dt.month:02d}"

def unique_dest(dest_dir: Path, name: str) -> Path:
    """Non-destructive destination — appends _2, _3 … if name exists."""
    dest = dest_dir / name
    if not dest.exists():
        return dest
    stem, suffix = Path(name).stem, Path(name).suffix
    n = 2
    while True:
        c = dest_dir / f"{stem}_{n}{suffix}"
        if not c.exists():
            return c
        n += 1

def is_protected(f: Path) -> bool:
    for p in PROTECTED_DIRS:
        try:
            f.relative_to(p)
            return True
        except ValueError:
            pass
    return False

def move_dated(f: Path, dest_root: Path) -> bool:
    """Move f into dest_root/YYYY/MM/.
    Uses os.rename (instant on same volume); falls back to copy+delete
    only when crossing filesystem boundaries (e.g. iCloud Drive)."""
    if is_protected(f):
        return False
    year, month = file_date(f)
    dest_dir = dest_root / year / month
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = unique_dest(dest_dir, f.name)
    try:
        os.rename(f, dest)        # instant — same volume
        return True
    except OSError:
        pass
    try:
        shutil.copy2(str(f), str(dest))
        f.unlink()
        return True
    except Exception:
        return False


# ══════════════════════════════════════════════════════════════
# REPORT
# ══════════════════════════════════════════════════════════════

report      = []
total_freed = 0

def add(emoji, title, detail, freed=0):
    global total_freed
    total_freed += freed
    report.append({"emoji": emoji, "title": title, "detail": detail,
                   "freed": human(freed) if freed > 0 else ""})


# ══════════════════════════════════════════════════════════════
# BANNER
# ══════════════════════════════════════════════════════════════

start = time.time()
print(f"\n{BD}{B}")
print("  ╔════════════════════════════════════════════════╗")
print("  ║            🍎  MAC DEEP CLEAN                 ║")
print(f"  ║        {datetime.now():%d %b %Y  %H:%M}                    ║")
print("  ╚════════════════════════════════════════════════╝")
print(NC)

# Common shallow-sweep roots (top-level only — never recurse into these directly)
# PICTURES is excluded — we recurse into specific subdirs only (Screenshots, etc.)
# HOME is excluded — too broad; only explicit named roots are swept
SHALLOW_ROOTS = [DESKTOP, DOWNLOADS, DOCUMENTS]


# ══════════════════════════════════════════════════════════════
# 1. SCREENSHOTS  →  ~/Pictures/Screenshots/YYYY/MM
# ══════════════════════════════════════════════════════════════

header("📸  Screenshots — Consolidate & Sort")

def is_screenshot(name: str) -> bool:
    return (name.startswith("Screenshot ")
            or name.startswith("Screen Shot ")
            or name.startswith("Screenshot_"))

SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

# Explicit dirs to recurse into for screenshot consolidation.
# Includes old iCloud locations so we drain them into the local destination.
OLD_SS_DIRS = [
    DESKTOP   / "Screenshots",
    HOME      / "Screenshots",
    PICTURES  / "Screenshots",   # old iCloud destination from previous runs
    SCREENSHOTS_DIR,             # normalise existing target structure
]

# Shallow scan of common drop zones (top-level files only)
SS_SCAN_ROOTS = [DESKTOP, DOWNLOADS, DOCUMENTS, HOME]

sp = Spinner("Scanning for screenshots")

candidates = []
for root in SS_SCAN_ROOTS:
    if root.exists():
        for f in root.iterdir():
            if f.is_file() and is_screenshot(f.name):
                candidates.append(f)
# Recurse into known screenshot folders only
for old_dir in OLD_SS_DIRS:
    if old_dir.exists():
        for f in old_dir.rglob("*"):
            if f.is_file() and is_screenshot(f.name):
                candidates.append(f)
# Deduplicate by resolved path
seen = set()
deduped = []
for f in candidates:
    key = f.resolve()
    if key not in seen:
        seen.add(key)
        deduped.append(f)
candidates = deduped

ss_moved = ss_skip = 0
for i, f in enumerate(candidates):
    sp.update(pbar(i + 1, len(candidates)) + f"  {f.name[:38]}")
    # Allow files inside old SS dirs even though they'd otherwise be "protected"
    in_old = any(str(f).startswith(str(d)) for d in OLD_SS_DIRS)
    if is_protected(f) and not in_old:
        ss_skip += 1
        continue
    if move_dated(f, SCREENSHOTS_DIR):
        ss_moved += 1
    else:
        ss_skip += 1

for old_dir in OLD_SS_DIRS:
    if old_dir.exists() and not any(old_dir.rglob("*")):
        try: old_dir.rmdir()
        except: pass

sp.stop(f"{ss_moved} moved → ~/Pictures/Screenshots/YYYY/MM"
        + (f"  ({ss_skip} skipped)" if ss_skip else ""))
add("📸", "Screenshots consolidated",
    f"{ss_moved} files → ~/Pictures/Screenshots/YYYY/MM")


# ══════════════════════════════════════════════════════════════
# 2. PDFs  →  ~/Documents/PDFs/YYYY/MM
# ══════════════════════════════════════════════════════════════

header("📄  PDFs — Consolidate & Sort")

PDFS_DIR.mkdir(parents=True, exist_ok=True)
sp = Spinner("Scanning for PDFs")

pdf_cands = []
for root in [DESKTOP, DOWNLOADS, DOCUMENTS, HOME]:
    if root.exists():
        for f in root.iterdir():
            if f.is_file() and f.suffix.lower() == ".pdf":
                pdf_cands.append(f)

pdf_moved = pdf_skip = 0
for i, f in enumerate(pdf_cands):
    sp.update(pbar(i + 1, len(pdf_cands)) + f"  {f.name[:38]}")
    if move_dated(f, PDFS_DIR):
        pdf_moved += 1
    else:
        pdf_skip += 1

sp.stop(f"{pdf_moved} moved → ~/Documents/PDFs/YYYY/MM"
        + (f"  ({pdf_skip} skipped)" if pdf_skip else ""))
add("📄", "PDFs consolidated",
    f"{pdf_moved} files → ~/Documents/PDFs/YYYY/MM")


# ══════════════════════════════════════════════════════════════
# 3. DOCUMENTS  →  ~/Documents/Documents/YYYY/MM
# ══════════════════════════════════════════════════════════════

header("📝  Documents — Consolidate & Sort")

DOCS_DIR.mkdir(parents=True, exist_ok=True)
sp = Spinner("Scanning for documents")

doc_cands = []
for root in [DESKTOP, DOWNLOADS, DOCUMENTS, HOME]:
    if root.exists():
        for f in root.iterdir():
            if f.is_file() and f.suffix.lower() in DOC_EXTENSIONS:
                doc_cands.append(f)

doc_moved = doc_skip = 0
for i, f in enumerate(doc_cands):
    sp.update(pbar(i + 1, len(doc_cands)) + f"  {f.name[:38]}")
    if move_dated(f, DOCS_DIR):
        doc_moved += 1
    else:
        doc_skip += 1

sp.stop(f"{doc_moved} moved → ~/Documents/Documents/YYYY/MM"
        + (f"  ({doc_skip} skipped)" if doc_skip else ""))
add("📝", "Documents consolidated",
    f"{doc_moved} files → ~/Documents/Documents/YYYY/MM")


# ══════════════════════════════════════════════════════════════
# 4. INSTALLERS — collect stale ones into Downloads/Installers
# ══════════════════════════════════════════════════════════════

header("💿  Installers — Collect Stale Files")

INSTALLERS_DIR.mkdir(parents=True, exist_ok=True)
cutoff_inst = time.time() - (DAYS_OLD_INSTALLERS * 86400)
sp = Spinner("Scanning for installers")

inst_cands = []
for root in [DESKTOP, DOWNLOADS, HOME]:
    if root.exists():
        for f in root.iterdir():
            if f.is_file() and f.suffix.lower() in INSTALLER_EXTENSIONS:
                inst_cands.append(f)

inst_moved = inst_skip = 0
for i, f in enumerate(inst_cands):
    sp.update(pbar(i + 1, len(inst_cands)) + f"  {f.name[:38]}")
    if is_protected(f):
        inst_skip += 1
        continue
    try:
        last_touch = f.stat().st_atime
    except Exception:
        inst_skip += 1
        continue
    if last_touch < cutoff_inst:
        dest = unique_dest(INSTALLERS_DIR, f.name)
        try:
            shutil.move(str(f), str(dest))
            inst_moved += 1
        except Exception:
            inst_skip += 1
    else:
        inst_skip += 1   # not stale yet — leave it

sp.stop(f"{inst_moved} stale installer(s) → ~/Downloads/Installers"
        + (f"  ({inst_skip} recent/skipped)" if inst_skip else ""))
add("💿", "Stale installers collected",
    f"{inst_moved} .dmg/.pkg/.iso untouched {DAYS_OLD_INSTALLERS}+ days → ~/Downloads/Installers")


# ══════════════════════════════════════════════════════════════
# 5. DESKTOP — move remaining loose files to Desktop/Misc
# ══════════════════════════════════════════════════════════════

header("🖥️   Desktop — Tidy Loose Files")

MISC.mkdir(exist_ok=True)
SKIP_DESKTOP = {".DS_Store", "Misc", "Screenshots"}

desktop_files = [f for f in DESKTOP.iterdir()
                 if f.is_file()
                 and f.name not in SKIP_DESKTOP
                 and not f.name.startswith(".")]

sp = Spinner("Tidying Desktop")
misc_count = 0
for i, f in enumerate(desktop_files):
    sp.update(pbar(i + 1, len(desktop_files)) + f"  {f.name[:38]}")
    try:
        shutil.move(str(f), str(unique_dest(MISC, f.name)))
        misc_count += 1
    except Exception:
        pass

sp.stop(f"{misc_count} loose file(s) → Desktop/Misc")
add("🖥️", "Desktop tidied", f"{misc_count} files → ~/Desktop/Misc")

# .DS_Store — bounded rglob across known dirs only
ds_count = 0
for root in [DESKTOP, DOWNLOADS, DOCUMENTS, PICTURES]:
    for f in root.rglob(".DS_Store"):
        try:
            f.unlink()
            ds_count += 1
        except: pass
if ds_count:
    ok(f"Removed {ds_count} .DS_Store files")


# ══════════════════════════════════════════════════════════════
# 6. DOWNLOADS — archive files older than 30 days
# ══════════════════════════════════════════════════════════════

header("📥  Downloads — Archive Old Files")

ARCHIVE.mkdir(exist_ok=True)
cutoff_dl = time.time() - (DAYS_OLD_DOWNLOADS * 86400)

dl_files  = [f for f in DOWNLOADS.iterdir()
             if f.is_file() and not is_protected(f) and f.name != ".DS_Store"]
old_files = [f for f in dl_files if f.stat().st_mtime < cutoff_dl]

sp = Spinner("Archiving old downloads")
old_count = 0
for i, f in enumerate(old_files):
    sp.update(pbar(i + 1, len(old_files)) + f"  {f.name[:38]}")
    try:
        shutil.move(str(f), str(unique_dest(ARCHIVE, f.name)))
        old_count += 1
    except Exception:
        pass

sp.stop(f"{old_count} file(s) older than {DAYS_OLD_DOWNLOADS} days → Downloads/Archive")
add("📥", "Old downloads archived",
    f"{old_count} files → ~/Downloads/Archive")


# ══════════════════════════════════════════════════════════════
# 7. TRASH
# ══════════════════════════════════════════════════════════════

header("🗑️   Trash")

sp = Spinner("Emptying Trash")
trash_size = dir_size(HOME / ".Trash")
result     = run('osascript -e "tell app \\"Finder\\" to empty trash"')
if result.returncode == 0:
    sp.stop(f"~{human(trash_size)} freed")
    add("🗑️", "Trash emptied", f"{human(trash_size)} freed", trash_size)
else:
    sp.stop("Could not empty — use Cmd+Shift+Delete manually", success=False)
    add("🗑️", "Trash", "Skipped — empty manually")


# ══════════════════════════════════════════════════════════════
# 8. USER CACHES
# ══════════════════════════════════════════════════════════════

header("🧹  App Caches")

cache_dir   = HOME / "Library" / "Caches"
cache_items = list(cache_dir.iterdir()) if cache_dir.exists() else []
sp = Spinner("Clearing app caches")
freed = 0
for i, item in enumerate(cache_items):
    sp.update(pbar(i + 1, len(cache_items)) + f"  {item.name[:38]}")
    try:
        sz = dir_size(item)
        shutil.rmtree(str(item), ignore_errors=True)
        freed += sz
    except: pass

sp.stop(f"~{human(freed)} freed from ~/Library/Caches")
add("🧹", "App caches cleared", f"{human(freed)} freed", freed)


# ══════════════════════════════════════════════════════════════
# 9. LOG FILES
# ══════════════════════════════════════════════════════════════

header("🪵  Logs")

sp = Spinner("Clearing user logs")
log_dir  = HOME / "Library" / "Logs"
log_size = dir_size(log_dir)
shutil.rmtree(str(log_dir), ignore_errors=True)
log_dir.mkdir(exist_ok=True)
sp.stop(f"~{human(log_size)} freed from ~/Library/Logs")
add("🪵", "Log files removed", f"{human(log_size)} freed", log_size)


# ══════════════════════════════════════════════════════════════
# 10. SAVED APP STATE
# ══════════════════════════════════════════════════════════════

header("💾  Saved App State")

sp = Spinner("Clearing saved app states")
state_dir  = HOME / "Library" / "Saved Application State"
state_size = dir_size(state_dir)
for item in (list(state_dir.iterdir()) if state_dir.exists() else []):
    shutil.rmtree(str(item), ignore_errors=True)
sp.stop(f"~{human(state_size)} freed")
add("💾", "App saved states cleared", f"{human(state_size)} freed", state_size)


# ══════════════════════════════════════════════════════════════
# 11. QUICKLOOK CACHE
# ══════════════════════════════════════════════════════════════

header("👁️   QuickLook Cache")

sp = Spinner("Rebuilding QuickLook cache")
ql_dir  = HOME / "Library" / "Caches" / "com.apple.QuickLook.thumbnailcache"
ql_size = dir_size(ql_dir)
run("qlmanage -r cache")
shutil.rmtree(str(ql_dir), ignore_errors=True)
sp.stop(f"~{human(ql_size)} freed")
add("👁️", "QuickLook cache cleared", f"{human(ql_size)} freed", ql_size)


# ══════════════════════════════════════════════════════════════
# 12. BROWSER CACHES
# ══════════════════════════════════════════════════════════════

header("🌍  Browser Caches")

browsers = {
    "Safari": HOME / "Library/Caches/com.apple.Safari",
    "Chrome": HOME / "Library/Caches/Google/Chrome",
    "Arc":    HOME / "Library/Caches/company.thebrowser.Browser",
    "Brave":  HOME / "Library/Caches/BraveSoftware",
    "Edge":   HOME / "Library/Caches/Microsoft Edge",
}

sp = Spinner("Clearing browser caches")
browser_freed = 0
found = []
for i, (name, path) in enumerate(browsers.items()):
    sp.update(pbar(i + 1, len(browsers)) + f"  {name}")
    if path.exists():
        sz = dir_size(path)
        shutil.rmtree(str(path), ignore_errors=True)
        browser_freed += sz
        found.append(name)

ff_root = HOME / "Library/Caches/Firefox"
if ff_root.exists():
    sp.update("Firefox")
    for ff in ff_root.rglob("cache2"):
        browser_freed += dir_size(ff)
        shutil.rmtree(str(ff), ignore_errors=True)
    if "Firefox" not in found:
        found.append("Firefox")

sp.stop(f"{human(browser_freed)} freed — {', '.join(found)}" if found else "None found")
add("🌍", "Browser caches cleared",
    f"{human(browser_freed)} freed — {', '.join(found) or 'none'}", browser_freed)


# ══════════════════════════════════════════════════════════════
# 13. RECENT ITEMS
# ══════════════════════════════════════════════════════════════

header("📋  Recent Items")

sp = Spinner("Clearing recent items")
for domain in ["com.apple.recentitems", "com.apple.TextEdit", "com.apple.Preview"]:
    run(f"defaults delete {domain} 2>/dev/null")
sp.stop("Finder, TextEdit, Preview history wiped")
add("📋", "Recent items cleared", "Finder, TextEdit, Preview history wiped")


# ══════════════════════════════════════════════════════════════
# 14. IOS BACKUPS — keep 2 most recent
# ══════════════════════════════════════════════════════════════

header("🎵  iOS Backups")

backup_dir = HOME / "Library/Application Support/MobileSync/Backup"
sp = Spinner("Checking iOS backups")

if backup_dir.exists():
    backups = sorted(backup_dir.iterdir(),
                     key=lambda x: x.stat().st_mtime, reverse=True)
    if len(backups) > 2:
        removed = freed_b = 0
        for old in backups[2:]:
            sp.update(f"Removing {old.name[:40]}")
            sz = dir_size(old)
            shutil.rmtree(str(old), ignore_errors=True)
            freed_b += sz
            removed += 1
        sp.stop(f"Pruned {removed} backup(s), kept 2 most recent — {human(freed_b)} freed")
        add("🎵", "iOS backups pruned",
            f"{removed} old backup(s) removed, kept 2", freed_b)
    else:
        sp.stop(f"Only {len(backups)} backup(s) — nothing to prune")
        add("🎵", "iOS backups", f"Only {len(backups)} found — nothing pruned")
else:
    sp.stop("No iOS backups found")
    add("🎵", "iOS backups", "None found")


# ══════════════════════════════════════════════════════════════
# 15. HOMEBREW
# ══════════════════════════════════════════════════════════════

header("🍺  Homebrew")

if shutil.which("brew"):
    sp = Spinner("Updating and cleaning Homebrew")
    run("brew update --quiet")
    brew_cache = run("brew --cache").stdout.strip()
    before     = dir_size(brew_cache)
    run("brew cleanup --prune=7 -q")
    run("brew autoremove -q")
    freed_b    = max(0, before - dir_size(brew_cache))
    sp.stop(f"~{human(freed_b)} freed, packages updated")
    add("🍺", "Homebrew cleaned", f"{human(freed_b)} freed, packages updated", freed_b)
else:
    skip("Homebrew not installed")
    add("🍺", "Homebrew", "Not installed")


# ══════════════════════════════════════════════════════════════
# 16. NPM
# ══════════════════════════════════════════════════════════════

header("📦  npm")

if shutil.which("npm"):
    sp = Spinner("Clearing npm cache")
    npm_cache = run("npm config get cache").stdout.strip()
    npm_size  = dir_size(npm_cache)
    run("npm cache clean --force")
    sp.stop(f"~{human(npm_size)} freed")
    add("📦", "npm cache cleared", f"{human(npm_size)} freed", npm_size)
else:
    skip("npm not installed")


# ══════════════════════════════════════════════════════════════
# 17. PIP
# ══════════════════════════════════════════════════════════════

header("🐍  pip")

for pip in ["pip3", "pip"]:
    if shutil.which(pip):
        sp = Spinner("Clearing pip cache")
        pip_dir  = run(f"{pip} cache dir").stdout.strip()
        pip_size = dir_size(pip_dir)
        run(f"{pip} cache purge")
        sp.stop(f"~{human(pip_size)} freed")
        add("🐍", "pip cache cleared", f"{human(pip_size)} freed", pip_size)
        break
else:
    skip("pip not installed")


# ══════════════════════════════════════════════════════════════
# 18. XCODE  (--full only)
# ══════════════════════════════════════════════════════════════

header("📐  Xcode")

if FULL_MODE and shutil.which("xcodebuild"):
    sp = Spinner("Cleaning Xcode DerivedData and simulators")
    dd      = HOME / "Library/Developer/Xcode/DerivedData"
    dd_size = dir_size(dd)
    shutil.rmtree(str(dd), ignore_errors=True)
    dd.mkdir(exist_ok=True)
    run("xcrun simctl delete unavailable")
    sp.stop(f"DerivedData cleared ({human(dd_size)}) + simulators pruned")
    add("📐", "Xcode cleaned",
        f"DerivedData ({human(dd_size)}) + simulators pruned", dd_size)
elif not FULL_MODE:
    info("Xcode skipped — use --full to include")
    add("📐", "Xcode", "Skipped (use --full)")
else:
    skip("Xcode not installed")
    add("📐", "Xcode", "Not installed")


# ══════════════════════════════════════════════════════════════
# 19. DOCKER  (--full only)
# ══════════════════════════════════════════════════════════════

header("🐳  Docker")

if FULL_MODE and shutil.which("docker"):
    sp = Spinner("Pruning Docker")
    if run("docker info").returncode == 0:
        run("docker system prune -af --volumes")
        sp.stop("Unused images, containers, volumes removed")
        add("🐳", "Docker pruned", "All unused resources removed")
    else:
        sp.stop("Docker not running", success=False)
        add("🐳", "Docker", "Not running")
elif not FULL_MODE:
    info("Docker skipped — use --full to include")
    add("🐳", "Docker", "Skipped (use --full)")
else:
    skip("Docker not installed")


# ══════════════════════════════════════════════════════════════
# 20. DNS
# ══════════════════════════════════════════════════════════════

header("🌐  DNS")

sp = Spinner("Flushing DNS cache")
run("dscacheutil -flushcache")
run("killall -HUP mDNSResponder")
sp.stop("DNS cache flushed")
add("🌐", "DNS flushed", "dscacheutil + mDNSResponder")


# ══════════════════════════════════════════════════════════════
# 21. RESTART FINDER + DOCK
# ══════════════════════════════════════════════════════════════

header("🔄  Restarting UI")

sp = Spinner("Restarting Finder and Dock")
run("killall Finder")
run("killall Dock")
sp.stop("Finder and Dock restarted")
add("🔄", "Finder & Dock restarted", "UI refreshed")


# ══════════════════════════════════════════════════════════════
# 22. HTML REPORT
# ══════════════════════════════════════════════════════════════

header("📊  Report")

elapsed     = int(time.time() - start)
report_path = DESKTOP / f"Mac_Clean_Report_{datetime.now():%Y-%m-%d_%H%M}.html"
items_json  = json.dumps(report)

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Mac Clean Report — {datetime.now():%d %b %Y}</title>
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;700;800&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root{{--bg:#0a0a0f;--surface:#13131a;--surface2:#1c1c28;--border:#2a2a3a;--accent:#00e5a0;--text:#e8e8f0;--muted:#6b6b88}}
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
body{{background:var(--bg);color:var(--text);font-family:'Syne',sans-serif;min-height:100vh;padding:0 0 80px}}
.hero{{position:relative;padding:80px 40px 60px;text-align:center;overflow:hidden}}
.hero::before{{content:'';position:absolute;inset:0;background:radial-gradient(ellipse 60% 50% at 50% -10%,rgba(0,229,160,.18) 0%,transparent 70%);pointer-events:none}}
.eyebrow{{font-family:'DM Mono',monospace;font-size:.75rem;letter-spacing:.2em;text-transform:uppercase;color:var(--accent);margin-bottom:20px}}
h1{{font-size:clamp(2.8rem,8vw,6rem);font-weight:800;line-height:1;letter-spacing:-.03em;background:linear-gradient(135deg,#fff 30%,var(--accent) 100%);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:12px}}
.sub{{color:var(--muted);font-size:1rem;font-family:'DM Mono',monospace}}
.stats{{display:flex;max-width:700px;margin:40px auto 0;border:1px solid var(--border);border-radius:16px;overflow:hidden;background:var(--surface)}}
.stat{{flex:1;padding:28px 24px;text-align:center;border-right:1px solid var(--border)}}
.stat:last-child{{border-right:none}}
.stat-val{{font-size:2rem;font-weight:800;color:var(--accent)}}
.stat-label{{font-family:'DM Mono',monospace;font-size:.7rem;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);margin-top:6px}}
.wrap{{max-width:1000px;margin:64px auto 0;padding:0 40px}}
.section-label{{font-family:'DM Mono',monospace;font-size:.7rem;letter-spacing:.18em;text-transform:uppercase;color:var(--muted);margin-bottom:20px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:12px}}
.card{{background:var(--surface);border:1px solid var(--border);border-radius:14px;padding:22px 24px;display:flex;align-items:flex-start;gap:16px;animation:fadeUp .4s ease both}}
@keyframes fadeUp{{from{{opacity:0;transform:translateY(16px)}}to{{opacity:1;transform:translateY(0)}}}}
.emoji{{font-size:1.6rem;flex-shrink:0;width:42px;height:42px;display:flex;align-items:center;justify-content:center;background:var(--surface2);border-radius:10px;border:1px solid var(--border)}}
.card-body{{flex:1;min-width:0}}
.card-title{{font-weight:700;font-size:.95rem;margin-bottom:4px}}
.card-detail{{font-family:'DM Mono',monospace;font-size:.72rem;color:var(--muted);line-height:1.4}}
.card-freed{{font-family:'DM Mono',monospace;font-size:.75rem;color:var(--accent);margin-top:8px}}
footer{{text-align:center;margin-top:80px;font-family:'DM Mono',monospace;font-size:.72rem;color:var(--muted)}}
</style>
</head>
<body>
<div class="hero">
  <p class="eyebrow">🍎 Mac Deep Clean — {datetime.now():%A, %d %B %Y at %H:%M}</p>
  <h1>All<br>Clean.</h1>
  <p class="sub">Scrubbed, sorted &amp; organised.</p>
  <div class="stats">
    <div class="stat"><div class="stat-val">{human(total_freed)}</div><div class="stat-label">Freed</div></div>
    <div class="stat"><div class="stat-val">{len(report)}</div><div class="stat-label">Tasks</div></div>
    <div class="stat"><div class="stat-val">{elapsed}s</div><div class="stat-label">Duration</div></div>
  </div>
</div>
<div class="wrap">
  <p class="section-label">Detailed Results</p>
  <div class="grid" id="grid"></div>
</div>
<footer><p>Generated by mac_clean.py · {datetime.now():%Y-%m-%d %H:%M:%S}</p></footer>
<script>
const items={items_json};
const grid=document.getElementById('grid');
items.forEach((item,i)=>{{
  const c=document.createElement('div');
  c.className='card';
  c.style.animationDelay=(i*40)+'ms';
  c.innerHTML=`<div class="emoji">${{item.emoji}}</div>
    <div class="card-body">
      <div class="card-title">${{item.title}}</div>
      <div class="card-detail">${{item.detail}}</div>
      ${{item.freed?`<div class="card-freed">↓ ${{item.freed}} freed</div>`:''}}
    </div>`;
  grid.appendChild(c);
}});
</script>
</body>
</html>"""

report_path.write_text(html)
ok(f"Report saved → {report_path}")
run(f'open "{report_path}"')


# ══════════════════════════════════════════════════════════════
# DONE
# ══════════════════════════════════════════════════════════════

print(f"\n{BD}{B}")
print("  ╔════════════════════════════════════════════════╗")
print("  ║           ✅  DEEP CLEAN COMPLETE             ║")
print(f"  ║   💾  ~{human(total_freed):<40}║")
print(f"  ║   ⏱   Finished in {elapsed}s{' ' * (29 - len(str(elapsed)))}║")
print("  ║   📊  Report opened on Desktop               ║")
print("  ╚════════════════════════════════════════════════╝")
print(NC)
print(f"  {D}Files are organised here (local, not iCloud):{NC}")
print(f"  {D}  📸 Screenshots  →  ~/Downloads/Organised/Screenshots/YYYY/MM{NC}")
print(f"  {D}  📄 PDFs         →  ~/Downloads/Organised/PDFs/YYYY/MM{NC}")
print(f"  {D}  📝 Documents    →  ~/Downloads/Organised/Documents/YYYY/MM{NC}")
print(f"  {D}  💿 Installers   →  ~/Downloads/Organised/Installers{NC}")
print(f"  {D}  🗂  Desktop misc →  ~/Desktop/Misc{NC}")
print(f"  {D}  📥 Old downloads →  ~/Downloads/Archive{NC}\n")
print(f"  {D}Tip: run with --full to also clean Xcode & Docker{NC}\n")
