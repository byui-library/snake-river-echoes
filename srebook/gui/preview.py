"""Sizing for the sheet preview.

No tkinter here, so the rule is testable without a display.

The preview exists so the operator can confirm an article really starts on the
sheet a bookmark claims. A fixed-width thumbnail was too small to read, which
defeats the point -- it has to fill whatever space the window gives it.
"""
from __future__ import annotations


def fit_within(image_size: tuple[int, int], box: tuple[int, int]) -> tuple[int, int]:
    """The largest size that fits `box` while keeping the scan's proportions.

    Never enlarges past the scan's own pixels: blowing a 300 DPI page up beyond
    its resolution only makes it soft, and the operator is reading small print.
    """
    width, height = image_size
    box_width, box_height = max(box[0], 1), max(box[1], 1)
    if width <= 0 or height <= 0:
        return 1, 1

    scale = min(box_width / width, box_height / height, 1.0)
    return max(round(width * scale), 1), max(round(height * scale), 1)
