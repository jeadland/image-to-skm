#!/usr/bin/env python3
"""Build 'SKP Converter.app' using py2app.

Run once from this project directory:
    python3 build_app.py

Requires: pip3 install py2app Pillow
"""

import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent.resolve()
APP_NAME = "SKP Converter"
DIST_APP = HERE / "dist" / f"{APP_NAME}.app"
DESKTOP_APP = Path.home() / "Desktop" / f"{APP_NAME}.app"


def build() -> None:
    for name in ["converter_app.py", "img_to_skm.py", "setup.py"]:
        if not (HERE / name).exists():
            sys.exit(f"{name} not found in {HERE}")

    # Clean previous builds
    for d in ["build", "dist"]:
        p = HERE / d
        if p.exists():
            shutil.rmtree(p)

    # Build with py2app
    print("Building with py2app…")
    result = subprocess.run(
        [sys.executable, "setup.py", "py2app"],
        cwd=str(HERE), capture_output=True, text=True
    )
    if result.returncode != 0:
        print(result.stderr)
        sys.exit("py2app build failed.")

    if not DIST_APP.exists():
        sys.exit(f"Build did not produce {DIST_APP}")

    # Ad-hoc sign so macOS Gatekeeper allows double-click launches
    print("Signing…")
    sign = subprocess.run(
        ["codesign", "--force", "--deep", "--sign", "-", str(DIST_APP)],
        capture_output=True, text=True
    )
    if sign.returncode != 0:
        print(f"  Warning: codesign failed — {sign.stderr.strip()}")
    else:
        print("✓  Signed (ad-hoc)")

    # Clear quarantine flags
    subprocess.run(["xattr", "-cr", str(DIST_APP)], capture_output=True)

    # Copy to Desktop for reliable launching (avoids Launch Services cache
    # issues from repeated rebuilds in the project directory)
    if DESKTOP_APP.exists():
        shutil.rmtree(DESKTOP_APP)
    shutil.copytree(DIST_APP, DESKTOP_APP)
    subprocess.run(["xattr", "-cr", str(DESKTOP_APP)], capture_output=True)

    print(f"\n✓  Ready: {DESKTOP_APP}")
    print("Double-click SKP Converter.app on your Desktop to launch.")


if __name__ == "__main__":
    build()
