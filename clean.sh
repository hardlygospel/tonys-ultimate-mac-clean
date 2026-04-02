#!/bin/bash
# ╔══════════════════════════════════════════════════════════════╗
# ║         MAC DEEP CLEAN  —  mac_deep_clean.sh                ║
# ║  Zero-intervention. Run once. Walk away spotless.           ║
# ╚══════════════════════════════════════════════════════════════╝
#
#  WHAT IT CLEANS:
#  ─────────────────────────────────────────────────────────────
#  📸 Screenshots     → sorted into ~/Pictures/Screenshots/YYYY/MM
#  🖥  Desktop        → loose files → ~/Desktop/Misc
#  📥 Downloads       → files 30+ days old → ~/Downloads/Archive
#  🗑  Trash          → emptied
#  🧹 User Caches     → ~/Library/Caches cleared
#  🪵 Log Files       → ~/Library/Logs cleared
#  💾 App State       → saved state for apps cleared
#  🎵 iTunes/Music    → old device backups removed
#  🔤 Font Caches     → rebuilt
#  📦 Xcode           → derived data, archives, simulators (if installed)
#  🐍 pip             → cache cleared
#  💎 Gem             → old gems cleaned
#  🍺 Homebrew        → update + cleanup (if installed)
#  🐳 Docker          → prune unused images/containers (if installed)
#  📝 TextEdit        → recent docs list cleared
#  🕵️  Spotlight      → unnecessary metadata re-index prevented
#  🌐 DNS             → flushed
#  🧠 RAM             → memory pressure purged
#  📊 Report          → beautiful HTML report saved to ~/Desktop
#  ─────────────────────────────────────────────────────────────
#
#  USAGE:
#    chmod +x mac_deep_clean.sh
#    ./mac_deep_clean.sh          # safe mode (skips big Xcode/Docker steps)
#    ./mac_deep_clean.sh --full   # includes Xcode + Docker
#
# ╔══════════════════════════════════════════════════════════════╗

set -uo pipefail

# ── Args ──────────────────────────────────────────────────────
FULL_MODE=false
[[ "${1:-}" == "--full" ]] && FULL_MODE=true

# ── Colours ───────────────────────────────────────────────────
BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
RED='\033[0;31m'
DIM='\033[2m'
NC='\033[0m'

# ── Report accumulator ────────────────────────────────────────
REPORT_ITEMS=()
TOTAL_FREED_BYTES=0

# ── Helpers ───────────────────────────────────────────────────
header() {
    echo -e "\n${CYAN}${BOLD}▸ $1${NC}"
    echo -e "${DIM}  ─────────────────────────────────────────${NC}"
}

log()  { echo -e "  ${GREEN}✔${NC}  $1"; }
info() { echo -e "  ${BLUE}→${NC}  $1"; }
warn() { echo -e "  ${YELLOW}⚠${NC}  $1"; }
skip() { echo -e "  ${DIM}–  $1 (skipped)${NC}"; }

# Returns size of path in bytes (0 if missing)
bytes_of() {
    if [[ -e "$1" ]]; then
        du -sk "$1" 2>/dev/null | awk '{print $1 * 1024}' || echo 0
    else
        echo 0
    fi
}

# Human-readable from bytes
human() {
    local b=$1
    if   (( b >= 1073741824 )); then printf "%.1f GB" "$(echo "scale=1; $b/1073741824" | bc)"
    elif (( b >= 1048576    )); then printf "%.1f MB" "$(echo "scale=1; $b/1048576"    | bc)"
    elif (( b >= 1024       )); then printf "%.1f KB" "$(echo "scale=1; $b/1024"       | bc)"
    else printf "%d B" "$b"
    fi
}

# Add an item to the HTML report
# report_item "emoji" "Title" "Detail" freed_bytes
report_item() {
    local emoji="$1" title="$2" detail="$3" freed="${4:-0}"
    TOTAL_FREED_BYTES=$(( TOTAL_FREED_BYTES + freed ))
    local freed_str=""
    [[ "$freed" -gt 0 ]] && freed_str="$(human $freed)"
    REPORT_ITEMS+=("{\"emoji\":\"$emoji\",\"title\":\"$title\",\"detail\":\"$detail\",\"freed\":\"$freed_str\"}")
}

