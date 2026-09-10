"""Check that a built PDF's invisible text sits on the words in the picture.

    py packaging/verify_text_layer.py "Image Files/SRE Vol 4 Number 1"

This is the project's central guarantee and its worst failure mode: a text
layer that has slid off the image looks perfect on screen and searches wrong,
with nothing on the page to show it. Phase 0 established the figure once, by
hand, at 99.42% of words recoverable at their own location. This makes it
repeatable, so a change to how the two derivatives are produced can be checked
rather than trusted.

For every word the OCR found, it asks the finished PDF what text lies in that
word's own rectangle, and counts a hit when the word is there.

**What it does not catch.** Measured by shifting the query deliberately, a
12 pt offset drops the score to 1.4% and a 40 pt one to 0.95%, so gross
misalignment is caught loudly. A 3 pt offset still scores 99.97%. The 1.73 pt
systematic error Phase 0 found would pass here unnoticed; that class is held by
the unit test on baselines in tests/test_assemble.py. This check is for the
derivatives drifting apart, not for sub-pixel drift.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pypdfium2 as pdfium                            # noqa: E402

from srebook.core import ocr, pipeline               # noqa: E402
# Imported, never copied: a harness calibrated from its own constants keeps
# reporting PASS after the value under test changes, which is the one thing
# this check exists to prevent.
from srebook.core.assemble import OCR_DPI            # noqa: E402

PT_PER_PX = 72.0 / OCR_DPI
PAD_PT = 1.5          # a word's box is tight; allow a little either side


def normalise(text: str) -> str:
    """Compare on letters and digits alone.

    PDFium marks a hyphen at a line break with a control character rather
    than a hyphen: Phase 0 recorded U+FFFE, this build emits U+0002.
    Counting either as a mismatch reports every hyphenated word in an issue
    as misplaced -- 164 of them in Vol 1 No 2, which is the whole difference
    between 98% and 100%. Punctuation carries no location information, so
    only alphanumerics are compared.
    """
    return "".join(ch for ch in text if ch.isalnum()).lower()


def verify(folder: Path) -> int:
    sheets = pipeline._sheets(folder)
    pdf_path = pipeline.pdf_path(folder)
    if not pdf_path.exists():
        print(f"No built PDF at {pdf_path}. Build the issue first.")
        return 2

    doc = pdfium.PdfDocument(str(pdf_path))
    if len(doc) != len(sheets):
        print(f"PDF has {len(doc)} pages but the folder has {len(sheets)} sheets.")
        return 1

    cache = pipeline.cache_dir(folder)
    checked = found = 0
    worst: list[tuple[str, int]] = []

    for index, sheet in enumerate(sheets):
        hocr = cache / f"{sheet.stem}.hocr"
        if not hocr.exists():
            continue
        # parse_hocr has already dropped anything below ocr.MIN_CONFIDENCE.
        # A word of pure punctuation normalises to nothing, so there is no
        # letter to locate; counting it as a miss understates the result.
        words = [w for w in ocr.parse_hocr(hocr.read_bytes()) if normalise(w.text)]
        if not words:
            continue

        page = doc[index]
        height = page.get_height()
        textpage = page.get_textpage()
        hits = 0
        for w in words:
            left = w.x0 * PT_PER_PX - PAD_PT
            right = w.x1 * PT_PER_PX + PAD_PT
            top = height - w.y0 * PT_PER_PX + PAD_PT
            bottom = height - w.y1 * PT_PER_PX - PAD_PT
            got = textpage.get_text_bounded(left=left, bottom=bottom,
                                            right=right, top=top)
            if normalise(w.text) in normalise(got):
                hits += 1
        checked += len(words)
        found += hits
        rate = hits / len(words) if words else 1.0
        if rate < 0.95:
            worst.append((f"sheet {index + 1}", round(rate * 100)))

    if not checked:
        print("No OCR words cached for this issue.")
        return 2

    pct = found / checked * 100
    print(f"{folder.name}")
    print(f"  words checked      {checked}")
    print(f"  found in place     {found}  ({pct:.2f}%)")
    if worst:
        print(f"  weakest sheets     {worst[:6]}")
    print(f"  verdict            {'PASS' if pct >= 99.0 else 'FAIL'}  "
          f"(Phase 0 measured 99.42%)")
    return 0 if pct >= 99.0 else 1


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        raise SystemExit(2)
    raise SystemExit(verify(Path(sys.argv[1])))
