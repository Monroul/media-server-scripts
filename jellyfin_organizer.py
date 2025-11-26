import os
import re
import sys
import platform
from pathlib import Path

"""
JELLYFIN/PLEX MEDIA ORGANIZER (Smart & Quiet Edition)
-----------------------------------------------------
Features:
1.  Works on a full Library folder OR a single Show folder automatically.
2.  "Quiet Mode": Only lists shows/files that actually require changes.
3.  Handles "Season X" and "Disc X" structures.
4.  Global Episode Numbering: Calculates offsets for Disc 2, Disc 3, etc.
5.  Ignores specific folders (Extras) and files tagged with [IGNORE].
6.  Generates a SAFE 'apply' script. No files are moved until you run the generated script.

Usage:
1.  python3 jellyfin_organizer.py /path/to/media
2.  Review output.
3.  Run generated apply_renames script.

Author: Generated with the help of Gemini AI.
"""

# --- CONFIGURATION ---
VIDEO_EXTENSIONS = {'.mkv', '.mp4', '.avi', '.m4v', '.iso', '.wmv'}
# Folders to ignore
FOLDER_IGNORE_KEYWORDS = ['RAZOR', 'THE PLAN', 'CONQUEST', 'EXTRAS', 'SPECIALS', 'FEATURETTES', 'SAMPLE']
# Files to ignore if they contain these strings
FILE_IGNORE_KEYWORDS = ['[IGNORE]', 'SAMPLE', 'TRAILER']

class ShowProcessor:
    def __init__(self):
        self.operations = [] 
        self.tree_output = [] # Stores final output to print
        
    def get_clean_season_num(self, folder_name):
        match = re.search(r"(?:season|staffel|s)[_.\-\s]?(\d+)", folder_name, re.IGNORECASE)
        return int(match.group(1)) if match else None

    def get_clean_disc_num(self, folder_name, season_num):
        temp_name = re.sub(f"s{season_num}", "", folder_name, flags=re.IGNORECASE)
        match = re.search(r"(?:disc|disk|dvd|d)[_.\-\s]?(\d+)", temp_name, re.IGNORECASE)
        if not match:
             match = re.search(r"s(\d+)d(\d+)", folder_name, re.IGNORECASE)
             if match and int(match.group(1)) == season_num:
                 return int(match.group(2))
        return int(match.group(1)) if match else None

    def get_episode_from_file(self, filename):
        match = re.search(r"[sS]\d+[eE](\d+)", filename)
        return int(match.group(1)) if match else None

    def should_ignore_file(self, filename):
        return any(k.upper() in filename.upper() for k in FILE_IGNORE_KEYWORDS)

    def process_show(self, show_path):
        # Buffer logs for this show. We only commit them if changes are found.
        show_logs = []
        initial_ops_count = len(self.operations)
        
        show_logs.append(f"\n📺 {show_path.name}")
        
        items = sorted(list(show_path.iterdir()))
        folders = [x for x in items if x.is_dir()]
        root_files = [x for x in items if x.is_file() and x.suffix.lower() in VIDEO_EXTENSIONS]
        
        seasons_map = {}
        
        # 1. Map Folders to Seasons
        for folder in folders:
            if any(k in folder.name.upper() for k in FOLDER_IGNORE_KEYWORDS):
                continue
            s_num = self.get_clean_season_num(folder.name)
            if s_num is not None:
                seasons_map[s_num] = folder

        # 2. Handle Root Files as Season 1 if implied
        if root_files and not any(self.should_ignore_file(f.name) for f in root_files):
            if 1 not in seasons_map:
                seasons_map[1] = "CREATE_ROOT_S1"

        # 3. Process each Season
        for s_num in sorted(seasons_map.keys()):
            folder = seasons_map[s_num]
            target_season_name = f"Season {s_num}"
            
            if folder == "CREATE_ROOT_S1":
                 self.process_season_content(show_path, root_files, s_num, target_season_name, is_root=True, logs=show_logs)
            else:
                rename_op = target_season_name if folder.name != target_season_name else None
                self.log_tree(show_logs, 1, folder.name, rename_op)
                self.process_season_content(folder, [], s_num, target_season_name, is_root=False, logs=show_logs)

        # 4. COMMIT LOGS: Only if operations were added for this show
        if len(self.operations) > initial_ops_count:
            self.tree_output.extend(show_logs)

    def process_season_content(self, current_path, root_files_list, s_num, target_season_name, is_root, logs):
        episode_counter = 0
        discs_map = {}
        direct_files = []

        if is_root:
            direct_files = sorted(root_files_list, key=lambda x: x.name)
        else:
            items = sorted(list(current_path.iterdir()))
            for item in items:
                if item.is_dir():
                    d_num = self.get_clean_disc_num(item.name, s_num)
                    if d_num: discs_map[d_num] = item
                elif item.is_file() and item.suffix.lower() in VIDEO_EXTENSIONS:
                    direct_files.append(item)

        # Process Direct Files
        for f in direct_files:
            if self.should_ignore_file(f.name): continue
            episode_counter = self.plan_file_rename(f, s_num, episode_counter, 2, logs, is_root_move=is_root)

        # Process Discs
        for d_num in sorted(discs_map.keys()):
            disc_folder = discs_map[d_num]
            target_disc_name = f"S{s_num}D{d_num}"
            
            # Check if disc folder needs rename
            rename_op = target_disc_name if disc_folder.name != target_disc_name else None
            
            # Buffer disc log (we might need to remove it if no files inside change? 
            # For simplicity, we keep folder structure visualization if files inside change)
            self.log_tree(logs, 2, disc_folder.name, rename_op)
            
            disc_files = sorted([x for x in disc_folder.iterdir() if x.is_file() and x.suffix.lower() in VIDEO_EXTENSIONS], key=lambda x: x.name)
            for f in disc_files:
                if self.should_ignore_file(f.name): continue
                episode_counter = self.plan_file_rename(f, s_num, episode_counter, 3, logs)

    def plan_file_rename(self, file_path, season_num, current_counter, indent, logs, is_root_move=False):
        explicit_ep = self.get_episode_from_file(file_path.name)
        
        if explicit_ep:
            current_counter = max(current_counter, explicit_ep)
            final_ep_num = explicit_ep
        else:
            current_counter += 1
            final_ep_num = current_counter
            
        new_name = f"S{season_num:02d}E{final_ep_num:02d}{file_path.suffix}"
        
        # Determine if change is needed
        needs_rename = file_path.name != new_name
        op = new_name if (needs_rename or is_root_move) else None
        
        if op:
            self.log_tree(logs, indent, file_path.name, op)
            self.operations.append({
                'original': file_path,
                'new_name': new_name,
                'season_num': season_num,
                'is_root_move': is_root_move
            })
        return current_counter

    def log_tree(self, log_list, level, text, operation=None):
        indent = "    " * level
        if operation:
            msg = f"{indent}├── {text}  ->  {operation}"
        else:
            msg = f"{indent}└── {text}"
        log_list.append(msg)

    def generate_script(self):
        if not self.operations:
            return None

        is_windows = os.name == 'nt'
        filename = "apply_renames.bat" if is_windows else "apply_renames.sh"
        
        with open(filename, 'w', encoding='utf-8') as f:
            if not is_windows: f.write("#!/bin/bash\n")
            f.write(f"REM Generated by Jellyfin Organizer\n" if is_windows else "# Generated by Jellyfin Organizer\n")
            
            for op in self.operations:
                orig = str(op['original'])
                parent = op['original'].parent
                
                if op['is_root_move']:
                    dest_folder = op['original'].parent / f"Season {op['season_num']}"
                    dest_file = dest_folder / op['new_name']
                    if is_windows:
                        f.write(f'mkdir "{dest_folder}" 2>nul\n')
                        f.write(f'move "{orig}" "{dest_file}"\n')
                    else:
                        f.write(f'mkdir -p "{dest_folder}"\n')
                        f.write(f'mv -n "{orig}" "{dest_file}"\n')
                else:
                    dest_file = parent / op['new_name']
                    if is_windows:
                        f.write(f'move "{orig}" "{dest_file}"\n')
                    else:
                        f.write(f'mv -n "{orig}" "{dest_file}"\n')
        return filename

