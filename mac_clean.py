#!/usr/bin/env python3
"""
mac_clean.py — Zero-intervention Mac deep clean.
Works from any shell (fish, zsh, bash). No sudo needed for most steps.
Usage: python3 mac_clean.py [--full]
"""

import os, sys, re, json, shutil, subprocess, threading, time
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

# All organised output lives in ~/Downloads/Organised.
# ~/Downloads is always local (Apple excludes it from iCloud Drive),
# so every move here is an instant os.rename — no byte-copying ever.
ORGANISED       = DOWNLOADS / "Organised"
SCREENSHOTS_DIR = ORGANISED / "Screenshots"
PDFS_DIR        = ORGANISED / "PDFs"
DOCS_DIR        = ORGANISED / "Documents"
INSTALLERS_DIR  = ORGANISED / "Installers"
MISC            = DESKTOP   / "Misc"
ARCHIVE         = DOWNLOADS / "Archive"

DAYS_OLD_DOWNLOADS  = 30
DAYS_OLD_INSTALLERS = 90
FULL_MODE           = "--full" in sys.argv

INSTALLER_EXTS = {".dmg", ".pkg", ".mpkg", ".iso"}
DOC_EXTS       = {".docx", ".doc", ".odt", ".rtf", ".pages"}

# ── Scan roots (shallow, top-level only) ──────────────────────
# We deliberately exclude ~/Pictures and ~/Documents from scanning.
# Files already inside those folders (especially iCloud-synced ones)
# are either already organised or would require slow iCloud downloads
# to move. We only sweep locations where loose files actually land.
SCAN_ROOTS = [DESKTOP, DOWNLOADS, HOME]


# ══════════════════════════════════════════════════════════════
# COLOURS
# ══════════════════════════════════════════════════════════════

G="\033[0;32m"; Y="\033[1;33m"; B="\033[0;36m"
D="\033[2m";    NC="\033[0m";   BD="\033[1m"


# ══════════════════════════════════════════════════════════════
# SPINNER  — live progress so you always know it hasn't hung
# ══════════════════════════════════════════════════════════════

class Spinner:
    F = ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"]
    def __init__(self, label):
        self.label = label; self.msg = ""
        self._stop = threading.Event(); self._lock = threading.Lock()
        self._t0   = time.time()
        self._t    = threading.Thread(target=self._run, daemon=True)
        self._t.start()

    def _run(self):
        i = 0
        while not self._stop.is_set():
            e = int(time.time() - self._t0)
            with self._lock: m = self.msg
            line = f"  {B}{self.F[i%len(self.F)]}{NC} {self.label}  {D}[{e}s]{NC}"
            if m: line += f"  {D}{m}{NC}"
            sys.stdout.write(f"\r{line:<120}"); sys.stdout.flush()
            i += 1; time.sleep(0.08)

    def update(self, msg):
        with self._lock: self.msg = msg

    def stop(self, result="", ok=True):
        self._stop.set(); self._t.join()
        e = int(time.time() - self._t0)
        icon = f"{G}✔{NC}" if ok else f"{Y}⚠{NC}"
        line = f"  {icon} {self.label}"
        if result: line += f"  {D}→ {result}{NC}"
        line += f"  {D}[{e}s]{NC}"
        sys.stdout.write(f"\r{line:<120}\n"); sys.stdout.flush()


def pbar(n, total, w=30):
    if not total: return ""
    f = int(w * n / total)
    return f"[{'█'*f}{'░'*(w-f)}] {n}/{total}"


# ══════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════

def header(t):
    print(f"\n{B}{BD}▸ {t}{NC}\n{D}  {'─'*52}{NC}")

def ok(m):   print(f"  {G}✔{NC} {m}")
def info(m): print(f"  {B}→{NC} {m}")
def warn(m): print(f"  {Y}⚠{NC} {m}")
def skip(m): print(f"  {D}– {m} (skipped){NC}")

