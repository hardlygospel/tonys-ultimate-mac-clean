#!/usr/bin/env python3

"""
mac_clean.py — Zero-intervention Mac deep clean.
Works from any shell (fish, zsh, bash). No sudo needed for most steps.
Usage: python3 mac_clean.py [--full]
"""

import os
import sys
import re
import shutil
import subprocess
import time
from pathlib import Path
from datetime import datetime, timedelta

# ── Config ────────────────────────────────────────────────────
HOME      = Path.home()
DESKTOP   = HOME / "Desktop"
DOWNLOADS = HOME / "Downloads"
PICTURES  = HOME / "Pictures"
DOCUMENTS = HOME / "Documents"

# Screenshots now consolidate to ~/Pictures/Screenshots (single source of truth)
SCREENSHOTS = PICTURES / "Screenshots"

MISC      = DESKTOP / "Misc"
ARCHIVE   = DOWNLOADS / "Archive"
DAYS_OLD  = 30
FULL_MODE = "--full" in sys.argv

# ── Colours ───────────────────────────────────────────────────
G  = "\033[0;32m"   # green
Y  = "\033[1;33m"   # yellow
B  = "\033[0;36m"   # cyan
D  = "\033[2m"      # dim
NC = "\033[0m"      # reset
BD = "\033[1m"

def header(title):
    print(f"\n{B}{BD}▸ {title}{NC}")
    print(f"{D} {'─'*41}{NC}")

def ok(msg):   print(f"  {G}✔{NC} {msg}")
def info(msg): print(f"  {B}→{NC} {msg}")
def warn(msg): print(f"  {Y}⚠{NC} {msg}")
def skip(msg): print(f"  {D}– {msg} (skipped){NC}")

def human(b):
    if b >= 1_073_741_824: return f"{b/1_073_741_824:.1f} GB"
    if b >= 1_048_576:     return f"{b/1_048_576:.1f} MB"
    if b >= 1_024:         return f"{b/1_024:.1f} KB"
    return f"{b} B"

def dir_size(p):
    total = 0
    try:
        for f in Path(p).rglob("*"):
            try: total += f.stat().st_size
            except: pass
    except: pass
    return total

def run(cmd, **kw):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, **kw)

report      = []
total_freed = 0

def add(emoji, title, detail, freed=0):
    global total_freed
    total_freed += freed
    report.append({"emoji": emoji, "title": title, "detail": detail,
                   "freed": human(freed) if freed > 0 else ""})

start = time.time()
print(f"\n{BD}{B}")
print("  ╔═══════════════════════════════════════╗")
print("  ║         🍎 MAC DEEP CLEAN             ║")
print(f"  ║   {datetime.now():%d %b %Y %H:%M}                 ║")
print("  ╚═══════════════════════════════════════╝")
print(NC)


# ══════════════════════════════════════════════════════════════
# 1. SCREENSHOTS — consolidate from everywhere → ~/Pictures/Screenshots/YYYY/MM
# ══════════════════════════════════════════════════════════════

header("📸 Screenshots — Consolidate & Sort")

DATE_PATTERN = re.compile(r"(\d{4})-(\d{2})-(\d{2})")

def is_screenshot(name: str) -> bool:
    """Return True if the filename looks like a macOS screenshot."""
    return (
        name.startswith("Screenshot ")
        or name.startswith("Screen Shot ")
        or name.startswith("Screenshot_")
    )

def get_date_for_file(f: Path):
    """
    Try to extract YYYY, MM from the filename first.
    Fall back to the file's creation date (st_birthtime on macOS).
    Returns (year_str, month_str).
    """
    m = DATE_PATTERN.search(f.name)
    if m:
        return m.group(1), m.group(2)
    try:
        ts = f.stat().st_birthtime          # macOS creation time
    except AttributeError:
        ts = f.stat().st_mtime              # Linux fallback
    dt = datetime.fromtimestamp(ts)
    return f"{dt.year:04d}", f"{dt.month:02d}"