def detect_mode_and_run(path_str):
    target_path = Path(path_str).resolve()
    if not target_path.exists():
        print("❌ Error: Path not found!")
        return

    processor = ShowProcessor()
    
    # HEURISTIC: Is this a single show or a library?
    # Check if immediate children contain "Season" folders or video files
    children = [x for x in target_path.iterdir()]
    has_season_folders = any("season" in x.name.lower() or "staffel" in x.name.lower() for x in children if x.is_dir())
    has_video_files = any(x.suffix.lower() in VIDEO_EXTENSIONS for x in children if x.is_file())

    if has_season_folders or has_video_files:
        print(f"📂 Detected SINGLE SHOW mode: {target_path.name}")
        processor.process_show(target_path)
    else:
        print(f"📚 Detected LIBRARY mode (scanning subfolders of {target_path.name})...")
        shows = [x for x in children if x.is_dir()]
        for show in sorted(shows):
            processor.process_show(show)

    # OUTPUT
    if processor.tree_output:
        print("\n" + "="*50)
        print("PROPOSED CHANGES (Nothing changed yet!)")
        print("="*50)
        for line in processor.tree_output: print(line)
        print("="*50)
        
        script_name = processor.generate_script()
        print(f"\n✅ Plan generated in: {script_name}")
        print(f"👉 Review the tree above. If satisfied, run the script to apply.")
    else:
        print("\n✨ Library is clean! No changes needed.")

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else input("Enter path to Media/Show folder: ").strip()
    detect_mode_and_run(target)