def human(b):
    for u,s in [(1<<30,"GB"),(1<<20,"MB"),(1<<10,"KB")]:
        if b >= u: return f"{b/u:.1f} {s}"
    return f"{b} B"

def dir_size(p):
    t = 0
    try:
        for f in Path(p).rglob("*"):
            try: t += f.stat().st_size
            except: pass
    except: pass
    return t

def run(cmd, **kw):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, **kw)

DATE_PAT = re.compile(r"(\d{4})-(\d{2})-(\d{2})")

def file_date(f):
    m = DATE_PAT.search(f.name)
    if m: return m.group(1), m.group(2)
    try:    ts = f.stat().st_birthtime
    except: ts = f.stat().st_mtime
    dt = datetime.fromtimestamp(ts)
    return f"{dt.year:04d}", f"{dt.month:02d}"

def unique_dest(d, name):
    dst = d / name
    if not dst.exists(): return dst
    stem, suf = Path(name).stem, Path(name).suffix
    n = 2
    while True:
        c = d / f"{stem}_{n}{suf}"
        if not c.exists(): return c
        n += 1

# ── Cross-volume detection ─────────────────────────────────────
# Get the device ID of ~/Downloads once at startup.
# Any source file on a different device (iCloud APFS volume, external
# drive, etc.) is skipped — we never do slow cross-volume copies.
try:
    _LOCAL_DEV = os.stat(DOWNLOADS).st_dev
except Exception:
    _LOCAL_DEV = None

def same_volume(f: Path) -> bool:
    """True if f is on the same volume as ~/Downloads."""
    if _LOCAL_DEV is None: return True   # can't check — allow
    try:    return os.stat(f).st_dev == _LOCAL_DEV
    except: return False

def fast_move(src: Path, dest_root: Path) -> str:
    """
    Move src into dest_root/YYYY/MM/.
    Returns 'moved', 'skipped_icloud', or 'error'.
    Never does a cross-volume byte-copy — iCloud files are skipped.
    """
    if not same_volume(src):
        return "skipped_icloud"
    year, month = file_date(src)
    dest_dir = dest_root / year / month
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = unique_dest(dest_dir, src.name)
    try:
        os.rename(src, dest)   # instant — same volume guaranteed
        return "moved"
    except Exception:
        return "error"

def fast_move_flat(src: Path, dest_dir: Path) -> str:
    """Move src into dest_dir/ (no date subdirectory). Same volume check."""
    if not same_volume(src):
        return "skipped_icloud"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = unique_dest(dest_dir, src.name)
    try:
        os.rename(src, dest)
        return "moved"
    except Exception:
        return "error"


# ══════════════════════════════════════════════════════════════
# REPORT
# ══════════════════════════════════════════════════════════════

report = []; total_freed = 0

def add(emoji, title, detail, freed=0):
    global total_freed; total_freed += freed
    report.append({"emoji":emoji,"title":title,"detail":detail,
                   "freed": human(freed) if freed else ""})


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

# Make sure organised root exists on the local volume
ORGANISED.mkdir(parents=True, exist_ok=True)

if _LOCAL_DEV is not None:
    info(f"Local volume device ID: {_LOCAL_DEV} — iCloud files will be skipped, not copied")
print()


# ══════════════════════════════════════════════════════════════
# 1. SCREENSHOTS  →  ~/Downloads/Organised/Screenshots/YYYY/MM
#
# Only scans SCAN_ROOTS (Desktop, Downloads, ~/). Files already
# inside any folder named "Screenshots" are left alone — they're
# already organised. iCloud files are skipped, not downloaded.
# ══════════════════════════════════════════════════════════════

header("📸  Screenshots — Collect & Sort")

def is_screenshot(name):
    return (name.startswith("Screenshot ")
            or name.startswith("Screen Shot ")
            or name.startswith("Screenshot_"))

SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
sp = Spinner("Collecting screenshots")

