"""
ChestBot — Build Script
────────────────────────────────────────────────
Run this on your Windows machine to produce a
single distributable .exe inside the /dist folder.

Requirements:
    pip install pyinstaller

Usage:
    python build.py
"""

import subprocess
import sys
import os

APP_NAME    = "ChestBot"
SCRIPT      = "chestbot.py"
ICON        = "icon.ico"          # optional — replace with your .ico file path
             #                      or remove the --icon line below if you don't have one

def main():
    if not os.path.exists(SCRIPT):
        print(f"ERROR: {SCRIPT} not found. Run this script from the ChestBot folder.")
        sys.exit(1)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",              # single .exe, no folder clutter
        "--windowed",             # no console window (GUI app)
        "--name", APP_NAME,
        "--clean",                # fresh build every time
        "--noconfirm",            # overwrite previous dist without asking
    ]

    # Add icon if it exists
    if os.path.exists(ICON):
        cmd += ["--icon", ICON]
    else:
        print(f"Note: {ICON} not found — building without a custom icon.")

    # Hidden imports that PyInstaller sometimes misses with ultralytics/torch
    hidden = [
        "ultralytics",
        "PIL._tkinter_finder",
        "numpy",
        "requests",
        "tkinter",
        "winreg",
    ]
    for h in hidden:
        cmd += ["--hidden-import", h]

    cmd.append(SCRIPT)

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    print("-" * 50)
    print(f"Building {APP_NAME}.exe ...")
    print("This may take 2-5 minutes on first run.")
    print("-" * 50)

    result = subprocess.run(cmd)

    if result.returncode == 0:
        exe_path = os.path.join("dist", f"{APP_NAME}.exe")
        size_mb  = round(os.path.getsize(exe_path) / 1024 / 1024, 1) if os.path.exists(exe_path) else "?"
        print("\n" + "-" * 50)
        print("OK  Build complete!")
        print(f"   Output:  dist/{APP_NAME}.exe  ({size_mb} MB)")
        print(f"\n   Put dist/{APP_NAME}.exe into your zip.")
        print(f"   Buyers run it directly -- no Python needed.")
        print("-" * 50)
    else:
        print("\nERROR  Build failed. Check the output above for errors.")
        print("   Common fix: pip install pyinstaller --upgrade")
        sys.exit(1)


if __name__ == "__main__":
    main()
