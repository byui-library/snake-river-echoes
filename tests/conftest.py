"""Synthetic page scans, so the suite needs no checked-in image fixtures."""
import numpy as np
import pytest
from PIL import Image


def text_like_page(width=1200, height=1600, rotate=0.0, dpi=300):
    """A page of horizontal 'text' bars. Skew detection keys off exactly the
    structure real text has: strong horizontal periodicity."""
    a = np.full((height, width), 255, dtype=np.uint8)
    for row in range(200, height - 200, 40):
        for col in range(150, width - 150, 30):
            a[row:row + 14, col:col + 22] = 20
    img = Image.fromarray(a, mode="L")
    if rotate:
        img = img.rotate(rotate, resample=Image.BICUBIC, fillcolor=255, expand=False)
    return img


@pytest.fixture
def make_sheet(tmp_path):
    """Write a synthetic TIFF and return its path."""
    def _make(name="SRE_1971_Vol1_No1_01.tif", rotate=0.0, dpi=300, mode="L", **kw):
        img = text_like_page(rotate=rotate, dpi=dpi, **kw)
        if mode != "L":
            img = img.convert(mode)
        path = tmp_path / name
        img.save(path, "TIFF", compression="tiff_lzw", dpi=(dpi, dpi))
        return path
    return _make
