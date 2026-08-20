# PyInstaller spec: one folder holding both the window and the command line.
#
# A onedir build rather than onefile: onefile unpacks 170 MB of Tesseract to a
# temp folder on every launch, which is slow and looks like a hang.
#
# Run from the repository root:
#     py packaging/vendor_tesseract.py
#     py -m PyInstaller packaging/srebook.spec --noconfirm

from pathlib import Path

ROOT = Path(SPECPATH).parent
VENDOR = ROOT / "srebook" / "vendor" / "tesseract"

if not (VENDOR / "tesseract.exe").exists():
    raise SystemExit(
        "Tesseract has not been vendored yet. Run:\n"
        "    py packaging/vendor_tesseract.py"
    )

# Tesseract is deliberately NOT handed to PyInstaller. PyInstaller reclassifies
# loose DLLs as binaries and copies them to _internal/ as well as the data
# destination -- 130 MB duplicated, for no benefit. The installer lays the
# vendored folder down beside the exe instead, and ocr.bundle_candidates looks
# there first.
vendor_data = []

hidden = [
    "PIL._tkinter_finder",   # ImageTk, for the preview pane
    "lxml._elementpath",     # lxml imports this dynamically
]

excluded = [
    "pytest", "pypdfium2",   # test-only
    "matplotlib", "scipy", "pandas", "IPython", "notebook",
]

gui = Analysis(
    [str(ROOT / "packaging" / "launch_gui.py")],
    pathex=[str(ROOT)],
    datas=vendor_data,
    hiddenimports=hidden,
    excludes=excluded,
    noarchive=False,
)

cli = Analysis(
    [str(ROOT / "packaging" / "launch_cli.py")],
    pathex=[str(ROOT)],
    datas=[],                # shares the GUI's vendored Tesseract in COLLECT
    hiddenimports=hidden,
    excludes=excluded + ["tkinter"],
    noarchive=False,
)

MERGE((gui, "launch_gui", "SREBookBuilder"), (cli, "launch_cli", "srebook"))

gui_pyz = PYZ(gui.pure)
cli_pyz = PYZ(cli.pure)

gui_exe = EXE(
    gui_pyz, gui.scripts, [],
    exclude_binaries=True,
    name="SREBookBuilder",
    console=False,            # archive staff should not see a console window
)

cli_exe = EXE(
    cli_pyz, cli.scripts, [],
    exclude_binaries=True,
    name="srebook",
    console=True,             # the CLI is only useful with its output visible
)

COLLECT(
    gui_exe, gui.binaries, gui.datas,
    cli_exe, cli.binaries, cli.datas,
    strip=False,
    upx=False,                # UPX on 170 MB of DLLs trips antivirus heuristics
    name="SREBookBuilder",
)