# Gather candidates: loose files in scan roots only.
# Skip anything already inside a folder named "Screenshots".
candidates = []
for root in SCAN_ROOTS:
    if not root.exists(): continue
    for f in root.iterdir():
        if f.is_file() and is_screenshot(f.name):
            # Skip if already sitting in a Screenshots folder
            if "screenshots" not in str(f.parent).lower():
                candidates.append(f)

ss_moved = ss_icloud = ss_err = 0
for i, f in enumerate(candidates):
    sp.update(pbar(i+1, len(candidates)) + f"  {f.name[:35]}")
    r = fast_move(f, SCREENSHOTS_DIR)
    if   r == "moved":          ss_moved  += 1
    elif r == "skipped_icloud": ss_icloud += 1
    else:                       ss_err    += 1

parts = [f"{ss_moved} moved → ~/Downloads/Organised/Screenshots/YYYY/MM"]
if ss_icloud: parts.append(f"{ss_icloud} skipped (iCloud — already in Pictures)")
if ss_err:    parts.append(f"{ss_err} errors")
sp.stop("  ".join(parts))
add("📸","Screenshots sorted", "  ".join(parts))


# ══════════════════════════════════════════════════════════════
# 2. PDFs  →  ~/Downloads/Organised/PDFs/YYYY/MM
# ══════════════════════════════════════════════════════════════

header("📄  PDFs — Collect & Sort")

PDFS_DIR.mkdir(parents=True, exist_ok=True)
sp = Spinner("Collecting PDFs")

pdf_cands = []
for root in SCAN_ROOTS:
    if not root.exists(): continue
    for f in root.iterdir():
        if f.is_file() and f.suffix.lower() == ".pdf":
            pdf_cands.append(f)

pdf_moved = pdf_icloud = pdf_err = 0
for i, f in enumerate(pdf_cands):
    sp.update(pbar(i+1, len(pdf_cands)) + f"  {f.name[:35]}")
    r = fast_move(f, PDFS_DIR)
    if   r == "moved":          pdf_moved  += 1
    elif r == "skipped_icloud": pdf_icloud += 1
    else:                       pdf_err    += 1

parts = [f"{pdf_moved} moved → ~/Downloads/Organised/PDFs/YYYY/MM"]
if pdf_icloud: parts.append(f"{pdf_icloud} skipped (iCloud)")
sp.stop("  ".join(parts))
add("📄","PDFs sorted","  ".join(parts))


# ══════════════════════════════════════════════════════════════
# 3. DOCUMENTS  →  ~/Downloads/Organised/Documents/YYYY/MM
# ══════════════════════════════════════════════════════════════

header("📝  Documents — Collect & Sort")

DOCS_DIR.mkdir(parents=True, exist_ok=True)
sp = Spinner("Collecting documents")

doc_cands = []
for root in SCAN_ROOTS:
    if not root.exists(): continue
    for f in root.iterdir():
        if f.is_file() and f.suffix.lower() in DOC_EXTS:
            doc_cands.append(f)

doc_moved = doc_icloud = doc_err = 0
for i, f in enumerate(doc_cands):
    sp.update(pbar(i+1, len(doc_cands)) + f"  {f.name[:35]}")
    r = fast_move(f, DOCS_DIR)
    if   r == "moved":          doc_moved  += 1
    elif r == "skipped_icloud": doc_icloud += 1
    else:                       doc_err    += 1

parts = [f"{doc_moved} moved → ~/Downloads/Organised/Documents/YYYY/MM"]
if doc_icloud: parts.append(f"{doc_icloud} skipped (iCloud)")
sp.stop("  ".join(parts))
add("📝","Documents sorted","  ".join(parts))


# ══════════════════════════════════════════════════════════════
# 4. INSTALLERS — move stale ones to ~/Downloads/Organised/Installers
# ══════════════════════════════════════════════════════════════

header("💿  Installers — Collect Stale Files")

INSTALLERS_DIR.mkdir(parents=True, exist_ok=True)
cutoff = time.time() - (DAYS_OLD_INSTALLERS * 86400)
sp = Spinner("Collecting stale installers")

