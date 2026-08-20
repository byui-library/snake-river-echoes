"""Build the installer, end to end.

    py packaging/build.py

Vendors Tesseract, freezes the app, compiles the installer and writes the
Windows Sandbox configuration for the clean-machine test.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ISCC_CANDIDATES = [
    Path.home() / "AppData/Local/Programs/Inno Setup 6/ISCC.exe",
    Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"),
    Path(r"C:\Program Files\Inno Setup 6\ISCC.exe"),
]


def step(number: int, title: str) -> None:
    print(f"\n=== {number}. {title} " + "=" * max(0, 52 - len(title)))


def run(command: list[str]) -> None:
    result = subprocess.run(command, cwd=ROOT)
    if result.returncode != 0:
        raise SystemExit(f"failed: {' '.join(str(c) for c in command)}")


def main() -> int:
    step(1, "vendor Tesseract")
    run([sys.executable, "packaging/vendor_tesseract.py"])

    step(2, "freeze the application")
    for stale in (ROOT / "dist" / "SREBookBuilder", ROOT / "build"):
        shutil.rmtree(stale, ignore_errors=True)
    run([sys.executable, "-m", "PyInstaller", "packaging/srebook.spec",
         "--noconfirm", "--distpath", "dist", "--workpath", "build"])

    step(3, "compile the installer")
    iscc = next((c for c in ISCC_CANDIDATES if c.exists()), None)
    if iscc is None:
        raise SystemExit(
            "Inno Setup not found. Install it:\n"
            "    winget install --id JRSoftware.InnoSetup"
        )
    run([str(iscc), "packaging/installer.iss"])

    step(4, "write the clean-machine test configuration")
    run([sys.executable, "packaging/make_sandbox.py"])

    installer = next((ROOT / "dist").glob("SREBookBuilder-*-setup.exe"))
    print(f"\nInstaller: {installer}  ({installer.stat().st_size / 1e6:.0f} MB)")
    print("Test it on a clean machine by double-clicking dist/clean-test.wsb")
    return 0


if __name__ == "__main__":
    sys.exit(main())