def unique_dest(dest_dir: Path, name: str) -> Path:
    """Return a path that doesn't already exist, appending _2, _3 … as needed."""
    dest = dest_dir / name
    if not dest.exists():
        return dest
    stem, suffix = Path(name).stem, Path(name).suffix
    counter = 2
    while True:
        candidate = dest_dir / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1

# Locations to search — includes any existing Screenshots folders
SEARCH_ROOTS = [
    DESKTOP,
    DOWNLOADS,
    DOCUMENTS,
    PICTURES,
    HOME,                           # files dropped directly in home dir
]

# Also catch any Screenshots subfolders that already exist (e.g. Desktop/Screenshots)
existing_screenshot_dirs = [
    DESKTOP / "Screenshots",
    PICTURES / "Screenshots",       # our target — walk it too to normalise structure
    HOME / "Screenshots",
]

moved   = 0
skipped = 0

SCREENSHOTS.mkdir(parents=True, exist_ok=True)

def consolidate_from(source_dir: Path, recursive: bool = False):
    """Move all screenshots found in source_dir into ~/Pictures/Screenshots/YYYY/MM."""
    global moved, skipped
    if not source_dir.exists():
        return
    iterator = source_dir.rglob("*") if recursive else source_dir.iterdir()
    for f in list(iterator):
        if not f.is_file():
            continue
        # Skip anything already inside our target tree
        try:
            f.relative_to(SCREENSHOTS)
            continue
        except ValueError:
            pass
        if not is_screenshot(f.name):
            continue
        year, month = get_date_for_file(f)
        dest_dir = SCREENSHOTS / year / month
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = unique_dest(dest_dir, f.name)
        try:
            shutil.move(str(f), str(dest))
            moved += 1
        except Exception as e:
            warn(f"Could not move {f.name}: {e}")
            skipped += 1

# 1a. Sweep top-level of common folders (non-recursive to avoid thrashing large trees)
for root in SEARCH_ROOTS:
    consolidate_from(root, recursive=False)

# 1b. Recurse into any pre-existing Screenshots folders to normalise their structure
for sdir in existing_screenshot_dirs:
    if sdir.exists() and sdir != SCREENSHOTS:
        consolidate_from(sdir, recursive=True)
        # If the old Screenshots folder is now empty, remove it
        try:
            remaining = list(sdir.rglob("*"))
            if not remaining:
                sdir.rmdir()
                info(f"Removed empty folder: {sdir}")
        except Exception:
            pass

# Report
if moved:
    ok(f"{moved} screenshot(s) consolidated → {SCREENSHOTS}")
    if skipped:
        warn(f"{skipped} file(s) could not be moved — check permissions")
    add("📸", "Screenshots consolidated", f"{moved} files → ~/Pictures/Screenshots/YYYY/MM")
else:
    info("No screenshots found to move.")
    add("📸", "Screenshots", "Nothing to consolidate")


# ══════════════════════════════════════════════════════════════
# 2. DESKTOP — move loose files to Desktop/Misc
# ══════════════════════════════════════════════════════════════

header("🖥️  Desktop")

misc_count  = 0
skip_names  = {".DS_Store", "Misc", "Screenshots"}

for f in list(DESKTOP.iterdir()):
    if f.name in skip_names or f.name.startswith("."):
        continue
    if f.is_file():
        MISC.mkdir(exist_ok=True)
        try:
            shutil.move(str(f), str(MISC / f.name))
            misc_count += 1
        except Exception as e:
            warn(f"Could not move {f.name}: {e}")

if misc_count:
    ok(f"{misc_count} loose file(s) → Desktop/Misc")
    add("🖥️", "Desktop tidied", f"{misc_count} files moved to ~/Desktop/Misc")
else:
    info("Desktop already clean.")
    add("🖥️", "Desktop", "Already tidy")

# Remove .DS_Store files
ds_count = 0
for f in HOME.rglob(".DS_Store"):
    try:
        f.unlink()
        ds_count += 1
    except: pass
if ds_count:
    ok(f"Deleted {ds_count} .DS_Store files")