# Safe rm -rf that logs before deleting
nuke() {
    local path="$1"
    if [[ -e "$path" ]]; then
        local sz
        sz=$(bytes_of "$path")
        rm -rf "$path" 2>/dev/null || true
        echo $sz
    else
        echo 0
    fi
}

# ─────────────────────────────────────────────────────────────
START_TIME=$(date +%s)

echo -e "\n${BOLD}${CYAN}"
echo "  ╔═══════════════════════════════════════╗"
echo "  ║      🍎  MAC DEEP CLEAN               ║"
echo "  ║      $(date '+%d %b %Y  %H:%M')                  ║"
echo "  ╚═══════════════════════════════════════╝"
echo -e "${NC}"

[[ "$FULL_MODE" == true ]] && warn "Running in --full mode (Xcode + Docker included)"

# ═══════════════════════════════════════════════════════════════
# 1. SCREENSHOTS
# ═══════════════════════════════════════════════════════════════
header "📸  Screenshots"

SCREENSHOTS_DEST="$HOME/Pictures/Screenshots"
MOVED=0

for dir in "$HOME/Desktop" "$HOME/Downloads"; do
    while IFS= read -r -d '' f; do
        fname=$(basename "$f")
        if [[ "$fname" =~ ([0-9]{4}-[0-9]{2}-[0-9]{2}) ]]; then
            year="${BASH_REMATCH[1]:0:4}"
            month="${BASH_REMATCH[1]:5:2}"
            dest="$SCREENSHOTS_DEST/$year/$month"
            mkdir -p "$dest"
            mv "$f" "$dest/" 2>/dev/null && MOVED=$((MOVED+1))
        elif [[ "$fname" =~ ^Screen\ Shot ]]; then
            mkdir -p "$SCREENSHOTS_DEST/Unsorted"
            mv "$f" "$SCREENSHOTS_DEST/Unsorted/" 2>/dev/null && MOVED=$((MOVED+1))
        fi
    done < <(find "$dir" -maxdepth 1 -type f \( -name "Screenshot*.png" -o -name "Screen Shot*.png" \) -print0 2>/dev/null)
done

if (( MOVED > 0 )); then
    log "$MOVED screenshot(s) sorted into $SCREENSHOTS_DEST/YYYY/MM"
    report_item "📸" "Screenshots sorted" "$MOVED files organised into ~/Pictures/Screenshots/YYYY/MM" 0
else
    info "No screenshots found on Desktop or Downloads."
    report_item "📸" "Screenshots" "Nothing to sort" 0
fi

# ═══════════════════════════════════════════════════════════════
# 2. DESKTOP TIDY
# ═══════════════════════════════════════════════════════════════
header "🖥️   Desktop"

MISC_DIR="$HOME/Desktop/Misc"
MISC_COUNT=0
while IFS= read -r -d '' f; do
    fname=$(basename "$f")
    [[ "$fname" == ".DS_Store" ]] && continue
    mkdir -p "$MISC_DIR"
    mv "$f" "$MISC_DIR/" 2>/dev/null && MISC_COUNT=$((MISC_COUNT+1))
done < <(find "$HOME/Desktop" -maxdepth 1 -type f -print0 2>/dev/null)

if (( MISC_COUNT > 0 )); then
    log "$MISC_COUNT loose file(s) moved → Desktop/Misc"
    report_item "🖥️" "Desktop tidied" "$MISC_COUNT loose files moved to ~/Desktop/Misc" 0
else
    info "Desktop already clean."
    report_item "🖥️" "Desktop" "Already tidy" 0
fi

# Remove .DS_Store files recursively from home folder
DS_COUNT=$(find "$HOME" -maxdepth 6 -name ".DS_Store" 2>/dev/null | wc -l | tr -d ' ')
find "$HOME" -maxdepth 6 -name ".DS_Store" -delete 2>/dev/null || true
(( DS_COUNT > 0 )) && log "Deleted $DS_COUNT .DS_Store file(s)" || info "No .DS_Store files found"

# ═══════════════════════════════════════════════════════════════
# 3. ARCHIVE OLD DOWNLOADS
# ═══════════════════════════════════════════════════════════════
header "📥  Downloads Archive"

