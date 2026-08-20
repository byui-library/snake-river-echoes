import io

import pytest
from PIL import Image

from srebook.core import prepare
from tests.conftest import text_like_page


def test_straight_page_measures_as_straight():
    assert abs(prepare.measure_skew(text_like_page())) < 0.15


@pytest.mark.parametrize("applied", [1.2, -0.8])
def test_skew_is_measured_as_the_correction_needed(applied):
    """measure_skew returns the angle to rotate BY to straighten the page."""
    skewed = text_like_page(rotate=applied)

    assert abs(prepare.measure_skew(skewed) - (-applied)) < 0.3


def test_prepare_returns_both_derivatives_at_the_right_scale(make_sheet):
    sheet = prepare.prepare_sheet(make_sheet(), ocr_dpi=300, embed_dpi=200)

    ocr_w, ocr_h = sheet.ocr_image.size
    assert sheet.embed_size == (round(ocr_w * 2 / 3), round(ocr_h * 2 / 3))


def test_deskew_is_applied_to_both_derivatives(make_sheet):
    """The constraint the design hinges on. Rotating one and not the other puts
    the image out from under its own text layer -- a PDF that looks perfect and
    searches wrong."""
    sheet = prepare.prepare_sheet(make_sheet(rotate=1.0))

    assert sheet.skew_deg != 0.0, "a 1 degree skew should have been corrected"

    embed = Image.open(io.BytesIO(sheet.embed_jpeg))
    assert abs(prepare.measure_skew(sheet.ocr_image)) < 0.3
    assert abs(prepare.measure_skew(embed)) < 0.3


def test_skew_below_the_threshold_is_left_alone(make_sheet):
    """Rotating costs a resample. Not worth it for a tenth of a degree."""
    assert prepare.prepare_sheet(make_sheet(rotate=0.05)).skew_deg == 0.0


def test_deskew_preserves_page_geometry(make_sheet):
    """expand=False keeps one scale factor relating the two derivatives."""
    straight = prepare.prepare_sheet(make_sheet(name="a_1.tif"))
    skewed = prepare.prepare_sheet(make_sheet(name="b_1.tif", rotate=1.0))

    assert straight.ocr_image.size == skewed.ocr_image.size


def test_colour_scans_are_converted_to_grayscale(make_sheet):
    sheet = prepare.prepare_sheet(make_sheet(mode="RGB"))

    assert sheet.ocr_image.mode == "L"
    assert Image.open(io.BytesIO(sheet.embed_jpeg)).mode == "L"


def test_embed_jpeg_decodes_at_the_declared_size(make_sheet):
    sheet = prepare.prepare_sheet(make_sheet())

    assert Image.open(io.BytesIO(sheet.embed_jpeg)).size == sheet.embed_size


def test_embed_dpi_is_recorded_in_the_jpeg(make_sheet):
    sheet = prepare.prepare_sheet(make_sheet(), embed_dpi=200)

    assert Image.open(io.BytesIO(sheet.embed_jpeg)).info["dpi"] == (200, 200)


def test_embedding_at_source_resolution_is_allowed(make_sheet):
    """The embed DPI is a runtime dial; 300 must work as well as 200."""
    sheet = prepare.prepare_sheet(make_sheet(), ocr_dpi=300, embed_dpi=300)

    assert sheet.embed_size == sheet.ocr_image.size


def test_ocr_image_keeps_full_source_resolution(make_sheet):
    """OCR always reads 300 DPI. Downsampling first costs accuracy for nothing."""
    sheet = prepare.prepare_sheet(make_sheet(), embed_dpi=150)

    assert sheet.ocr_image.size == text_like_page().size


def test_unreadable_file_raises_a_readable_error(tmp_path):
    bad = tmp_path / "broken.tif"
    bad.write_bytes(b"not a tiff")

    with pytest.raises(prepare.PrepareError) as e:
        prepare.prepare_sheet(bad)

    assert "broken.tif" in str(e.value)
