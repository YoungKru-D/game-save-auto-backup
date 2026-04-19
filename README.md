# 🎮 Game Save Backup Manager

A lightweight Python GUI tool to automatically back up game save files.

This tool is designed for games that frequently overwrite or rotate save files (e.g., using timestamps like `SAVE_3$2026...`). It ensures your latest save is always safely backed up.

<!-- --- -->

<!-- ## ✨ Features

* 🔄 Automatic backup on file change (real-time monitoring with watchdog)
* ⏱️ Time-based backup (interval-based)
* 📁 Supports dynamic save file patterns (e.g. `SAVE_3$...`)
* 🕒 Optional timestamped backups
* 🖥️ Simple GUI using Tkinter
* ⚡ Manual backup button
* 🧠 Smart detection of newest save file -->

---

## 🛠️ Requirements

* Python 3.x (tested on 3.10.11 and 3.14.3)
* Tkinter library for the GUI
  (usually included with Python, but may need to be installed separately depending on your setup)
* Optional (for real-time monitoring):

  ```
  pip install watchdog
  ```

---

## 🚀 How to Use

1. Run the script:

   ```
   python save_file_backuper.py
   ```

2. Select:

   * Source game save file
   * Backup destination folder

3. Choose backup mode:

   * **Modification mode** → triggers when the file changes
   * **Time-based mode** → performs backups every X seconds/minutes

4. Click **Start Monitoring**

---

## 📂 Backup Behavior

* If the file uses a pattern like:

  ```
  SAVE_3$2026.03.30-14.20.01
  ```

  The app will:

  * Automatically detect all matching files
  * Back up the **newest file only**

* For other save file it work similar but only takes the files when changes or by time and manual backup.
  (Important some games my use temp file to saved temporary then overwrite the main save file)

---

## 💡 Future Improvements

* Multiple save file support
* Folder-based save backup support
* Compression (ZIP backups)
* Cloud sync support (hopefully)

---

<!-- ## 📸 Screenshot

*(Add later if you want)*

--- -->

## 📜 License

MIT License

---

## ⚠️ Important Considerations Regarding Game Terms of Service

While this tool is not illegal to use, there is an important distinction between **legality** and **compliance with a game's Terms of Service (ToS)**.

### 🛡️ Anti-Cheat Systems

Many modern multiplayer games use intrusive anti-cheat systems such as Easy Anti-Cheat or BattlEye. These systems may monitor file access and background processes.

Because this tool monitors and accesses game save directories, it **may be flagged as suspicious behavior**, even if used purely for backup purposes.
This could potentially result in:

* Temporary suspension
* Permanent account bans

This happens not because the tool is malicious, but because it may violate the game's security policies.

---

<!-- ---

### 🎮 Single-Player vs Multiplayer

* ✅ **Safe:** Offline / single-player games (no anti-cheat, no competitive impact)
* ⚠️ **Risky:** Online / multiplayer games with anti-cheat systems

--- -->

### 💡 Recommendation

If you plan to use this tool:

* ✔ Use it for **offline or single-player games only**
* ❌ Avoid using it with **online/multiplayer titles**

For multiplayer games, it is safer to rely on:

* Steam Cloud
* Epic Games Launcher cloud saves
* Official in-game backup systems

These are designed to work within the game's security policies and will not risk account penalties.

---

**Use this tool at your own risk.**