inst_cands = [f for root in SCAN_ROOTS if root.exists()
              for f in root.iterdir()
              if f.is_file() and f.suffix.lower() in INSTALLER_EXTS
              and str(f.parent) != str(INSTALLERS_DIR)]

inst_moved = inst_recent = inst_icloud = 0
for i, f in enumerate(inst_cands):
    sp.update(pbar(i+1, len(inst_cands)) + f"  {f.name[:35]}")
    try:    atime = f.stat().st_atime
    except: inst_icloud += 1; continue
    if atime >= cutoff:
        inst_recent += 1; continue
    r = fast_move_flat(f, INSTALLERS_DIR)
    if   r == "moved":          inst_moved  += 1
    elif r == "skipped_icloud": inst_icloud += 1

parts = [f"{inst_moved} stale installer(s) → ~/Downloads/Organised/Installers"]
if inst_recent:  parts.append(f"{inst_recent} recent (left in place)")
if inst_icloud:  parts.append(f"{inst_icloud} skipped (iCloud)")
sp.stop("  ".join(parts))
add("💿","Stale installers collected","  ".join(parts))


# ══════════════════════════════════════════════════════════════
# 5. DESKTOP — loose files to Desktop/Misc
# ══════════════════════════════════════════════════════════════

header("🖥️   Desktop — Tidy Loose Files")

MISC.mkdir(exist_ok=True)
SKIP = {".DS_Store","Misc","Screenshots","Organised"}
desktop_files = [f for f in DESKTOP.iterdir()
                 if f.is_file() and f.name not in SKIP
                 and not f.name.startswith(".")]

sp = Spinner("Tidying Desktop")
misc_n = misc_icloud = 0
for i, f in enumerate(desktop_files):
    sp.update(pbar(i+1, len(desktop_files)) + f"  {f.name[:35]}")
    r = fast_move_flat(f, MISC)
    if   r == "moved":          misc_n      += 1
    elif r == "skipped_icloud": misc_icloud += 1

parts = [f"{misc_n} file(s) → Desktop/Misc"]
if misc_icloud: parts.append(f"{misc_icloud} skipped (iCloud)")
sp.stop("  ".join(parts))
add("🖥️","Desktop tidied","  ".join(parts))

# .DS_Store — bounded sweep
ds = sum(1 for root in [DESKTOP, DOWNLOADS]
         for f in root.rglob(".DS_Store")
         if not (f.unlink() or False))
if ds: ok(f"Removed {ds} .DS_Store files")


# ══════════════════════════════════════════════════════════════
# 6. DOWNLOADS — archive files older than 30 days
# ══════════════════════════════════════════════════════════════

header("📥  Downloads — Archive Old Files")

ARCHIVE.mkdir(exist_ok=True)
cutoff_dl = time.time() - (DAYS_OLD_DOWNLOADS * 86400)

# Only files sitting directly in Downloads, not in subdirs
dl_files = [f for f in DOWNLOADS.iterdir()
            if f.is_file() and f.name != ".DS_Store"
            and f.stat().st_mtime < cutoff_dl]

sp = Spinner("Archiving old downloads")
arc_n = 0
for i, f in enumerate(dl_files):
    sp.update(pbar(i+1, len(dl_files)) + f"  {f.name[:35]}")
    r = fast_move_flat(f, ARCHIVE)
    if r == "moved": arc_n += 1

sp.stop(f"{arc_n} file(s) older than {DAYS_OLD_DOWNLOADS} days → Downloads/Archive")
add("📥","Old downloads archived",f"{arc_n} files → ~/Downloads/Archive")


# ══════════════════════════════════════════════════════════════
# 7. TRASH
# ══════════════════════════════════════════════════════════════

header("🗑️   Trash")

