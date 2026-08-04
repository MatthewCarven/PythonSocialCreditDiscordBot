"""
sync.py — Project file sync utility for the MatthewCarven game project family.

Run this from inside the Python SocialCreditBot folder after making changes to
any shared source-of-truth files. It copies them out to sibling projects.

Usage:
    python sync.py           — Dry run. Shows what WOULD be copied, copies nothing.
    python sync.py --apply   — Actually copies the files.

HOW IT WORKS
------------
This folder (SocialCreditBot) is the source of truth.
Shared files live here and get copied to sibling folders in the same parent directory.

Currently synced:
    game_engine.py  →  Python Trash Colllector 2
    mining_db.py    →  Python Trash Colllector 2

When car_engine.py exists, it will also sync to:
    car_engine.py   →  Python Car Collector 2
    car_engine.py   →  Python Car Collector 2 Standalone  (future)

ADDING NEW SHARED FILES
-----------------------
Just add an entry to SYNC_RULES below.
Each rule is: (source_filename, destination_folder_name)
"""

import os
import sys
import shutil
import hashlib
from datetime import datetime

# Windows consoles often default to cp1252, which can't print the emoji
# below — and a crash mid-loop during --apply would mean a partial sync.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


# ---------------------------------------------------------------------------
# SYNC RULES
# Format: (source filename, destination folder name)
# Folder names are relative to the shared parent directory.
# ---------------------------------------------------------------------------
SYNC_RULES = [
    ("game_engine.py", "Python Trash Colllector 2"),   # Note: triple L in Colllector
    ("mining_db.py",   "Python Trash Colllector 2"),

    # Uncomment when car_engine.py exists:
    # ("car_engine.py",  "Python Car Collector 2"),
    # ("car_engine.py",  "Python Car Collector 2 Standalone"),
]


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def md5(filepath):
    """Return MD5 hex digest of a file."""
    h = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def files_are_identical(src, dst):
    """True if both files exist and have the same content."""
    if not os.path.exists(dst):
        return False
    return md5(src) == md5(dst)


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    dry_run = "--apply" not in sys.argv

    # Locate this script → SocialCreditBot folder → parent (Desktop/OneDrive folder)
    this_dir   = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(this_dir)

    print("=" * 60)
    print("  MatthewCarven Project Sync")
    print(f"  Source:  {this_dir}")
    print(f"  Parent:  {parent_dir}")
    if dry_run:
        print("  Mode:    DRY RUN  (use --apply to actually copy)")
    else:
        print("  Mode:    APPLY — files will be copied")
    print("=" * 60)
    print()

    any_changes = False
    errors = []

    for source_file, dest_folder in SYNC_RULES:
        src_path  = os.path.join(this_dir, source_file)
        dest_dir  = os.path.join(parent_dir, dest_folder)
        dest_path = os.path.join(dest_dir, source_file)

        # Check source exists
        if not os.path.exists(src_path):
            print(f"  ⚠️  SKIP   {source_file} → {dest_folder}")
            print(f"            (source not found: {src_path})")
            print()
            continue

        # Check destination folder exists
        if not os.path.isdir(dest_dir):
            msg = f"Destination folder not found: {dest_dir}"
            print(f"  ❌ ERROR  {source_file} → {dest_folder}")
            print(f"            {msg}")
            print()
            errors.append(msg)
            continue

        # Compare
        if files_are_identical(src_path, dest_path):
            print(f"  ✅ IN SYNC  {source_file} → {dest_folder}")
        else:
            any_changes = True
            if os.path.exists(dest_path):
                action = "UPDATE"
            else:
                action = "NEW   "

            if dry_run:
                print(f"  📋 PENDING {action}  {source_file} → {dest_folder}")
            else:
                shutil.copy2(src_path, dest_path)
                print(f"  📋 COPIED  {action}  {source_file} → {dest_folder}")

        print()

    # Summary
    print("=" * 60)
    if errors:
        print(f"  ⚠️  Finished with {len(errors)} error(s):")
        for e in errors:
            print(f"     - {e}")
    elif dry_run and any_changes:
        print("  Pending changes found. Run with --apply to copy them.")
    elif dry_run and not any_changes:
        print("  All files already in sync. Nothing to do.")
    elif not dry_run and any_changes:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        print(f"  Sync complete at {ts}.")
    else:
        print("  All files already in sync. Nothing to do.")
    print("=" * 60)


if __name__ == "__main__":
    main()
