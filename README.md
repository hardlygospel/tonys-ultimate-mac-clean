# 🍎⚡ Tony's Ultimate Mac Clean

[![Stars](https://img.shields.io/github/stars/hardlygospel/tonys-ultimate-mac-clean?style=for-the-badge&color=yellow)](https://github.com/hardlygospel/tonys-ultimate-mac-clean/stargazers) [![Forks](https://img.shields.io/github/forks/hardlygospel/tonys-ultimate-mac-clean?style=for-the-badge&color=blue)](https://github.com/hardlygospel/tonys-ultimate-mac-clean/network/members) [![Issues](https://img.shields.io/github/issues/hardlygospel/tonys-ultimate-mac-clean?style=for-the-badge&color=red)](https://github.com/hardlygospel/tonys-ultimate-mac-clean/issues) [![Last Commit](https://img.shields.io/github/last-commit/hardlygospel/tonys-ultimate-mac-clean?style=for-the-badge&color=green)](https://github.com/hardlygospel/tonys-ultimate-mac-clean/commits) [![License](https://img.shields.io/badge/License-GPL_v3-blue?style=for-the-badge)](https://github.com/hardlygospel/tonys-ultimate-mac-clean/blob/main/LICENSE) [![macOS](https://img.shields.io/badge/macOS-supported-brightgreen?style=for-the-badge&logo=apple)](https://github.com/hardlygospel/tonys-ultimate-mac-clean) [![Linux](https://img.shields.io/badge/Linux-supported-brightgreen?style=for-the-badge&logo=linux)](https://github.com/hardlygospel/tonys-ultimate-mac-clean) [![Shell](https://img.shields.io/badge/Shell-Bash-4EAA25?style=for-the-badge&logo=gnubash)](https://github.com/hardlygospel/tonys-ultimate-mac-clean) [![Docker](https://img.shields.io/badge/Docker-ready-2496ED?style=for-the-badge&logo=docker)](https://github.com/hardlygospel/tonys-ultimate-mac-clean) [![Maintained](https://img.shields.io/badge/Maintained-yes-brightgreen?style=for-the-badge)](https://github.com/hardlygospel/tonys-ultimate-mac-clean) [![Repo Size](https://img.shields.io/github/repo-size/hardlygospel/tonys-ultimate-mac-clean?style=for-the-badge)](https://github.com/hardlygospel/tonys-ultimate-mac-clean) [![Code Size](https://img.shields.io/github/languages/code-size/hardlygospel/tonys-ultimate-mac-clean?style=for-the-badge)](https://github.com/hardlygospel/tonys-ultimate-mac-clean)
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

This project is licensed under the **GNU General Public License v3.0**.


You are free to use, modify, and distribute this software under the terms of the GPL-3.0. See the [full licence](https://github.com/hardlygospel/tonys-ultimate-mac-clean/blob/main/LICENSE) for details.
