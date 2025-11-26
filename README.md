# Media Server Utilities (Jellyfin / Plex)

A collection of Python scripts to help organize, manage, and "tame" local media libraries for Jellyfin, Plex, and Emby.

## 📂 Current Tools

### 1. `jellyfin_organizer.py` (The Disc Flattener)

**The Problem:**
Ripping physical media (using tools like MakeMKV) often leaves you with messy structures like `TV Show > Season 1 > Disc 1 > Title_t00.mkv`. Media servers hate this. They want flat structures (`S01E01`, `S01E02`). Renaming files manually—especially calculating that "Disc 2" starts at "Episode 5"—is tedious and prone to error.

**The Solution:**
This script scans your library (or a single show), detects "Disc" folders, calculates global episode numbers automatically, and flattens the structure into a format media servers love.

**Features:**
* **Safe Mode:** Generates a `.bat` (Windows) or `.sh` (Linux/Mac) script. **No files are moved until you review and run that script.**
* **Smart Detection:** Works on an entire library or a single show folder automatically.
* **Global Numbering:** Understands that if Disc 1 has 4 episodes, Disc 2 starts at Episode 5.
* **MKV Sorting:** Sorts generic filenames (`t00`, `t01`) alphabetically to ensure episode order is preserved before renaming.
* **Quiet Mode:** Only reports shows that actually need fixing.
* **Ignore Support:** Ignores "Extras" folders and any file tagged with `[IGNORE]`.

**Usage:**

1.  Download `jellyfin_organizer.py`.
2.  Run the script:
    ```bash
    python3 jellyfin_organizer.py /path/to/your/media
    ```
3.  Review the "Tree View" output in the terminal.
4.  If the plan looks good, run the generated script:
    * **Linux/Mac:** `./apply_renames.sh`
    * **Windows:** Double-click `apply_renames.bat`

---

## 🛠 Requirements

* Python 3.x
* No external dependencies required (uses standard library).

## ⚠️ Disclaimer

While this script is designed to be safe (by generating a reviewable plan before acting), always ensure you have backups of your media or test on a small folder first. I am not responsible for lost data.

## 🤝 Contributing

Feel free to submit Pull Requests or open Issues if you have ideas for new scripts or improvements!