sp = Spinner("Emptying Trash")
trash_sz = dir_size(HOME / ".Trash")
r = run('osascript -e "tell app \\"Finder\\" to empty trash"')
if r.returncode == 0:
    sp.stop(f"~{human(trash_sz)} freed"); add("🗑️","Trash emptied",f"{human(trash_sz)} freed",trash_sz)
else:
    sp.stop("Could not empty — use Cmd+Shift+Delete manually", ok=False)
    add("🗑️","Trash","Skipped — empty manually")


# ══════════════════════════════════════════════════════════════
# 8. USER CACHES
# ══════════════════════════════════════════════════════════════

header("🧹  App Caches")

cache_dir   = HOME / "Library" / "Caches"
cache_items = list(cache_dir.iterdir()) if cache_dir.exists() else []
sp = Spinner("Clearing app caches")
freed = 0
for i, item in enumerate(cache_items):
    sp.update(pbar(i+1, len(cache_items)) + f"  {item.name[:35]}")
    try: sz = dir_size(item); shutil.rmtree(str(item), ignore_errors=True); freed += sz
    except: pass
sp.stop(f"~{human(freed)} freed"); add("🧹","App caches cleared",f"{human(freed)} freed",freed)


# ══════════════════════════════════════════════════════════════
# 9. LOGS
# ══════════════════════════════════════════════════════════════

header("🪵  Logs")

sp = Spinner("Clearing user logs")
log_dir = HOME / "Library" / "Logs"
sz = dir_size(log_dir)
shutil.rmtree(str(log_dir), ignore_errors=True); log_dir.mkdir(exist_ok=True)
sp.stop(f"~{human(sz)} freed"); add("🪵","Log files removed",f"{human(sz)} freed",sz)


# ══════════════════════════════════════════════════════════════
# 10. SAVED APP STATE
# ══════════════════════════════════════════════════════════════

header("💾  Saved App State")

sp = Spinner("Clearing saved app states")
state_dir = HOME / "Library" / "Saved Application State"
sz = dir_size(state_dir)
for item in (list(state_dir.iterdir()) if state_dir.exists() else []):
    shutil.rmtree(str(item), ignore_errors=True)
sp.stop(f"~{human(sz)} freed"); add("💾","Saved states cleared",f"{human(sz)} freed",sz)


# ══════════════════════════════════════════════════════════════
# 11. QUICKLOOK
# ══════════════════════════════════════════════════════════════

header("👁️   QuickLook Cache")

sp = Spinner("Rebuilding QuickLook cache")
ql = HOME / "Library" / "Caches" / "com.apple.QuickLook.thumbnailcache"
sz = dir_size(ql); run("qlmanage -r cache"); shutil.rmtree(str(ql), ignore_errors=True)
sp.stop(f"~{human(sz)} freed"); add("👁️","QuickLook cleared",f"{human(sz)} freed",sz)


# ══════════════════════════════════════════════════════════════
# 12. BROWSER CACHES
# ══════════════════════════════════════════════════════════════

header("🌍  Browser Caches")

browsers = {
    "Safari": HOME/"Library/Caches/com.apple.Safari",
    "Chrome": HOME/"Library/Caches/Google/Chrome",
    "Arc":    HOME/"Library/Caches/company.thebrowser.Browser",
    "Brave":  HOME/"Library/Caches/BraveSoftware",
    "Edge":   HOME/"Library/Caches/Microsoft Edge",
}
sp = Spinner("Clearing browser caches")
b_freed = 0; found = []
for i,(name,path) in enumerate(browsers.items()):
    sp.update(pbar(i+1, len(browsers)) + f"  {name}")
    if path.exists():
        b_freed += dir_size(path); shutil.rmtree(str(path), ignore_errors=True); found.append(name)
ff = HOME/"Library/Caches/Firefox"
if ff.exists():
    sp.update("Firefox")
    for c in ff.rglob("cache2"): b_freed += dir_size(c); shutil.rmtree(str(c), ignore_errors=True)
    if "Firefox" not in found: found.append("Firefox")