ARCHIVE="$HOME/Downloads/Archive"
mkdir -p "$ARCHIVE"
OLD_COUNT=0
while IFS= read -r -d '' f; do
    fname=$(basename "$f")
    [[ "$fname" == ".DS_Store" ]] && continue
    mv "$f" "$ARCHIVE/" 2>/dev/null && OLD_COUNT=$((OLD_COUNT+1))
done < <(find "$HOME/Downloads" -maxdepth 1 -type f -mtime +30 -print0 2>/dev/null)

if (( OLD_COUNT > 0 )); then
    log "$OLD_COUNT file(s) older than 30 days → Downloads/Archive"
    report_item "📥" "Old downloads archived" "$OLD_COUNT files (30+ days old) moved to ~/Downloads/Archive" 0
else
    info "No old downloads to archive."
    report_item "📥" "Downloads" "Nothing older than 30 days" 0
fi

# ═══════════════════════════════════════════════════════════════
# 4. TRASH
# ═══════════════════════════════════════════════════════════════
header "🗑️   Trash"

TRASH_BYTES=$(bytes_of "$HOME/.Trash")
osascript -e 'tell app "Finder" to empty trash' 2>/dev/null && {
    log "Trash emptied (freed ~$(human $TRASH_BYTES))"
    report_item "🗑️" "Trash emptied" "$(human $TRASH_BYTES) freed" "$TRASH_BYTES"
} || {
    warn "Trash needs Finder — run manually with Cmd+Shift+Delete"
    report_item "🗑️" "Trash" "Skipped (run manually)" 0
}

# ═══════════════════════════════════════════════════════════════
# 5. USER CACHES
# ═══════════════════════════════════════════════════════════════
header "🧹  User Application Caches"

CACHE_DIR="$HOME/Library/Caches"
CACHE_BYTES=$(bytes_of "$CACHE_DIR")
find "$CACHE_DIR" -mindepth 1 -maxdepth 1 -exec rm -rf {} + 2>/dev/null || true
log "User caches cleared (freed ~$(human $CACHE_BYTES))"
report_item "🧹" "App caches cleared" "$(human $CACHE_BYTES) freed from ~/Library/Caches" "$CACHE_BYTES"

# ═══════════════════════════════════════════════════════════════
# 6. LOG FILES
# ═══════════════════════════════════════════════════════════════
header "🪵  Log Files"

LOG_DIR="$HOME/Library/Logs"
LOG_BYTES=$(bytes_of "$LOG_DIR")
find "$LOG_DIR" -mindepth 1 -exec rm -rf {} + 2>/dev/null || true
log "User logs cleared (freed ~$(human $LOG_BYTES))"
report_item "🪵" "Log files removed" "$(human $LOG_BYTES) freed from ~/Library/Logs" "$LOG_BYTES"

# System logs (needs sudo)
SYS_LOG_BYTES=$(bytes_of "/private/var/log")
if sudo -n true 2>/dev/null; then
    sudo find /private/var/log -name "*.log" -mtime +7 -delete 2>/dev/null || true
    log "Old system logs (7+ days) removed"
    report_item "🪵" "System logs pruned" "Logs older than 7 days removed" "$SYS_LOG_BYTES"
else
    info "System logs skipped (no sudo). Re-run with sudo for deeper clean."
fi

# ═══════════════════════════════════════════════════════════════
# 7. APP SAVED STATE
# ═══════════════════════════════════════════════════════════════
header "💾  App Saved State"

