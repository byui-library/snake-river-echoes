"""Tesseract, and the hOCR it produces.

hOCR carries word text plus pixel coordinates. Composing the PDF text layer from
those coordinates -- rather than letting Tesseract render the PDF -- is what lets
OCR read 300 DPI while the page embeds 200 DPI.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from lxml import html as lxml_html
from PIL import Image

MIN_CONFIDENCE = 30  # below this Tesseract is reading noise, not type
LINE_CLASSES = ("ocr_line", "ocr_header", "ocr_caption", "ocr_textfloat")

_BBOX = re.compile(r"bbox (\d+) (\d+) (\d+) (\d+)")
_CONF = re.compile(r"x_wconf (\d+)")
_BASELINE = re.compile(r"baseline ([-\d.]+) ([-\d.]+)")

_WINDOWS_TESSERACT = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


class OcrError(Exception):
    """OCR could not run, in terms a person can act on."""


@dataclass
class Word:
    text: str
    x0: int
    y0: int
    x1: int
    y1: int
    confidence: int
    baseline_y: float

    @property
    def ascent(self) -> float:
        """Height above the baseline. Font size derives from this, not from the
        full box, which also spans descenders."""
        return max(self.baseline_y - self.y0, 1.0)


def find_tesseract() -> str | None:
    """The Tesseract binary: bundled beside the app, on PATH, or installed."""
    bundled = Path(__file__).resolve().parent.parent / "vendor" / "tesseract" / "tesseract.exe"
    if bundled.exists():
        return str(bundled)
    if env := os.environ.get("SREBOOK_TESSERACT"):
        if Path(env).exists():
            return env
    if found := shutil.which("tesseract"):
        return found
    if Path(_WINDOWS_TESSERACT).exists():
        return _WINDOWS_TESSERACT
    return None


def run_tesseract(image: Image.Image, cache_dir: Path, key: str,
                  dpi: int = 300, language: str = "eng") -> bytes:
    """OCR one image to hOCR, caching by `key`.

    OCR is the slow stage. Everything downstream is rebuilt from the cache, so
    editing a bookmark and rebuilding never re-OCRs.
    """
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cached = cache_dir / f"{key}.hocr"
    if cached.exists():
        return cached.read_bytes()

    binary = find_tesseract()
    if binary is None:
        raise OcrError(
            "Tesseract could not be found. It is normally installed alongside "
            "this program; set SREBOOK_TESSERACT to its location if it lives "
            "somewhere else."
        )

    tmp = cache_dir / f"{key}.ocr-input.png"
    image.save(tmp, "PNG")
    try:
        subprocess.run(
            [binary, str(tmp), str(cache_dir / key), "--dpi", str(dpi),
             "-l", language, "hocr"],
            check=True, capture_output=True,
        )
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.decode("utf-8", "replace").strip().splitlines()
        raise OcrError(
            f"Tesseract could not read this page: {detail[-1] if detail else exc}"
        ) from exc
    finally:
        tmp.unlink(missing_ok=True)

    return cached.read_bytes()


def _lines(data: bytes):
    root = lxml_html.fromstring(data)
    predicate = " or ".join(f"@class='{c}'" for c in LINE_CLASSES)
    return root.xpath(f"//*[{predicate}]")


def parse_hocr(data: bytes, min_confidence: int = MIN_CONFIDENCE) -> list[Word]:
    """hOCR -> words, in reading order, with a usable baseline for each."""
    words: list[Word] = []
    for line in _lines(data):
        title = line.get("title", "")
        line_box = _BBOX.search(title)
        if not line_box:
            continue
        lx0, _ly0, _lx1, ly1 = (int(g) for g in line_box.groups())
        bl = _BASELINE.search(title)
        slope, offset = (float(bl.group(1)), float(bl.group(2))) if bl else (0.0, 0.0)

        for el in line.xpath(".//*[@class='ocrx_word']"):
            wtitle = el.get("title", "")
            box = _BBOX.search(wtitle)
            if not box:
                continue
            text = "".join(el.itertext()).strip()
            if not text:
                continue
            conf_match = _CONF.search(wtitle)
            confidence = int(conf_match.group(1)) if conf_match else -1
            if confidence < min_confidence:
                continue

            x0, y0, x1, y1 = (int(g) for g in box.groups())
            baseline_y = ly1 + offset + slope * ((x0 + x1) / 2 - lx0)
            # A baseline above the word's own top, or far below its descender,
            # is nonsense -- fall back to the box bottom rather than propagate it.
            if not y0 < baseline_y <= y1 + (y1 - y0):
                baseline_y = float(y1)

            words.append(Word(text, x0, y0, x1, y1, confidence, baseline_y))
    return words


def text_lines(data: bytes) -> list[str]:
    """The page as lines of text. The outline parser works on lines."""
    out = []
    for line in _lines(data):
        text = " ".join(
            "".join(w.itertext()).strip()
            for w in line.xpath(".//*[@class='ocrx_word']")
        )
        text = re.sub(r"\s+", " ", text).strip()
        if text:
            out.append(text)
    return out