sp.stop(f"{human(b_freed)} freed — {', '.join(found) or 'none'}")
add("🌍","Browser caches cleared",f"{human(b_freed)} freed",b_freed)


# ══════════════════════════════════════════════════════════════
# 13. RECENT ITEMS
# ══════════════════════════════════════════════════════════════

header("📋  Recent Items")

sp = Spinner("Clearing recent items")
for d in ["com.apple.recentitems","com.apple.TextEdit","com.apple.Preview"]:
    run(f"defaults delete {d} 2>/dev/null")
sp.stop("Finder, TextEdit, Preview history wiped")
add("📋","Recent items cleared","Finder, TextEdit, Preview")


# ══════════════════════════════════════════════════════════════
# 14. IOS BACKUPS
# ══════════════════════════════════════════════════════════════

header("🎵  iOS Backups")

bk_dir = HOME/"Library/Application Support/MobileSync/Backup"
sp = Spinner("Checking iOS backups")
if bk_dir.exists():
    bks = sorted(bk_dir.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True)
    if len(bks) > 2:
        rm = 0; freed_b = 0
        for old in bks[2:]:
            sp.update(f"Removing {old.name[:40]}")
            freed_b += dir_size(old); shutil.rmtree(str(old), ignore_errors=True); rm += 1
        sp.stop(f"Pruned {rm}, kept 2 most recent — {human(freed_b)} freed")
        add("🎵","iOS backups pruned",f"{rm} removed, kept 2",freed_b)
    else:
        sp.stop(f"Only {len(bks)} backup(s) — nothing to prune")
        add("🎵","iOS backups",f"Only {len(bks)} found")
else:
    sp.stop("None found"); add("🎵","iOS backups","None found")


# ══════════════════════════════════════════════════════════════
# 15. HOMEBREW
# ══════════════════════════════════════════════════════════════

header("🍺  Homebrew")

if shutil.which("brew"):
    sp = Spinner("Updating and cleaning Homebrew")
    run("brew update --quiet")
    bc = run("brew --cache").stdout.strip(); before = dir_size(bc)
    run("brew cleanup --prune=7 -q"); run("brew autoremove -q")
    freed_b = max(0, before - dir_size(bc))
    sp.stop(f"~{human(freed_b)} freed"); add("🍺","Homebrew cleaned",f"{human(freed_b)} freed",freed_b)
else:
    skip("Homebrew not installed"); add("🍺","Homebrew","Not installed")


# ══════════════════════════════════════════════════════════════
# 16. NPM
# ══════════════════════════════════════════════════════════════

header("📦  npm")

if shutil.which("npm"):
    sp = Spinner("Clearing npm cache")
    nc = run("npm config get cache").stdout.strip(); sz = dir_size(nc)
    run("npm cache clean --force")
    sp.stop(f"~{human(sz)} freed"); add("📦","npm cache cleared",f"{human(sz)} freed",sz)
else:
    skip("npm not installed")


# ══════════════════════════════════════════════════════════════
# 17. PIP
# ══════════════════════════════════════════════════════════════

header("🐍  pip")

for pip in ["pip3","pip"]:
    if shutil.which(pip):
        sp = Spinner("Clearing pip cache")
        pd = run(f"{pip} cache dir").stdout.strip(); sz = dir_size(pd)
        run(f"{pip} cache purge")
        sp.stop(f"~{human(sz)} freed"); add("🐍","pip cache cleared",f"{human(sz)} freed",sz)
        break
else:
    skip("pip not installed")


# ══════════════════════════════════════════════════════════════
# 18. XCODE  (--full only)
# ══════════════════════════════════════════════════════════════

header("📐  Xcode")

if FULL_MODE and shutil.which("xcodebuild"):
    sp = Spinner("Cleaning Xcode")
    dd = HOME/"Library/Developer/Xcode/DerivedData"; sz = dir_size(dd)
    shutil.rmtree(str(dd), ignore_errors=True); dd.mkdir(exist_ok=True)
    run("xcrun simctl delete unavailable")
    sp.stop(f"DerivedData ({human(sz)}) + simulators pruned"); add("📐","Xcode cleaned",f"{human(sz)} freed",sz)
