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


def test_a_colour_scan_is_read_in_grey_and_embedded_in_colour(make_sheet):
    """The two derivatives exist to differ. Tesseract wants grey; the book
    should carry the colour the scanner captured. This test asserted the
    embedded image was grey too, which published a colour collection in black
    and white."""
    sheet = prepare.prepare_sheet(make_sheet(mode="RGB"))

    assert sheet.ocr_image.mode == "L"
    assert Image.open(io.BytesIO(sheet.embed_jpeg)).mode == "RGB"


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


# ------------------------------------------------------------- colour ----
# Every scan was converted to greyscale, which was right when the whole
# corpus was 1971 typescript. 64 of the 73 folders are colour, and their
# published books were coming out black and white.

def _colour_page(tmp_path, name="colour.tif", mode="RGB"):
    grey = text_like_page()
    page = Image.merge("RGB", (grey, grey.point(lambda v: min(255, v + 60)), grey))
    if mode == "RGBA":
        page = page.convert("RGBA")
    path = tmp_path / name
    page.save(path, dpi=(300, 300))
    return path


def test_a_colour_scan_is_embedded_in_colour(tmp_path):
    sheet = prepare.prepare_sheet(_colour_page(tmp_path))

    embedded = Image.open(io.BytesIO(sheet.embed_jpeg))

    assert embedded.mode == "RGB"


def test_a_scan_with_transparency_is_embedded_in_colour(tmp_path):
    """RGBA is the commonest mode in this collection; JPEG cannot hold alpha."""
    sheet = prepare.prepare_sheet(_colour_page(tmp_path, "alpha.tif", "RGBA"))

    embedded = Image.open(io.BytesIO(sheet.embed_jpeg))

    assert embedded.mode == "RGB"


def test_a_greyscale_scan_stays_greyscale(tmp_path):
    path = tmp_path / "grey.tif"
    text_like_page().save(path, dpi=(300, 300))

    sheet = prepare.prepare_sheet(path)

    assert Image.open(io.BytesIO(sheet.embed_jpeg)).mode == "L"


def test_ocr_still_reads_greyscale_whatever_the_source(tmp_path):
    """Tesseract is tuned for greyscale, and the text layer must not change
    because a scan happens to be in colour."""
    sheet = prepare.prepare_sheet(_colour_page(tmp_path))

    assert sheet.ocr_image.mode == "L"


def test_the_deskew_angle_is_applied_to_the_colour_image_too(tmp_path):
    """Rotating one derivative and not the other slides the invisible text off
    the words -- the worst failure this project has."""
    grey = text_like_page(rotate=1.0)
    page = Image.merge("RGB", (grey, grey, grey))
    path = tmp_path / "skewed.tif"
    page.save(path, dpi=(300, 300))

    sheet = prepare.prepare_sheet(path)

    assert abs(sheet.skew_deg) >= prepare.DESKEW_MIN_DEG
    embedded = Image.open(io.BytesIO(sheet.embed_jpeg)).convert("L")
    # Straightened: row darkness is far more periodic than in the skewed source.
    import numpy as np
    straight = float(np.var(np.asarray(embedded, dtype=np.float32).sum(axis=1)))
    skewed = float(np.var(np.asarray(page.convert("L").resize(embedded.size),
                                     dtype=np.float32).sum(axis=1)))
    assert straight > skewed
