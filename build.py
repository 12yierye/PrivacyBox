"""PrivacyBox build script — PyInstaller + installer packaging.

Usage:
    python build.py                    Build PyInstaller exe (all platforms)
    python build.py --installer        Build PyInstaller exe + platform installer
    python build.py --installer-only   Build only the installer (assumes exe exists)
    python build.py --clean            Clean build artifacts
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
DIST = ROOT / "dist"
BUILD = ROOT / "build"
SPEC = ROOT / "privacybox.spec"

PYINSTALLER_ARGS = [
    sys.executable, "-m", "PyInstaller",
    str(SPEC),
    "--clean",
    "--noconfirm",
]


def banner(msg: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {msg}")
    print(f"{'='*60}")


def build_pyinstaller() -> None:
    banner("Building PrivacyBox with PyInstaller")
    subprocess.check_call(PYINSTALLER_ARGS, cwd=str(ROOT))


def build_installer_windows() -> None:
    banner("Building Windows installer with Inno Setup")
    iss = ROOT / "installer" / "windows" / "setup.iss"
    if not iss.exists():
        print(f"[SKIP] {iss} not found")
        return
    iscc = shutil.which("iscc")
    if not iscc:
        print("[SKIP] Inno Setup (iscc) not found in PATH")
        return
    subprocess.check_call([iscc, str(iss)], cwd=str(ROOT))


def build_installer_macos() -> None:
    banner("Building macOS installer")
    script = ROOT / "installer" / "macos" / "build_pkg.sh"
    if not script.exists():
        print(f"[SKIP] {script} not found")
        return
    subprocess.check_call(["bash", str(script)], cwd=str(ROOT))


def build_installer_linux() -> None:
    banner("Building Linux .deb + AppImage")
    script = ROOT / "installer" / "linux" / "build_deb.sh"
    if not script.exists():
        print(f"[SKIP] {script} not found")
        return
    subprocess.check_call(["bash", str(script)], cwd=str(ROOT))


def clean() -> None:
    banner("Cleaning build artifacts")
    for d in [BUILD, DIST]:
        if d.exists():
            shutil.rmtree(d)
            print(f"  Removed {d}")
    for f in ROOT.glob("*.spec"):
        if f.name != "privacybox.spec":
            f.unlink()
    pycache = ROOT / "__pycache__"
    if pycache.exists():
        shutil.rmtree(pycache)
    print("  Done")


def main() -> None:
    parser = argparse.ArgumentParser(description="PrivacyBox build script")
    parser.add_argument("--installer", action="store_true", help="Also build platform installer")
    parser.add_argument("--installer-only", action="store_true", help="Only build installer (exe must exist)")
    parser.add_argument("--clean", action="store_true", help="Clean build artifacts")
    args = parser.parse_args()

    if args.clean:
        clean()
        return

    if args.installer_only:
        pass
    else:
        build_pyinstaller()

    platform = sys.platform
    if args.installer or args.installer_only:
        if platform == "win32":
            build_installer_windows()
        elif platform == "darwin":
            build_installer_macos()
        else:
            build_installer_linux()
    else:
        print(f"\nTip: run 'python build.py --installer' to also build the platform installer")

    banner("Build complete")


if __name__ == "__main__":
    main()
