"""
Build script for uXa Automator.

Usage:
    pip install pyinstaller pillow
    python build.py

Produces:
    Windows: dist/uXa Automator.exe
    macOS:   dist/uXa Automator.app  (then optionally wrap in .dmg)
"""

import subprocess
import sys
import platform
import os

from PIL import Image

SCRIPT = "auto_input.py"
NAME = "uXa Automator"
ICON_PNG = "uxa-no-background.png"
ICON_ICO = "uxa.ico"
ICON_ICNS = "uxa.icns"


def make_ico(src, dst):
    """Convert PNG to .ico for Windows."""
    img = Image.open(src)
    sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    img.save(dst, format="ICO", sizes=sizes)
    print(f"  Created {dst}")


def make_icns(src, dst):
    """Convert PNG to .icns for macOS using sips + iconutil."""
    iconset = "uxa.iconset"
    os.makedirs(iconset, exist_ok=True)

    img = Image.open(src)
    sizes = [16, 32, 64, 128, 256, 512]
    for s in sizes:
        resized = img.resize((s, s), Image.LANCZOS)
        resized.save(os.path.join(iconset, f"icon_{s}x{s}.png"))
        # @2x variant
        s2 = s * 2
        if s2 <= 1024:
            resized2 = img.resize((s2, s2), Image.LANCZOS)
            resized2.save(os.path.join(iconset, f"icon_{s}x{s}@2x.png"))

    subprocess.run(["iconutil", "-c", "icns", iconset, "-o", dst], check=True)
    print(f"  Created {dst}")

    # Clean up iconset
    import shutil
    shutil.rmtree(iconset)


def build():
    system = platform.system()
    print(f"Building uXa Automator for {system}...")

    # Generate platform icon
    if system == "Windows":
        print("Generating .ico...")
        make_ico(ICON_PNG, ICON_ICO)
        icon_flag = f"--icon={ICON_ICO}"
    elif system == "Darwin":
        print("Generating .icns...")
        make_icns(ICON_PNG, ICON_ICNS)
        icon_flag = f"--icon={ICON_ICNS}"
    else:
        icon_flag = ""

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--windowed",
        f"--name={NAME}",
        f"--add-data={ICON_PNG}{os.pathsep}.",
    ]

    if icon_flag:
        cmd.append(icon_flag)

    cmd.append(SCRIPT)

    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)

    if system == "Windows":
        exe_path = os.path.join("dist", f"{NAME}.exe")
        print(f"\nDone! Windows executable: {exe_path}")

    elif system == "Darwin":
        app_path = os.path.join("dist", f"{NAME}.app")
        print(f"\nDone! macOS app bundle: {app_path}")

        # Create .dmg
        dmg_path = os.path.join("dist", f"{NAME}.dmg")
        print(f"Creating DMG at {dmg_path}...")
        subprocess.run([
            "hdiutil", "create",
            "-volname", NAME,
            "-srcfolder", app_path,
            "-ov",
            "-format", "UDZO",
            dmg_path,
        ], check=True)
        print(f"Done! macOS DMG: {dmg_path}")

    else:
        bin_path = os.path.join("dist", NAME)
        print(f"\nDone! Linux binary: {bin_path}")


if __name__ == "__main__":
    build()