elif not FULL_MODE:
    info("Xcode skipped — use --full to include"); add("📐","Xcode","Skipped (use --full)")
else:
    skip("Xcode not installed"); add("📐","Xcode","Not installed")


# ══════════════════════════════════════════════════════════════
# 19. DOCKER  (--full only)
# ══════════════════════════════════════════════════════════════

header("🐳  Docker")

if FULL_MODE and shutil.which("docker"):
    sp = Spinner("Pruning Docker")
    if run("docker info").returncode == 0:
        run("docker system prune -af --volumes")
        sp.stop("Unused images, containers, volumes removed"); add("🐳","Docker pruned","All unused removed")
    else:
        sp.stop("Docker not running", ok=False); add("🐳","Docker","Not running")
elif not FULL_MODE:
    info("Docker skipped — use --full to include"); add("🐳","Docker","Skipped (use --full)")
else:
    skip("Docker not installed")


# ══════════════════════════════════════════════════════════════
# 20. DNS
# ══════════════════════════════════════════════════════════════

header("🌐  DNS")

sp = Spinner("Flushing DNS")
run("dscacheutil -flushcache"); run("killall -HUP mDNSResponder")
sp.stop("DNS cache flushed"); add("🌐","DNS flushed","dscacheutil + mDNSResponder")


# ══════════════════════════════════════════════════════════════
# 21. RESTART FINDER + DOCK
# ══════════════════════════════════════════════════════════════

header("🔄  Restarting UI")

sp = Spinner("Restarting Finder and Dock")
run("killall Finder"); run("killall Dock")
sp.stop("Done"); add("🔄","Finder & Dock restarted","UI refreshed")


# ══════════════════════════════════════════════════════════════
# 22. HTML REPORT
# ══════════════════════════════════════════════════════════════

header("📊  Report")

elapsed     = int(time.time() - start)
report_path = DESKTOP / f"Mac_Clean_Report_{datetime.now():%Y-%m-%d_%H%M}.html"
items_json  = json.dumps(report)

