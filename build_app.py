#!/usr/bin/env python3
"""Build 'SKP Converter.app' — a native macOS GUI app.

Run once from this project directory:
    python3 build_app.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent.resolve()
APP_NAME = "SKP Converter"
APP_PATH = HERE / f"{APP_NAME}.app"

CONTENTS   = APP_PATH / "Contents"
MACOS_DIR  = CONTENTS / "MacOS"
RES_DIR    = CONTENTS / "Resources"

SCRIPTS_TO_BUNDLE = ["converter_app.py", "img_to_skm.py"]


def _find_python() -> str:
    """Return the macOS framework GUI Python that has Pillow installed.

    Must use the Python.app/Contents/MacOS/Python binary — the regular
    python3 binary cannot register as a GUI app when exec'd from an app bundle.
    """
    # Framework GUI binaries (required for window server access from .app bundles)
    framework_gui_candidates = [
        "/Library/Frameworks/Python.framework/Versions/3.13/Resources/Python.app/Contents/MacOS/Python",
        "/Library/Frameworks/Python.framework/Versions/3.12/Resources/Python.app/Contents/MacOS/Python",
        "/Library/Frameworks/Python.framework/Versions/3.11/Resources/Python.app/Contents/MacOS/Python",
    ]
    for candidate in framework_gui_candidates:
        if os.path.exists(candidate):
            result = subprocess.run([candidate, "-c", "import PIL"],
                                    capture_output=True)
            if result.returncode == 0:
                return candidate

    # Fallback to regular python3 if framework binary not available
    for candidate in [
        "/usr/local/bin/python3",
        "/opt/homebrew/bin/python3",
        sys.executable,
    ]:
        if subprocess.run([candidate, "-c", "import PIL"],
                         capture_output=True).returncode == 0:
            print(f"Warning: using non-framework Python ({candidate}) — app may not launch from Finder.")
            return candidate

    sys.exit("Could not find Python 3 with Pillow.\nRun:  pip3 install Pillow")


def build() -> None:
    for name in SCRIPTS_TO_BUNDLE:
        if not (HERE / name).exists():
            sys.exit(f"{name} not found in {HERE}")

    python_bin = _find_python()
    print(f"Using Python: {python_bin}")

    # Remove old bundle
    if APP_PATH.exists():
        shutil.rmtree(APP_PATH)

    # Create directory structure
    MACOS_DIR.mkdir(parents=True)
    RES_DIR.mkdir(parents=True)

    # Copy Python scripts into Resources
    for name in SCRIPTS_TO_BUNDLE:
        shutil.copy2(HERE / name, RES_DIR / name)

    # Write the launcher shell script.
    # No `exec` — bash must stay alive as the parent so macOS keeps the
    # app-bundle association (dock icon, window-server access).
    launcher = MACOS_DIR / APP_NAME
    launcher.write_text(
        f"""#!/bin/bash
DIR="$(cd "$(dirname "$0")/../Resources" && pwd)"
"{python_bin}" "$DIR/converter_app.py" "$@"
""",
        encoding="utf-8"
    )
    launcher.chmod(0o755)

    # Write Info.plist
    (CONTENTS / "Info.plist").write_text(
        f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>          <string>{APP_NAME}</string>
    <key>CFBundleDisplayName</key>   <string>{APP_NAME}</string>
    <key>CFBundleExecutable</key>    <string>{APP_NAME}</string>
    <key>CFBundleIdentifier</key>    <string>com.local.skp-converter</string>
    <key>CFBundleVersion</key>       <string>1.0</string>
    <key>CFBundlePackageType</key>   <string>APPL</string>
    <key>LSMinimumSystemVersion</key><string>12.0</string>
    <key>NSHighResolutionCapable</key><true/>
</dict>
</plist>
""",
        encoding="utf-8"
    )

    # Ad-hoc sign the app so macOS Gatekeeper allows double-click launches.
    # The "-" identity requires no Apple Developer account.
    print("Signing…")
    sign = subprocess.run(
        ["codesign", "--force", "--deep", "--sign", "-", str(APP_PATH)],
        capture_output=True, text=True
    )
    if sign.returncode != 0:
        print(f"  Warning: codesign failed — {sign.stderr.strip()}")
        print("  The app may still work; try right-click → Open if double-click fails.")
    else:
        print("✓  Signed (ad-hoc)")

    # Clear any quarantine flags macOS may have set
    subprocess.run(["xattr", "-cr", str(APP_PATH)], capture_output=True)

    print(f"\n✓  Ready: {APP_PATH}")
    print("Double-click SKP Converter.app in Finder to launch.")


if __name__ == "__main__":
    build()
