"""Sizing for the sheet preview.

Kept free of tkinter so the rule can be tested without a display: the preview
must fill whatever space the operator gives it, because the fixed 300px version
was too small for most people to read.
"""
import pytest

from srebook.gui import preview


def test_a_tall_scan_in_a_wide_box_is_limited_by_height():
    assert preview.fit_within((2272, 3302), (2000, 800)) == (550, 800)


def test_a_tall_scan_in_a_narrow_box_is_limited_by_width():
    assert preview.fit_within((2272, 3302), (400, 5000)) == (400, 581)


def test_aspect_ratio_is_preserved():
    w, h = preview.fit_within((2272, 3302), (900, 900))

    assert abs((w / h) - (2272 / 3302)) < 0.01


def test_the_preview_grows_when_the_pane_grows():
    small = preview.fit_within((2272, 3302), (300, 400))
    large = preview.fit_within((2272, 3302), (900, 1200))

    assert large[0] > small[0] and large[1] > small[1]


def test_it_never_upscales_past_the_scan_itself():
    """Blowing a 300 DPI page up beyond its own pixels just looks soft."""
    assert preview.fit_within((800, 1000), (4000, 5000)) == (800, 1000)


def test_a_degenerate_box_still_returns_something_drawable():
    w, h = preview.fit_within((2272, 3302), (0, 0))

    assert w >= 1 and h >= 1


@pytest.mark.parametrize("box", [(200, 300), (1000, 700), (640, 480)])
def test_the_result_always_fits_inside_the_box(box):
    w, h = preview.fit_within((2272, 3302), box)

    assert w <= max(box[0], 1) and h <= max(box[1], 1)