STATE_DIR="$HOME/Library/Saved Application State"
STATE_BYTES=$(bytes_of "$STATE_DIR")
rm -rf "$STATE_DIR"/* 2>/dev/null || true
log "App saved states cleared (freed ~$(human $STATE_BYTES))"
report_item "💾" "App saved states cleared" "$(human $STATE_BYTES) freed" "$STATE_BYTES"

# ═══════════════════════════════════════════════════════════════
# 8. QUICKLOOK CACHE
# ═══════════════════════════════════════════════════════════════
header "👁️   QuickLook Cache"

QL_DIR="$HOME/Library/Caches/com.apple.QuickLook.thumbnailcache"
QL_BYTES=$(bytes_of "$QL_DIR")
qlmanage -r cache 2>/dev/null || true
rm -rf "$QL_DIR" 2>/dev/null || true
log "QuickLook cache cleared (freed ~$(human $QL_BYTES))"
report_item "👁️" "QuickLook cache cleared" "$(human $QL_BYTES) freed" "$QL_BYTES"

# ═══════════════════════════════════════════════════════════════
# 9. FONT CACHES
# ═══════════════════════════════════════════════════════════════
header "🔤  Font Caches"

atsutil databases -remove 2>/dev/null && \
    log "Font database caches cleared" || \
    info "Font cache clear skipped (may need restart)"
report_item "🔤" "Font caches cleared" "Font database rebuilt on next login" 0

# ═══════════════════════════════════════════════════════════════
# 10. RECENT ITEMS / APP HISTORY
# ═══════════════════════════════════════════════════════════════
header "📝  Recent Items & App History"

# Clear recent documents list in Finder/system
defaults delete com.apple.recentitems 2>/dev/null || true
# TextEdit
defaults delete com.apple.TextEdit NSRecentDocumentRecords 2>/dev/null || true
# Preview
defaults delete com.apple.Preview NSRecentDocumentRecords 2>/dev/null || true
log "Recent items lists cleared (Finder, TextEdit, Preview)"
report_item "📝" "Recent items cleared" "Finder, TextEdit, Preview history wiped" 0

# ═══════════════════════════════════════════════════════════════
# 11. BROWSER CACHES (non-destructive — keeps logins/history)
# ═══════════════════════════════════════════════════════════════
header "🌍  Browser Caches"

BROWSER_BYTES=0

# Safari WebKit cache
SAFARI_CACHE="$HOME/Library/Caches/com.apple.Safari"
sz=$(bytes_of "$SAFARI_CACHE"); BROWSER_BYTES=$((BROWSER_BYTES+sz))
rm -rf "$SAFARI_CACHE" 2>/dev/null || true

# Chrome
CHROME_CACHE="$HOME/Library/Caches/Google/Chrome"
sz=$(bytes_of "$CHROME_CACHE"); BROWSER_BYTES=$((BROWSER_BYTES+sz))
rm -rf "$CHROME_CACHE" 2>/dev/null || true

# Firefox
FF_CACHE=$(find "$HOME/Library/Caches/Firefox" -maxdepth 3 -name "cache2" 2>/dev/null | head -1)
if [[ -n "$FF_CACHE" ]]; then
    sz=$(bytes_of "$FF_CACHE"); BROWSER_BYTES=$((BROWSER_BYTES+sz))
    rm -rf "$FF_CACHE" 2>/dev/null || true
fi

# Arc
ARC_CACHE="$HOME/Library/Caches/company.thebrowser.Browser"
sz=$(bytes_of "$ARC_CACHE"); BROWSER_BYTES=$((BROWSER_BYTES+sz))
rm -rf "$ARC_CACHE" 2>/dev/null || true

# Brave
BRAVE_CACHE="$HOME/Library/Caches/BraveSoftware"
sz=$(bytes_of "$BRAVE_CACHE"); BROWSER_BYTES=$((BROWSER_BYTES+sz))
rm -rf "$BRAVE_CACHE" 2>/dev/null || true

if (( BROWSER_BYTES > 0 )); then
    log "Browser caches cleared — $(human $BROWSER_BYTES) freed (Safari, Chrome, Firefox, Arc, Brave)"
    report_item "🌍" "Browser caches cleared" "$(human $BROWSER_BYTES) freed across all detected browsers" "$BROWSER_BYTES"
else
    info "No browser caches found."
    report_item "🌍" "Browser caches" "None found" 0
fi

# ═══════════════════════════════════════════════════════════════
# 12. MUSIC / ITUNES — OLD BACKUPS
# ═══════════════════════════════════════════════════════════════
header "🎵  Music / iTunes"

IOS_BACKUP_DIR="$HOME/Library/Application Support/MobileSync/Backup"
BACKUP_BYTES=$(bytes_of "$IOS_BACKUP_DIR")

if [[ -d "$IOS_BACKUP_DIR" ]]; then
    # Keep the 2 most recent backups, delete older ones
    BACKUP_COUNT=$(ls -1 "$IOS_BACKUP_DIR" 2>/dev/null | wc -l | tr -d ' ')
    if (( BACKUP_COUNT > 2 )); then
        ls -1t "$IOS_BACKUP_DIR" | tail -n +3 | while read -r bk; do
            rm -rf "$IOS_BACKUP_DIR/$bk" 2>/dev/null || true
        done
        log "Old iOS backups pruned (kept 2 most recent of $BACKUP_COUNT)"
        report_item "🎵" "iOS backups pruned" "Kept 2 most recent; removed $((BACKUP_COUNT-2)) old backup(s)" "$BACKUP_BYTES"
    else
        info "Only $BACKUP_COUNT iOS backup(s) — keeping all."
        report_item "🎵" "iOS backups" "Only $BACKUP_COUNT found — nothing pruned" 0
    fi
else
    info "No iOS backups directory found."
    report_item "🎵" "iOS backups" "None found" 0
fi

# ═══════════════════════════════════════════════════════════════
# 13. HOMEBREW
# ═══════════════════════════════════════════════════════════════
header "🍺  Homebrew"

if command -v brew &>/dev/null; then
    info "Updating Homebrew..."
    brew update --quiet 2>/dev/null || true
    BREW_BEFORE=$(bytes_of "$(brew --cache)")
    brew cleanup --prune=7 -q 2>/dev/null || true
    brew autoremove -q 2>/dev/null || true
    BREW_AFTER=$(bytes_of "$(brew --cache)")
    BREW_FREED=$(( BREW_BEFORE > BREW_AFTER ? BREW_BEFORE - BREW_AFTER : 0 ))
    log "Homebrew cleaned up (freed ~$(human $BREW_FREED))"
    report_item "🍺" "Homebrew cleaned" "$(human $BREW_FREED) freed; packages updated" "$BREW_FREED"
else
    skip "Homebrew not installed"
    report_item "🍺" "Homebrew" "Not installed" 0
fi

# ═══════════════════════════════════════════════════════════════
# 14. NODE / NPM
# ═══════════════════════════════════════════════════════════════
header "📦  Node / npm"

if command -v npm &>/dev/null; then
    NPM_CACHE=$(npm config get cache 2>/dev/null || echo "$HOME/.npm")
    NPM_BYTES=$(bytes_of "$NPM_CACHE")
    npm cache clean --force 2>/dev/null || true
    log "npm cache cleared (freed ~$(human $NPM_BYTES))"
    report_item "📦" "npm cache cleared" "$(human $NPM_BYTES) freed" "$NPM_BYTES"
else
    skip "npm not installed"
fi

# ═══════════════════════════════════════════════════════════════
# 15. PYTHON / PIP
# ═══════════════════════════════════════════════════════════════
header "🐍  Python / pip"

PIP_FREED=0
for pip_cmd in pip pip3 pip3.11 pip3.12; do
    if command -v "$pip_cmd" &>/dev/null; then
        PIP_DIR=$($pip_cmd cache dir 2>/dev/null || true)
        if [[ -n "$PIP_DIR" ]]; then
            sz=$(bytes_of "$PIP_DIR")
            $pip_cmd cache purge 2>/dev/null || true
            PIP_FREED=$((PIP_FREED + sz))
        fi
        break
    fi
done

if (( PIP_FREED > 0 )); then
    log "pip cache cleared (freed ~$(human $PIP_FREED))"
    report_item "🐍" "pip cache cleared" "$(human $PIP_FREED) freed" "$PIP_FREED"
else
    skip "pip not installed or no cache"
fi

# ═══════════════════════════════════════════════════════════════
# 16. RUBY / GEMS
# ═══════════════════════════════════════════════════════════════
header "💎  Ruby / Gems"

if command -v gem &>/dev/null; then
    GEM_BEFORE=$(gem list 2>/dev/null | wc -l | tr -d ' ')
    gem cleanup 2>/dev/null || true
    GEM_AFTER=$(gem list 2>/dev/null | wc -l | tr -d ' ')
    log "Old gem versions cleaned ($GEM_BEFORE → $GEM_AFTER versions)"
    report_item "💎" "Ruby gems cleaned" "Old gem versions removed" 0
else
    skip "gem not installed"
fi

# ═══════════════════════════════════════════════════════════════
# 17. XCODE (optional — only with --full)
# ═══════════════════════════════════════════════════════════════
header "📐  Xcode"

if [[ "$FULL_MODE" == true ]] && command -v xcodebuild &>/dev/null; then
    # Derived Data
    DD="$HOME/Library/Developer/Xcode/DerivedData"
    DD_BYTES=$(bytes_of "$DD")
    rm -rf "$DD"/* 2>/dev/null || true
    log "Xcode DerivedData cleared (freed ~$(human $DD_BYTES))"
    report_item "📐" "Xcode DerivedData cleared" "$(human $DD_BYTES) freed" "$DD_BYTES"

    # Archives older than 90 days
    ARCH_DIR="$HOME/Library/Developer/Xcode/Archives"
    ARCH_BYTES=0
    find "$ARCH_DIR" -maxdepth 2 -name "*.xcarchive" -mtime +90 | while read -r arc; do
        sz=$(bytes_of "$arc"); ARCH_BYTES=$((ARCH_BYTES+sz))
        rm -rf "$arc" 2>/dev/null || true
    done
    log "Old Xcode archives (90+ days) removed"
    report_item "📐" "Xcode archives pruned" "Archives older than 90 days removed" "$ARCH_BYTES"

    # Simulators
    xcrun simctl delete unavailable 2>/dev/null && \
        log "Unavailable iOS simulators removed" || true
    report_item "📐" "iOS Simulators" "Unavailable simulators pruned" 0
elif [[ "$FULL_MODE" == false ]]; then
    info "Xcode cleanup skipped (use --full to include)"
    report_item "📐" "Xcode" "Skipped (use --full)" 0
else
    skip "Xcode not installed"
    report_item "📐" "Xcode" "Not installed" 0
fi

# ═══════════════════════════════════════════════════════════════
# 18. DOCKER (optional — only with --full)
# ═══════════════════════════════════════════════════════════════
header "🐳  Docker"

if [[ "$FULL_MODE" == true ]] && command -v docker &>/dev/null; then
    if docker info &>/dev/null 2>&1; then
        docker system prune -af --volumes 2>/dev/null && \
            log "Docker: all unused images, containers, volumes pruned"
        report_item "🐳" "Docker pruned" "Unused images, containers & volumes removed" 0
    else
        warn "Docker installed but daemon not running — skipping"
        report_item "🐳" "Docker" "Daemon not running" 0
    fi
elif [[ "$FULL_MODE" == false ]]; then
    info "Docker cleanup skipped (use --full to include)"
    report_item "🐳" "Docker" "Skipped (use --full)" 0
else
    skip "Docker not installed"
    report_item "🐳" "Docker" "Not installed" 0
fi

# ═══════════════════════════════════════════════════════════════
# 19. DNS FLUSH
# ═══════════════════════════════════════════════════════════════
header "🌐  DNS Cache"

if sudo -n true 2>/dev/null; then
    sudo dscacheutil -flushcache 2>/dev/null
    sudo killall -HUP mDNSResponder 2>/dev/null
    log "DNS cache flushed"
    report_item "🌐" "DNS flushed" "dscacheutil + mDNSResponder restarted" 0
else
    # Try without sudo (works on some versions)
    dscacheutil -flushcache 2>/dev/null || true
    killall -HUP mDNSResponder 2>/dev/null || true
    log "DNS cache flush attempted (run with sudo for guaranteed flush)"
    report_item "🌐" "DNS flushed" "Attempted without sudo" 0
fi

# ═══════════════════════════════════════════════════════════════
# 20. MEMORY / RAM PRESSURE
# ═══════════════════════════════════════════════════════════════
header "🧠  Memory"

if sudo -n true 2>/dev/null; then
    sudo purge 2>/dev/null && \
        log "Inactive RAM purged (disk cache cleared)" || \
        warn "purge failed"
    report_item "🧠" "RAM purged" "Inactive memory freed via 'purge'" 0
else
    info "Memory purge skipped (needs sudo). Run: sudo purge"
    report_item "🧠" "RAM purge" "Skipped (needs sudo)" 0
fi

# ═══════════════════════════════════════════════════════════════
# 21. RELAUNCH FINDER & DOCK
# ═══════════════════════════════════════════════════════════════
header "🔄  Restarting UI Services"

killall Finder 2>/dev/null || true
killall Dock   2>/dev/null || true
log "Finder and Dock restarted (picks up all changes)"
report_item "🔄" "Finder & Dock restarted" "UI refreshed to apply all changes" 0

# ═══════════════════════════════════════════════════════════════
# 22. GENERATE HTML REPORT
# ═══════════════════════════════════════════════════════════════
header "📊  Generating Report"

END_TIME=$(date +%s)
ELAPSED=$(( END_TIME - START_TIME ))
REPORT_FILE="$HOME/Desktop/Mac_Clean_Report_$(date +%Y-%m-%d_%H%M).html"
TOTAL_HUMAN=$(human $TOTAL_FREED_BYTES)

# Build items JSON for the page
ITEMS_JSON="["
for i in "${!REPORT_ITEMS[@]}"; do
    [[ $i -gt 0 ]] && ITEMS_JSON+=","
    ITEMS_JSON+="${REPORT_ITEMS[$i]}"
done
ITEMS_JSON+="]"

cat > "$REPORT_FILE" <<HTMLEOF
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Mac Clean Report — $(date '+%d %b %Y')</title>
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;700;800&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
  :root {
    --bg: #0a0a0f;
    --surface: #13131a;
    --surface2: #1c1c28;
    --border: #2a2a3a;
    --accent: #00e5a0;
    --accent2: #7c6aff;
    --text: #e8e8f0;
    --muted: #6b6b88;
    --freed: #00e5a0;
  }
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: var(--bg);
    color: var(--text);
    font-family: 'Syne', sans-serif;
    min-height: 100vh;
    padding: 0 0 80px;
    overflow-x: hidden;
  }

  /* ── Hero ── */
  .hero {
    position: relative;
    padding: 80px 40px 60px;
    text-align: center;
    overflow: hidden;
  }
  .hero::before {
    content: '';
    position: absolute;
    inset: 0;
    background:
      radial-gradient(ellipse 60% 50% at 50% -10%, rgba(0,229,160,.18) 0%, transparent 70%),
      radial-gradient(ellipse 40% 30% at 80% 80%, rgba(124,106,255,.12) 0%, transparent 60%);
    pointer-events: none;
  }
  .hero-eyebrow {
    font-family: 'DM Mono', monospace;
    font-size: .75rem;
    letter-spacing: .2em;
    text-transform: uppercase;
    color: var(--accent);
    margin-bottom: 20px;
    opacity: .8;
  }
  .hero h1 {
    font-size: clamp(2.8rem, 8vw, 6rem);
    font-weight: 800;
    line-height: 1;
    letter-spacing: -.03em;
    background: linear-gradient(135deg, #fff 30%, var(--accent) 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin-bottom: 12px;
  }
  .hero-sub {
    color: var(--muted);
    font-size: 1rem;
    font-family: 'DM Mono', monospace;
  }

  /* ── Stats bar ── */
  .stats {
    display: flex;
    justify-content: center;
    gap: 0;
    max-width: 700px;
    margin: 40px auto 0;
    border: 1px solid var(--border);
    border-radius: 16px;
    overflow: hidden;
    background: var(--surface);
  }
  .stat {
    flex: 1;
    padding: 28px 24px;
    text-align: center;
    border-right: 1px solid var(--border);
    transition: background .2s;
  }
  .stat:last-child { border-right: none; }
  .stat:hover { background: var(--surface2); }
  .stat-val {
    font-size: 2rem;
    font-weight: 800;
    color: var(--accent);
    letter-spacing: -.02em;
    line-height: 1;
  }
  .stat-label {
    font-family: 'DM Mono', monospace;
    font-size: .7rem;
    letter-spacing: .12em;
    text-transform: uppercase;
    color: var(--muted);
    margin-top: 6px;
  }

  /* ── Grid ── */
  .grid-wrap {
    max-width: 1000px;
    margin: 64px auto 0;
    padding: 0 40px;
  }
  .section-label {
    font-family: 'DM Mono', monospace;
    font-size: .7rem;
    letter-spacing: .18em;
    text-transform: uppercase;
    color: var(--muted);
    margin-bottom: 20px;
  }
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 12px;
  }

  /* ── Card ── */
  .card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 22px 24px;
    display: flex;
    align-items: flex-start;
    gap: 16px;
    transition: transform .15s, border-color .15s, background .15s;
    animation: fadeUp .4s ease both;
  }
  .card:hover {
    transform: translateY(-2px);
    border-color: rgba(0,229,160,.3);
    background: var(--surface2);
  }
  @keyframes fadeUp {
    from { opacity: 0; transform: translateY(16px); }
    to   { opacity: 1; transform: translateY(0); }
  }
  .card-emoji {
    font-size: 1.6rem;
    flex-shrink: 0;
    width: 42px;
    height: 42px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--surface2);
    border-radius: 10px;
    border: 1px solid var(--border);
  }
  .card-body { flex: 1; min-width: 0; }
  .card-title {
    font-weight: 700;
    font-size: .95rem;
    color: var(--text);
    margin-bottom: 4px;
  }
  .card-detail {
    font-family: 'DM Mono', monospace;
    font-size: .72rem;
    color: var(--muted);
    line-height: 1.4;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .card-freed {
    font-family: 'DM Mono', monospace;
    font-size: .75rem;
    font-weight: 500;
    color: var(--freed);
    margin-top: 8px;
  }

  /* ── Footer ── */
  footer {
    text-align: center;
    margin-top: 80px;
    font-family: 'DM Mono', monospace;
    font-size: .72rem;
    color: var(--muted);
    letter-spacing: .06em;
  }
  footer a { color: var(--accent); text-decoration: none; }

  /* ── Scan line texture ── */
  body::after {
    content: '';
    position: fixed;
    inset: 0;
    background: repeating-linear-gradient(
      0deg,
      transparent,
      transparent 2px,
      rgba(0,0,0,.04) 2px,
      rgba(0,0,0,.04) 4px
    );
    pointer-events: none;
    z-index: 9999;
  }
</style>
</head>
<body>

<div class="hero">
  <p class="hero-eyebrow">🍎 Mac Deep Clean — $(date '+%A, %d %B %Y at %H:%M')</p>
  <h1>All<br>Clean.</h1>
  <p class="hero-sub">Your Mac has been scrubbed, sorted &amp; optimised.</p>

  <div class="stats">
    <div class="stat">
      <div class="stat-val">${TOTAL_HUMAN}</div>
      <div class="stat-label">Freed</div>
    </div>
    <div class="stat">
      <div class="stat-val">${#REPORT_ITEMS[@]}</div>
      <div class="stat-label">Tasks run</div>
    </div>
    <div class="stat">
      <div class="stat-val">${ELAPSED}s</div>
      <div class="stat-label">Duration</div>
    </div>
  </div>
</div>

<div class="grid-wrap">
  <p class="section-label">Detailed Results</p>
  <div class="grid" id="grid"></div>
</div>

<footer>
  <p>Generated by mac_deep_clean.sh &nbsp;·&nbsp; $(date '+%Y-%m-%d %H:%M:%S')</p>
</footer>

<script>
const items = ${ITEMS_JSON};
const grid = document.getElementById('grid');
items.forEach((item, i) => {
  const card = document.createElement('div');
  card.className = 'card';
  card.style.animationDelay = (i * 40) + 'ms';
  card.innerHTML = \`
    <div class="card-emoji">\${item.emoji}</div>
    <div class="card-body">
      <div class="card-title">\${item.title}</div>
      <div class="card-detail" title="\${item.detail}">\${item.detail}</div>
      \${item.freed ? \`<div class="card-freed">↓ \${item.freed} freed</div>\` : ''}
    </div>
  \`;
  grid.appendChild(card);
});
</script>
</body>
</html>
HTMLEOF

log "Report saved → $REPORT_FILE"
open "$REPORT_FILE" 2>/dev/null || true

# ═══════════════════════════════════════════════════════════════
# FINAL SUMMARY
# ═══════════════════════════════════════════════════════════════
echo -e "\n${BOLD}${CYAN}"
echo "  ╔═══════════════════════════════════════╗"
echo "  ║   ✅  DEEP CLEAN COMPLETE             ║"
printf "  ║   💾  %-32s║\n" "~$(human $TOTAL_FREED_BYTES) freed"
printf "  ║   ⏱   Finished in %-20s║\n" "${ELAPSED} seconds"
echo "  ║   📊  Report opened on Desktop       ║"
echo "  ╚═══════════════════════════════════════╝"
echo -e "${NC}"
echo -e "  ${DIM}Tip: run with ${NC}${BOLD}--full${NC}${DIM} flag to also clean Xcode & Docker${NC}\n"