# ══════════════════════════════════════════════════════════════
# 3. DOWNLOADS — archive files older than 30 days
# ══════════════════════════════════════════════════════════════

header("📥 Downloads")

cutoff    = time.time() - (DAYS_OLD * 86400)
old_count = 0

for f in list(DOWNLOADS.iterdir()):
    if f.is_file() and f.name != ".DS_Store":
        try:
            if f.stat().st_mtime < cutoff:
                ARCHIVE.mkdir(exist_ok=True)
                shutil.move(str(f), str(ARCHIVE / f.name))
                old_count += 1
        except Exception as e:
            warn(f"Could not archive {f.name}: {e}")

if old_count:
    ok(f"{old_count} file(s) older than {DAYS_OLD} days → Downloads/Archive")
    add("📥", "Old downloads archived", f"{old_count} files moved to ~/Downloads/Archive")
else:
    info("No old downloads to archive.")
    add("📥", "Downloads", f"Nothing older than {DAYS_OLD} days")


# ══════════════════════════════════════════════════════════════
# 4. TRASH
# ══════════════════════════════════════════════════════════════

header("🗑️  Trash")

trash      = HOME / ".Trash"
trash_size = dir_size(trash)
result     = run('osascript -e "tell app \\"Finder\\" to empty trash"')

if result.returncode == 0:
    ok(f"Trash emptied (freed ~{human(trash_size)})")
    add("🗑️", "Trash emptied", f"{human(trash_size)} freed", trash_size)
else:
    warn("Could not empty Trash — do it manually with Cmd+Shift+Delete")
    add("🗑️", "Trash", "Skipped — empty manually")


# ══════════════════════════════════════════════════════════════
# 5. USER CACHES
# ══════════════════════════════════════════════════════════════

header("🧹 App Caches")

cache_dir  = HOME / "Library" / "Caches"
freed      = 0

for item in list(cache_dir.iterdir()):
    try:
        sz = dir_size(item)
        shutil.rmtree(str(item), ignore_errors=True)
        freed += sz
    except: pass

ok(f"App caches cleared (~{human(freed)} freed)")
add("🧹", "App caches cleared", f"{human(freed)} freed from ~/Library/Caches", freed)


# ══════════════════════════════════════════════════════════════
# 6. LOG FILES
# ══════════════════════════════════════════════════════════════

header("🪵 Logs")

log_dir  = HOME / "Library" / "Logs"
log_size = dir_size(log_dir)
shutil.rmtree(str(log_dir), ignore_errors=True)
log_dir.mkdir(exist_ok=True)

ok(f"User logs cleared (~{human(log_size)} freed)")
add("🪵", "Log files removed", f"{human(log_size)} freed from ~/Library/Logs", log_size)


# ══════════════════════════════════════════════════════════════
# 7. SAVED APP STATE
# ══════════════════════════════════════════════════════════════

header("💾 Saved App State")

state_dir  = HOME / "Library" / "Saved Application State"
state_size = dir_size(state_dir)

for item in (list(state_dir.iterdir()) if state_dir.exists() else []):
    shutil.rmtree(str(item), ignore_errors=True)

ok(f"App saved states cleared (~{human(state_size)} freed)")
add("💾", "App saved states cleared", f"{human(state_size)} freed", state_size)


# ══════════════════════════════════════════════════════════════
# 8. QUICKLOOK CACHE
# ══════════════════════════════════════════════════════════════

header("👁️  QuickLook Cache")

ql_dir  = HOME / "Library" / "Caches" / "com.apple.QuickLook.thumbnailcache"
ql_size = dir_size(ql_dir)
run("qlmanage -r cache")
shutil.rmtree(str(ql_dir), ignore_errors=True)

ok(f"QuickLook cache cleared (~{human(ql_size)} freed)")
add("👁️", "QuickLook cache cleared", f"{human(ql_size)} freed", ql_size)


# ══════════════════════════════════════════════════════════════
# 9. BROWSER CACHES
# ══════════════════════════════════════════════════════════════

header("🌍 Browser Caches")

