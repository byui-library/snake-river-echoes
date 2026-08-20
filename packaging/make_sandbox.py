"""Write the Windows Sandbox configuration for the clean-machine test.

Generated rather than committed, because a .wsb file needs absolute host paths
and those differ per machine.

Windows Sandbox gives a pristine Windows that is discarded on close: no Python,
no Tesseract, no Visual C++ runtime beyond the base image. That is exactly the
machine an archive workstation looks like, and the only environment in which
"the installer works" means anything.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
# Outside dist/, because dist/ is mapped read-only and Sandbox does not
# handle a writable mapping nested inside a read-only one.
RESULTS = ROOT / "sandbox-results"

TEMPLATE = """<Configuration>
  <VGpu>Disable</VGpu>
  <Networking>Disable</Networking>
  <MappedFolders>
    <MappedFolder>
      <HostFolder>{install}</HostFolder>
      <SandboxFolder>C:\\install</SandboxFolder>
      <ReadOnly>true</ReadOnly>
    </MappedFolder>
    <MappedFolder>
      <HostFolder>{scans}</HostFolder>
      <SandboxFolder>C:\\scans</SandboxFolder>
      <ReadOnly>true</ReadOnly>
    </MappedFolder>
    <MappedFolder>
      <HostFolder>{results}</HostFolder>
      <SandboxFolder>C:\\results</SandboxFolder>
      <ReadOnly>false</ReadOnly>
    </MappedFolder>
  </MappedFolders>
  <LogonCommand>
    <Command>C:\\install\\sandbox_test.cmd</Command>
  </LogonCommand>
</Configuration>
"""


def main() -> int:
    installer = next(DIST.glob("SREBookBuilder-*-setup.exe"), None)
    if installer is None:
        raise SystemExit(
            "No installer found in dist/. Build it first:\n"
            "    py packaging/vendor_tesseract.py\n"
            "    py -m PyInstaller packaging/srebook.spec --noconfirm\n"
            '    "%LOCALAPPDATA%\\Programs\\Inno Setup 6\\ISCC.exe" packaging\\installer.iss'
        )

    scans = ROOT / "Image Files" / "SRE Vol 1 Number 1"
    if not scans.is_dir():
        raise SystemExit(f"Sample scans not found at {scans}")

    RESULTS.mkdir(parents=True, exist_ok=True)
    # The test script has to be inside a mapped folder to be runnable at logon.
    shutil.copy2(Path(__file__).parent / "sandbox_test.cmd", DIST / "sandbox_test.cmd")

    config = DIST / "clean-test.wsb"
    config.write_text(
        TEMPLATE.format(install=DIST, scans=scans, results=RESULTS), encoding="utf-8"
    )

    print(f"Wrote {config}")
    print(f"  installer   {installer.name} ({installer.stat().st_size / 1e6:.0f} MB)")
    print(f"  scans       {scans.name}")
    print(f"  results     {RESULTS}")
    print()
    print("Double-click the .wsb file. Windows Sandbox opens a pristine Windows,")
    print(f"installs the app, and runs the test. Results appear in {RESULTS}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
