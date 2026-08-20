"""Copy the parts of Tesseract the app actually needs into srebook/vendor/.

Run before PyInstaller. Everything copied here is Apache 2.0 and freely
redistributable, which is why the project uses Tesseract directly rather than
OCRmyPDF -- that route depends on Ghostscript, and AGPL obligations would follow
an installer handed to other institutions.

The training tools (lstmtraining, text2image and friends) are about 50 MB of
executables this app never invokes, so they are left behind.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

SOURCE_CANDIDATES = [
    Path(r"C:\Program Files\Tesseract-OCR"),
    Path(r"C:\Program Files (x86)\Tesseract-OCR"),
]
DEST = Path(__file__).resolve().parent.parent / "srebook" / "vendor" / "tesseract"

# English only. Each extra language is megabytes in the installer, and osd is
# needed only for orientation detection, which this app does not use -- it
# measures and corrects skew itself.
LANGUAGES = ["eng"]


def find_source() -> Path:
    for candidate in SOURCE_CANDIDATES:
        if (candidate / "tesseract.exe").exists():
            return candidate
    raise SystemExit(
        "Tesseract was not found. Install it first:\n"
        "    winget install --id UB-Mannheim.TesseractOCR"
    )


def main() -> int:
    source = find_source()
    if DEST.exists():
        shutil.rmtree(DEST)
    (DEST / "tessdata").mkdir(parents=True)

    shutil.copy2(source / "tesseract.exe", DEST / "tesseract.exe")

    # Every DLL: tesseract.exe needs most of them, and shipping a DLL we did not
    # need is far cheaper than a missing one that only shows up on a machine
    # without Tesseract installed.
    dlls = sorted(source.glob("*.dll"))
    for dll in dlls:
        shutil.copy2(dll, DEST / dll.name)

    for language in LANGUAGES:
        data = source / "tessdata" / f"{language}.traineddata"
        if not data.exists():
            raise SystemExit(f"Language data missing: {data}")
        shutil.copy2(data, DEST / "tessdata" / data.name)

    # tessdata/configs holds the output-mode config files. "hocr" on the command
    # line names configs/hocr, not a built-in flag -- without it Tesseract exits
    # 0, silently writes plain text instead, and the pipeline finds no .hocr.
    # 40 KB, and the app does not work without it.
    for folder in ("configs", "tessconfigs"):
        origin = source / "tessdata" / folder
        if origin.is_dir():
            shutil.copytree(origin, DEST / "tessdata" / folder)
    if not (DEST / "tessdata" / "configs" / "hocr").exists():
        raise SystemExit(
            f"tessdata/configs/hocr is missing from {source}. Without it "
            "Tesseract cannot produce hOCR and this app cannot read any scans."
        )

    for name in ("LICENSE", "COPYING", "README.md"):
        licence = source / name
        if licence.exists():
            shutil.copy2(licence, DEST / name)

    size = sum(f.stat().st_size for f in DEST.rglob("*") if f.is_file())
    print(f"vendored Tesseract from {source}")
    print(f"  tesseract.exe + {len(dlls)} DLLs + {len(LANGUAGES)} language(s)")
    print(f"  {size / 1e6:.0f} MB -> {DEST}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