browsers = {
    "Safari":  HOME / "Library/Caches/com.apple.Safari",
    "Chrome":  HOME / "Library/Caches/Google/Chrome",
    "Arc":     HOME / "Library/Caches/company.thebrowser.Browser",
    "Brave":   HOME / "Library/Caches/BraveSoftware",
    "Edge":    HOME / "Library/Caches/Microsoft Edge",
}

browser_freed = 0
found         = []

for name, path in browsers.items():
    if path.exists():
        sz = dir_size(path)
        shutil.rmtree(str(path), ignore_errors=True)
        browser_freed += sz
        found.append(name)

# Firefox (nested path)
ff_root = HOME / "Library/Caches/Firefox"
if ff_root.exists():
    for ff in ff_root.rglob("cache2"):
        sz = dir_size(ff)
        shutil.rmtree(str(ff), ignore_errors=True)
        browser_freed += sz
    if "Firefox" not in found:
        found.append("Firefox")

if found:
    ok(f"Browser caches cleared — {human(browser_freed)} freed ({', '.join(found)})")
    add("🌍", "Browser caches cleared", f"{human(browser_freed)} freed — {', '.join(found)}", browser_freed)
else:
    info("No browser caches found.")
    add("🌍", "Browser caches", "None found")


# ══════════════════════════════════════════════════════════════
# 10. RECENT ITEMS
# ══════════════════════════════════════════════════════════════

header("📝 Recent Items")

for domain in ["com.apple.recentitems", "com.apple.TextEdit", "com.apple.Preview"]:
    run(f"defaults delete {domain} 2>/dev/null")

ok("Recent items cleared (Finder, TextEdit, Preview)")
add("📝", "Recent items cleared", "Finder, TextEdit, Preview history wiped")


# ══════════════════════════════════════════════════════════════
# 11. IOS BACKUPS — keep 2 most recent
# ══════════════════════════════════════════════════════════════

header("🎵 iOS Backups")

backup_dir = HOME / "Library/Application Support/MobileSync/Backup"

if backup_dir.exists():
    backups = sorted(backup_dir.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True)
    if len(backups) > 2:
        removed  = 0
        freed_b  = 0
        for old in backups[2:]:
            sz = dir_size(old)
            shutil.rmtree(str(old), ignore_errors=True)
            freed_b += sz
            removed += 1
        ok(f"Pruned {removed} old iOS backup(s), kept 2 most recent (~{human(freed_b)} freed)")
        add("🎵", "iOS backups pruned", f"{removed} old backup(s) removed, kept 2", freed_b)
    else:
        info(f"Only {len(backups)} backup(s) — keeping all.")
        add("🎵", "iOS backups", f"Only {len(backups)} found — nothing pruned")
else:
    skip("No iOS backups found")
    add("🎵", "iOS backups", "None found")


# ══════════════════════════════════════════════════════════════
# 12. HOMEBREW
# ══════════════════════════════════════════════════════════════

header("🍺 Homebrew")

if shutil.which("brew"):
    info("Updating Homebrew...")
    run("brew update --quiet")
    brew_cache = run("brew --cache").stdout.strip()
    before     = dir_size(brew_cache)
    run("brew cleanup --prune=7 -q")
    run("brew autoremove -q")
    after    = dir_size(brew_cache)
    freed_b  = max(0, before - after)
    ok(f"Homebrew cleaned (~{human(freed_b)} freed)")
    add("🍺", "Homebrew cleaned", f"{human(freed_b)} freed, packages updated", freed_b)
else:
    skip("Homebrew not installed")
    add("🍺", "Homebrew", "Not installed")


# ══════════════════════════════════════════════════════════════
# 13. NPM
# ══════════════════════════════════════════════════════════════

header("📦 npm")

if shutil.which("npm"):
    npm_cache = run("npm config get cache").stdout.strip()
    npm_size  = dir_size(npm_cache)
    run("npm cache clean --force")
    ok(f"npm cache cleared (~{human(npm_size)} freed)")
    add("📦", "npm cache cleared", f"{human(npm_size)} freed", npm_size)
