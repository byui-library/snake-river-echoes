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
      <HostFolder>{gappy}</HostFolder>
      <SandboxFolder>C:\\scans-with-a-gap</SandboxFolder>
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


def check_script(path):
    """Refuse to stage a test script with a control character in it.

    An editing slip once turned "C:\\results" into "C:" plus a carriage return,
    so the gap check wrote its output to a path that did not exist and reported
    a failure that was the harness's fault, not the program's. A test that can
    lie about the thing it is testing is worse than no test.
    """
    # newline="" matters: the default translates a lone carriage return into a
    # newline, so the very mangling this looks for would be tidied away before
    # it could be seen.
    with path.open(encoding="utf-8", newline="") as handle:
        text = handle.read()
    # chr() rather than escape sequences: this check was itself written with
    # "\n\r\t" that arrived as literal backslash-letter pairs, so it flagged
    # every newline in the file. The guard fell to the bug it exists to catch.
    allowed = {10, 13, 9}
    stray = {hex(ord(c)) for c in text if ord(c) < 32 and ord(c) not in allowed}
    if stray:
        raise SystemExit(f"{path} contains stray control characters {stray}. "
                         "Rewrite the file rather than shipping it.")

    # A carriage return belongs only immediately before a newline. One loose in
    # the middle of a line is an escape that was eaten -- which is exactly how
    # "C:\\results" became "C:" plus a carriage return, sending the gap check's
    # output to a path that did not exist.
    for number, line in enumerate(text.split(chr(10)), start=1):
        if chr(13) in line.rstrip(chr(13)):
            raise SystemExit(
                f"{path} line {number} has a carriage return inside it, so a "
                "path or string was mangled. Rewrite the file rather than "
                "shipping it.")
    for expected in ("C:" + chr(92) + "results", "C:" + chr(92) + "install",
                     "C:" + chr(92) + "scans"):
        if expected not in text:
            raise SystemExit(f"{path} no longer mentions {expected}; "
                             "a path may have been mangled.")


def newest_installer(folder):
    """The installer just built, not whichever one the glob happens to yield.

    An older build left beside a new one was being picked up: the build script
    printed the wrong version, and the clean-machine test would have installed
    a stale binary and reported it as passing.
    """
    found = sorted(folder.glob("SREBookBuilder-*-setup.exe"),
                   key=lambda p: p.stat().st_mtime, reverse=True)
    return found[0] if found else None


def main() -> int:
    installer = newest_installer(DIST)
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

    # An issue known to be missing pages 27 and 28, so the clean machine test
    # exercises the missing-page warning rather than only the happy path.
    gappy = ROOT / "Image Files" / "SRE Vol 1 Number 2"
    if not gappy.is_dir():
        raise SystemExit(f"Sample scans not found at {gappy}")

    RESULTS.mkdir(parents=True, exist_ok=True)
    # The test script has to be inside a mapped folder to be runnable at logon.
    script = Path(__file__).parent / "sandbox_test.cmd"
    check_script(script)
    shutil.copy2(script, DIST / "sandbox_test.cmd")

    config = DIST / "clean-test.wsb"
    config.write_text(
        TEMPLATE.format(install=DIST, scans=scans, gappy=gappy, results=RESULTS),
        encoding="utf-8"
    )

    print(f"Wrote {config}")
    print(f"  installer   {installer.name} ({installer.stat().st_size / 1e6:.0f} MB)")
    print(f"  scans       {scans.name}")
    print(f"  gap check   {gappy.name}  (missing pages 27, 28)")
    print(f"  results     {RESULTS}")
    print()
    print("Double-click the .wsb file. Windows Sandbox opens a pristine Windows,")
    print(f"installs the app, and runs the test. Results appear in {RESULTS}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
