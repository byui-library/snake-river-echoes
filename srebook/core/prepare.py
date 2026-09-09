"""One TIFF -> the two derivatives the rest of the pipeline needs.

The OCR image keeps full source resolution because Tesseract is tuned for
300 DPI. The embedded image is downsampled because it is what determines file
size. Decoupling them is the reason this project composes its own text layer
instead of using Tesseract's PDF renderer.

Deskew is measured once and applied to BOTH. Applying it to one only would
rotate the image out from under its own text layer.
"""
from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, UnidentifiedImageError

DESKEW_LIMIT_DEG = 2.0    # scans are placed by hand; beyond this it is a misfeed
DESKEW_STEP_DEG = 0.1
DESKEW_MIN_DEG = 0.15     # below this, a resample costs more than it fixes
JPEG_QUALITY = 72

Image.MAX_IMAGE_PIXELS = None  # archival scans are legitimately large


class PrepareError(Exception):
    """A scan could not be read or converted, in terms a person can act on."""


@dataclass
class PreparedSheet:
    ocr_image: Image.Image
    embed_jpeg: bytes
    embed_size: tuple[int, int]
    skew_deg: float


def measure_skew(image: Image.Image) -> float:
    """The angle to rotate by to straighten the page, in degrees.

    Text lines make row-darkness strongly periodic. That periodicity peaks when
    the lines are horizontal, so the variance of the row sums is maximal at the
    correcting angle.
    """
    small = image.convert("L")
    small = small.resize((max(small.width // 4, 1), max(small.height // 4, 1)),
                         Image.BILINEAR)
    a = np.asarray(small, dtype=np.float32)
    ink = (a < a.mean() * 0.85)
    if ink.sum() < 100:
        return 0.0

    mask = Image.fromarray((ink * 255).astype(np.uint8), mode="L")
    best_angle, best_score = 0.0, -1.0
    angle = -DESKEW_LIMIT_DEG
    while angle <= DESKEW_LIMIT_DEG + 1e-9:
        rotated = np.asarray(
            mask.rotate(angle, resample=Image.BILINEAR, fillcolor=0), dtype=np.float32
        )
        score = float(np.var(rotated.sum(axis=1)))
        if score > best_score:
            best_score, best_angle = score, angle
        angle += DESKEW_STEP_DEG
    return round(best_angle, 2)


def prepare_sheet(path: Path, ocr_dpi: int = 300, embed_dpi: int = 200) -> PreparedSheet:
    path = Path(path)
    try:
        image = Image.open(path)
        image.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise PrepareError(f"Could not read the scan {path.name}: {exc}") from exc

    # Keep the colour the scanner captured. Most of this collection is in
    # colour, and converting everything to grey published forty years of a
    # county history journal in black and white for a 7% saving in file size.
    if image.mode == "RGBA":
        # JPEG cannot hold transparency, and RGBA is the commonest mode here.
        flat = Image.new("RGB", image.size, (255, 255, 255))
        flat.paste(image, mask=image.split()[3])
        image = flat
    elif image.mode not in ("L", "RGB"):
        image = image.convert("RGB")

    grey = image if image.mode == "L" else image.convert("L")
    skew = measure_skew(grey)
    if abs(skew) >= DESKEW_MIN_DEG:
        # expand=False keeps the two derivatives related by a single scale
        # factor, which is what lets hOCR coordinates map onto the embedded image.
        fill = 255 if image.mode == "L" else (255, 255, 255)
        image = image.rotate(skew, resample=Image.BICUBIC, fillcolor=fill,
                             expand=False)
    else:
        skew = 0.0

    # Derived from the rotated image rather than rotated separately, so the two
    # derivatives cannot drift apart and slide the text layer off the words.
    ocr_image = image if image.mode == "L" else image.convert("L")

    scale = embed_dpi / ocr_dpi
    embed_size = (round(image.width * scale), round(image.height * scale))
    embed = image if scale == 1 else image.resize(embed_size, Image.LANCZOS)

    buf = io.BytesIO()
    embed.save(buf, "JPEG", quality=JPEG_QUALITY, optimize=True,
               dpi=(embed_dpi, embed_dpi))

    return PreparedSheet(
        ocr_image=ocr_image,
        embed_jpeg=buf.getvalue(),
        embed_size=embed.size,
        skew_deg=skew,
    )