else:
    skip("npm not installed")


# ══════════════════════════════════════════════════════════════
# 14. PIP
# ══════════════════════════════════════════════════════════════

header("🐍 pip")

for pip in ["pip3", "pip"]:
    if shutil.which(pip):
        pip_dir  = run(f"{pip} cache dir").stdout.strip()
        pip_size = dir_size(pip_dir)
        run(f"{pip} cache purge")
        ok(f"pip cache cleared (~{human(pip_size)} freed)")
        add("🐍", "pip cache cleared", f"{human(pip_size)} freed", pip_size)
        break
else:
    skip("pip not installed")


# ══════════════════════════════════════════════════════════════
# 15. XCODE (--full only)
# ══════════════════════════════════════════════════════════════

header("📐 Xcode")

if FULL_MODE and shutil.which("xcodebuild"):
    dd      = HOME / "Library/Developer/Xcode/DerivedData"
    dd_size = dir_size(dd)
    shutil.rmtree(str(dd), ignore_errors=True)
    dd.mkdir(exist_ok=True)
    ok(f"DerivedData cleared (~{human(dd_size)} freed)")
    run("xcrun simctl delete unavailable")
    ok("Unavailable simulators removed")
    add("📐", "Xcode cleaned", f"DerivedData ({human(dd_size)}) + simulators pruned", dd_size)
elif not FULL_MODE:
    info("Xcode skipped — use --full to include")
    add("📐", "Xcode", "Skipped (use --full)")
else:
    skip("Xcode not installed")
    add("📐", "Xcode", "Not installed")


# ══════════════════════════════════════════════════════════════
# 16. DOCKER (--full only)
# ══════════════════════════════════════════════════════════════

header("🐳 Docker")

if FULL_MODE and shutil.which("docker"):
    if run("docker info").returncode == 0:
        run("docker system prune -af --volumes")
        ok("Docker pruned — unused images, containers, volumes removed")
        add("🐳", "Docker pruned", "All unused resources removed")
    else:
        warn("Docker not running")
        add("🐳", "Docker", "Not running")
elif not FULL_MODE:
    info("Docker skipped — use --full to include")
    add("🐳", "Docker", "Skipped (use --full)")
else:
    skip("Docker not installed")


# ══════════════════════════════════════════════════════════════
# 17. DNS
# ══════════════════════════════════════════════════════════════

header("🌐 DNS")

run("dscacheutil -flushcache")
run("killall -HUP mDNSResponder")
ok("DNS cache flushed")
add("🌐", "DNS flushed", "dscacheutil + mDNSResponder")


# ══════════════════════════════════════════════════════════════
# 18. RESTART FINDER + DOCK
# ══════════════════════════════════════════════════════════════

header("🔄 Restarting UI")

run("killall Finder")
run("killall Dock")
ok("Finder and Dock restarted")
add("🔄", "Finder & Dock restarted", "UI refreshed")


# ══════════════════════════════════════════════════════════════
# 19. HTML REPORT
# ══════════════════════════════════════════════════════════════

header("📊 Report")

elapsed     = int(time.time() - start)
report_path = DESKTOP / f"Mac_Clean_Report_{datetime.now():%Y-%m-%d_%H%M}.html"

import json
items_json = json.dumps(report)

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Mac Clean Report — {datetime.now():%d %b %Y}</title>
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;700;800&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root {{
  --bg: #0a0a0f; --surface: #13131a; --surface2: #1c1c28;
  --border: #2a2a3a; --accent: #00e5a0; --text: #e8e8f0; --muted: #6b6b88;
}}
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ background: var(--bg); color: var(--text); font-family: 'Syne', sans-serif;
  min-height: 100vh; padding: 0 0 80px; }}
.hero {{ position: relative; padding: 80px 40px 60px; text-align: center; overflow: hidden; }}
.hero::before {{ content: ''; position: absolute; inset: 0;
  background: radial-gradient(ellipse 60% 50% at 50% -10%, rgba(0,229,160,.18) 0%, transparent 70%);
  pointer-events: none; }}
