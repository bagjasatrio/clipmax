#!/usr/bin/env python3
"""
ClipMax Studio Pro Installer Builder
Automates building the C# launcher and generating the official Windows Inno Setup installer executable.
"""
import os
import sys
import subprocess
from pathlib import Path

def build():
    root = Path(__file__).resolve().parent
    print("[1/3] Building C# Launcher (ClipMax.exe)...")
    csc_path = Path("C:/Windows/Microsoft.NET/Framework64/v4.0.30319/csc.exe")
    if not csc_path.exists():
        csc_path = Path("C:/Windows/Microsoft.NET/Framework/v4.0.30319/csc.exe")

    if not csc_path.exists():
        print("ERROR: C# compiler (csc.exe) not found.")
        sys.exit(1)

    cmd_csc = [
        str(csc_path),
        "-target:winexe",
        "-win32icon:icon.ico",
        "-out:ClipMax.exe",
        "launcher.cs"
    ]
    res_csc = subprocess.run(cmd_csc, cwd=root)
    if res_csc.returncode != 0:
        print("ERROR: Failed compiling ClipMax.exe.")
        sys.exit(res_csc.returncode)
    print("      ClipMax.exe compiled successfully.")

    print("[2/3] Locating Inno Setup Compiler (ISCC.exe)...")
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    candidates = [
        Path(local_app_data) / "Programs" / "Inno Setup 6" / "ISCC.exe",
        Path("C:/Program Files (x86)/Inno Setup 6/ISCC.exe"),
        Path("C:/Program Files/Inno Setup 6/ISCC.exe"),
    ]
    iscc_bin = next((p for p in candidates if p.exists()), None)
    if not iscc_bin:
        print("ERROR: Inno Setup 6 (ISCC.exe) not found. Install via: winget install JRSoftware.InnoSetup")
        sys.exit(1)
    print(f"      Found compiler at: {iscc_bin}")

    print("[3/3] Compiling Setup Package (dist/ClipMax_Studio_v2.6.0_Setup.exe)...")
    dist_dir = root / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)

    cmd_iscc = [str(iscc_bin), "installer.iss"]
    res_iscc = subprocess.run(cmd_iscc, cwd=root)
    if res_iscc.returncode != 0:
        print("ERROR: Inno Setup compilation failed.")
        sys.exit(res_iscc.returncode)

    setup_file = dist_dir / "ClipMax_Studio_v2.6.0_Setup.exe"
    if setup_file.exists():
        mb_size = round(setup_file.stat().st_size / (1024 * 1024), 2)
        print(f"\n[SUCCESS] Installer built successfully!")
        print(f"          Path: {setup_file}")
        print(f"          Size: {mb_size} MB")
    else:
        print("ERROR: Output setup file not found.")

if __name__ == "__main__":
    build()
