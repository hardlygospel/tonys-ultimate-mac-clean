# 🍎⚡ Tony's Ultimate Mac Clean
### *For Discord Users & Gamers*

> One command. No intervention. Walk away with a faster, cleaner Mac.

Built for people who spend more time in Discord and games than messing around with system settings. Run it, let it do its thing, and get back to what matters.

---

## ⚡ Quick Start

```bash
python3 mac_clean.py
```

That's it. No sudo. No questions. Just clean.

```bash
# Nuclear mode — also cleans Xcode & Docker
python3 mac_clean.py --full
```

---

## 🧹 What Gets Cleaned

| | What | Result |
|---|---|---|
| 📸 | **Screenshots** | Sorted into `Desktop/Screenshots/YYYY/MM` |
| 🖥️ | **Desktop** | Loose files moved to `Desktop/Misc` |
| 📥 | **Downloads** | Files 30+ days old archived automatically |
| 🗑️ | **Trash** | Emptied |
| 🧹 | **App Caches** | All of `~/Library/Caches` cleared |
| 🪵 | **Log Files** | User logs wiped |
| 💾 | **Saved App State** | App window history cleared |
| 👁️ | **QuickLook** | Thumbnail cache rebuilt |
| 📝 | **Recent Items** | Finder, TextEdit, Preview history wiped |
| 🌍 | **Browsers** | Safari, Chrome, Firefox, Arc & Brave caches cleared |
| 🎵 | **iOS Backups** | Keeps 2 most recent, prunes the rest |
| 🍺 | **Homebrew** | Updated + cleaned |
| 📦 | **npm** | Cache purged |
| 🐍 | **pip** | Cache purged |
| 💎 | **Ruby Gems** | Old versions removed |
| 🌐 | **DNS** | Cache flushed (speeds up browsing) |
| 🔄 | **Finder + Dock** | Restarted to apply changes |
| 📊 | **HTML Report** | Beautiful report auto-opens on your Desktop |

**With `--full` also cleans:**

| | What | Result |
|---|---|---|
| 📐 | **Xcode** | DerivedData, old archives, dead simulators |
| 🐳 | **Docker** | All unused images, containers & volumes |

---

## 📊 Report

After every run a slick dark-mode HTML report pops open on your Desktop:

- Total disk space freed
- Every task with its result
- How long it took

---

## 🎮 Why This Exists

Discord and games chew through cache, logs and temp files fast. macOS doesn't clean these up automatically. Screenshots pile up on the Desktop. Downloads folder becomes a graveyard. This script fixes all of that in one go.

Tested on macOS Ventura and Sonoma. Works from any shell including fish.

---

## 🔒 Safe by Default

- Files are **moved**, not deleted (Desktop → Misc, Downloads → Archive)
- Browser **passwords and history are never touched** — only cache
- iOS backups: always keeps your **2 most recent**
- `--full` Xcode/Docker cleanup is **opt-in only**

---

## 💻 Requirements

- macOS Ventura or later
- Python 3 (ships with macOS)
- Everything else (Homebrew, npm, pip etc.) is optional — skipped if not installed

---

## 📄 Licence

MIT — do whatever you like with it.

---

*Made with ☕ and too many open Discord tabs.*