html = f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Mac Clean — {datetime.now():%d %b %Y}</title>
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;700;800&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root{{--bg:#0a0a0f;--s:#13131a;--s2:#1c1c28;--b:#2a2a3a;--a:#00e5a0;--t:#e8e8f0;--m:#6b6b88}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:var(--bg);color:var(--t);font-family:'Syne',sans-serif;min-height:100vh;padding:0 0 80px}}
.hero{{position:relative;padding:80px 40px 60px;text-align:center;overflow:hidden}}
.hero::before{{content:'';position:absolute;inset:0;background:radial-gradient(ellipse 60% 50% at 50% -10%,rgba(0,229,160,.18),transparent 70%);pointer-events:none}}
.ey{{font-family:'DM Mono',monospace;font-size:.75rem;letter-spacing:.2em;text-transform:uppercase;color:var(--a);margin-bottom:20px}}
h1{{font-size:clamp(2.8rem,8vw,6rem);font-weight:800;line-height:1;letter-spacing:-.03em;background:linear-gradient(135deg,#fff 30%,var(--a) 100%);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:12px}}
.sub{{color:var(--m);font-size:1rem;font-family:'DM Mono',monospace}}
.stats{{display:flex;max-width:700px;margin:40px auto 0;border:1px solid var(--b);border-radius:16px;overflow:hidden;background:var(--s)}}
.stat{{flex:1;padding:28px 24px;text-align:center;border-right:1px solid var(--b)}}.stat:last-child{{border-right:none}}
.sv{{font-size:2rem;font-weight:800;color:var(--a)}}.sl{{font-family:'DM Mono',monospace;font-size:.7rem;letter-spacing:.12em;text-transform:uppercase;color:var(--m);margin-top:6px}}
.wrap{{max-width:1000px;margin:64px auto 0;padding:0 40px}}
.sl2{{font-family:'DM Mono',monospace;font-size:.7rem;letter-spacing:.18em;text-transform:uppercase;color:var(--m);margin-bottom:20px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:12px}}
.card{{background:var(--s);border:1px solid var(--b);border-radius:14px;padding:22px 24px;display:flex;align-items:flex-start;gap:16px;animation:up .4s ease both}}
@keyframes up{{from{{opacity:0;transform:translateY(16px)}}to{{opacity:1;transform:none}}}}
.em{{font-size:1.6rem;flex-shrink:0;width:42px;height:42px;display:flex;align-items:center;justify-content:center;background:var(--s2);border-radius:10px;border:1px solid var(--b)}}
.cb{{flex:1;min-width:0}}.ct{{font-weight:700;font-size:.95rem;margin-bottom:4px}}
.cd{{font-family:'DM Mono',monospace;font-size:.72rem;color:var(--m);line-height:1.4}}
.cf{{font-family:'DM Mono',monospace;font-size:.75rem;color:var(--a);margin-top:8px}}
footer{{text-align:center;margin-top:80px;font-family:'DM Mono',monospace;font-size:.72rem;color:var(--m)}}
</style></head><body>
<div class="hero">
  <p class="ey">🍎 Mac Deep Clean — {datetime.now():%A, %d %B %Y at %H:%M}</p>
  <h1>All<br>Clean.</h1>
  <p class="sub">Scrubbed, sorted &amp; organised.</p>
  <div class="stats">
    <div class="stat"><div class="sv">{human(total_freed)}</div><div class="sl">Freed</div></div>
    <div class="stat"><div class="sv">{len(report)}</div><div class="sl">Tasks</div></div>
    <div class="stat"><div class="sv">{elapsed}s</div><div class="sl">Duration</div></div>
  </div>
</div>
<div class="wrap"><p class="sl2">Detailed Results</p><div class="grid" id="g"></div></div>
<footer><p>Generated by mac_clean.py · {datetime.now():%Y-%m-%d %H:%M:%S}</p></footer>
<script>
const items={items_json},g=document.getElementById('g');
items.forEach((x,i)=>{{
  const c=document.createElement('div');c.className='card';c.style.animationDelay=i*40+'ms';
  c.innerHTML=`<div class="em">${{x.emoji}}</div><div class="cb"><div class="ct">${{x.title}}</div>
    <div class="cd">${{x.detail}}</div>${{x.freed?`<div class="cf">↓ ${{x.freed}} freed</div>`:''}}
  </div>`;g.appendChild(c);
}});
</script></body></html>"""

report_path.write_text(html)
ok(f"Report → {report_path}")
run(f'open "{report_path}"')


# ══════════════════════════════════════════════════════════════
# DONE
# ══════════════════════════════════════════════════════════════

print(f"\n{BD}{B}")
print("  ╔════════════════════════════════════════════════╗")
print("  ║           ✅  DEEP CLEAN COMPLETE             ║")
print(f"  ║   💾  ~{human(total_freed):<40}║")
print(f"  ║   ⏱   Finished in {elapsed}s{' '*(29-len(str(elapsed)))}║")
print("  ║   📊  Report opened on Desktop               ║")
print("  ╚════════════════════════════════════════════════╝")
print(NC)
print(f"  {D}All organised files → ~/Downloads/Organised/ (local, instant){NC}")
print(f"  {D}  📸  Screenshots/YYYY/MM{NC}")
print(f"  {D}  📄  PDFs/YYYY/MM{NC}")
print(f"  {D}  📝  Documents/YYYY/MM{NC}")
print(f"  {D}  💿  Installers/{NC}")
print(f"  {D}  🗂   ~/Desktop/Misc  —  📥  ~/Downloads/Archive{NC}")
print(f"\n  {D}iCloud files were skipped — they are already organised{NC}")
print(f"\n  {D}Tip: --full also cleans Xcode & Docker{NC}\n")