.eyebrow {{ font-family: 'DM Mono', monospace; font-size: .75rem; letter-spacing: .2em;
  text-transform: uppercase; color: var(--accent); margin-bottom: 20px; }}
h1 {{ font-size: clamp(2.8rem, 8vw, 6rem); font-weight: 800; line-height: 1; letter-spacing: -.03em;
  background: linear-gradient(135deg, #fff 30%, var(--accent) 100%);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 12px; }}
.sub {{ color: var(--muted); font-size: 1rem; font-family: 'DM Mono', monospace; }}
.stats {{ display: flex; max-width: 700px; margin: 40px auto 0;
  border: 1px solid var(--border); border-radius: 16px; overflow: hidden;
  background: var(--surface); }}
.stat {{ flex: 1; padding: 28px 24px; text-align: center; border-right: 1px solid var(--border); }}
.stat:last-child {{ border-right: none; }}
.stat-val {{ font-size: 2rem; font-weight: 800; color: var(--accent); }}
.stat-label {{ font-family: 'DM Mono', monospace; font-size: .7rem; letter-spacing: .12em;
  text-transform: uppercase; color: var(--muted); margin-top: 6px; }}
.wrap {{ max-width: 1000px; margin: 64px auto 0; padding: 0 40px; }}
.section-label {{ font-family: 'DM Mono', monospace; font-size: .7rem; letter-spacing: .18em;
  text-transform: uppercase; color: var(--muted); margin-bottom: 20px; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 12px; }}
.card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 14px;
  padding: 22px 24px; display: flex; align-items: flex-start; gap: 16px;
  animation: fadeUp .4s ease both; }}
@keyframes fadeUp {{ from {{ opacity:0; transform:translateY(16px) }} to {{ opacity:1; transform:translateY(0) }} }}
.emoji {{ font-size: 1.6rem; flex-shrink: 0; width: 42px; height: 42px;
  display: flex; align-items: center; justify-content: center;
  background: var(--surface2); border-radius: 10px; border: 1px solid var(--border); }}
.card-body {{ flex: 1; min-width: 0; }}
.card-title {{ font-weight: 700; font-size: .95rem; margin-bottom: 4px; }}
.card-detail {{ font-family: 'DM Mono', monospace; font-size: .72rem; color: var(--muted); line-height: 1.4; }}
.card-freed {{ font-family: 'DM Mono', monospace; font-size: .75rem; color: var(--accent); margin-top: 8px; }}
footer {{ text-align: center; margin-top: 80px; font-family: 'DM Mono', monospace;
  font-size: .72rem; color: var(--muted); }}
</style>
</head>
<body>
<div class="hero">
  <p class="eyebrow">🍎 Mac Deep Clean — {datetime.now():%A, %d %B %Y at %H:%M}</p>
  <h1>All<br>Clean.</h1>
  <p class="sub">Your Mac has been scrubbed, sorted &amp; optimised.</p>
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
const items = {items_json};
const grid  = document.getElementById('grid');
items.forEach((item, i) => {{
  const c = document.createElement('div');
  c.className = 'card';
  c.style.animationDelay = (i * 40) + 'ms';
  c.innerHTML = `<div class="emoji">${{item.emoji}}</div>
    <div class="card-body">
      <div class="card-title">${{item.title}}</div>
      <div class="card-detail">${{item.detail}}</div>
      ${{item.freed ? `<div class="card-freed">↓ ${{item.freed}} freed</div>` : ''}}
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
print("  ╔═══════════════════════════════════════╗")
print("  ║       ✅ DEEP CLEAN COMPLETE          ║")
print(f"  ║  💾 ~{human(total_freed):<34}║")
print(f"  ║  ⏱  Finished in {elapsed} seconds{' '*(22-len(str(elapsed)))}║")
print("  ║  📊 Report opened on Desktop          ║")
print("  ╚═══════════════════════════════════════╝")
print(NC)
print(f"  {D}Tip: run with --full to also clean Xcode & Docker{NC}\n")
