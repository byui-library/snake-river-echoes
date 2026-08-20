import shutil

import pytest

from srebook.core import ocr


def hocr(lines: str) -> bytes:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml"><body>
 <div class='ocr_page' id='page_1' title='bbox 0 0 2272 3302'>
  <div class='ocr_carea' id='block_1_1' title="bbox 100 200 900 400">
   <p class='ocr_par' title="bbox 100 200 900 400">
{lines}
   </p></div></div></body></html>""".encode("utf-8")


def line(words, bbox="100 200 900 240", baseline="baseline 0 -9", cls="ocr_line"):
    inner = "".join(
        f"<span class='ocrx_word' title='bbox {b}; x_wconf {c}'>{t}</span>"
        for t, b, c in words
    )
    return f"<span class='{cls}' title=\"bbox {bbox}; {baseline}\">{inner}</span>"


def test_reads_word_text_and_box():
    words = ocr.parse_hocr(hocr(line([("Andrew", "100 200 300 240", 96)])))

    assert len(words) == 1
    w = words[0]
    assert (w.text, w.x0, w.y0, w.x1, w.y1, w.confidence) == ("Andrew", 100, 200, 300, 240, 96)


def test_baseline_comes_from_the_enclosing_line_not_the_word_box():
    """hOCR word boxes span ascender to descender. Text must be SET on the
    baseline; using the box bottom put every word a descender's depth low."""
    words = ocr.parse_hocr(hocr(line([("Andrew", "100 200 300 240", 96)],
                                     bbox="100 200 900 240",
                                     baseline="baseline 0 -9")))

    # line bottom 240, offset -9
    assert words[0].baseline_y == pytest.approx(231.0)


def test_baseline_slope_tilts_across_the_line():
    """A slightly rotated line has a sloped baseline; words further right sit lower."""
    words = ocr.parse_hocr(hocr(
        line([("left", "100 200 200 240", 90), ("right", "800 200 900 240", 90)],
             bbox="100 200 900 240", baseline="baseline 0.01 -10")))

    left, right = words
    assert right.baseline_y > left.baseline_y
    # centres are 150 and 850, so 700 px apart at slope 0.01
    assert right.baseline_y - left.baseline_y == pytest.approx(7.0, abs=0.01)


def test_missing_baseline_falls_back_to_the_box_bottom():
    words = ocr.parse_hocr(hocr(line([("x", "100 200 300 240", 90)], baseline="")))

    assert words[0].baseline_y == 240


def test_implausible_baseline_falls_back_to_the_box_bottom():
    """A baseline above the word's own top is nonsense; don't propagate it."""
    words = ocr.parse_hocr(hocr(line([("x", "100 200 300 240", 90)],
                                     baseline="baseline 0 -500")))

    assert words[0].baseline_y == 240


def test_low_confidence_words_are_dropped():
    """Non-text pages generate noise words that pollute search."""
    words = ocr.parse_hocr(hocr(line([("real", "100 200 300 240", 90),
                                      ("nois", "310 200 400 240", 12)])))

    assert [w.text for w in words] == ["real"]


def test_confidence_floor_is_configurable():
    words = ocr.parse_hocr(hocr(line([("x", "100 200 300 240", 40)])), min_confidence=50)

    assert words == []


def test_empty_and_whitespace_words_are_dropped():
    words = ocr.parse_hocr(hocr(line([("", "100 200 300 240", 90),
                                      ("   ", "310 200 400 240", 90),
                                      ("ok", "410 200 500 240", 90)])))

    assert [w.text for w in words] == ["ok"]


def test_headings_and_captions_are_read_too():
    """Article titles are ocr_header, and they are what the outline needs most."""
    words = ocr.parse_hocr(hocr(
        line([("ANDREW", "100 200 300 240", 96)], cls="ocr_header")
        + line([("caption", "100 300 300 340", 96)], cls="ocr_caption")))

    assert [w.text for w in words] == ["ANDREW", "caption"]


def test_typographic_characters_survive_parsing():
    words = ocr.parse_hocr(hocr(line([("Snake’s", "100 200 300 240", 96)])))

    assert words[0].text == "Snake’s"


def test_page_with_no_words_parses_to_nothing():
    assert ocr.parse_hocr(hocr("")) == []


def test_text_of_returns_reading_order_lines():
    """The outline parser works on lines, not loose words."""
    data = hocr(line([("A", "100 200 150 240", 90), ("GOAL", "160 200 300 240", 90)])
                + line([("The", "100 300 150 340", 90)], bbox="100 300 900 340"))

    assert ocr.text_lines(data) == ["A GOAL", "The"]


# ------------------------------------------------------------- integration ----

needs_tesseract = pytest.mark.skipif(
    ocr.find_tesseract() is None, reason="Tesseract is not installed"
)


@needs_tesseract
def test_tesseract_reads_rendered_text(tmp_path):
    from PIL import Image, ImageDraw

    img = Image.new("L", (1200, 300), 255)
    ImageDraw.Draw(img).text((40, 100), "ANDREW HENRY", fill=0)
    img = img.resize((2400, 600), Image.LANCZOS)

    words = ocr.parse_hocr(ocr.run_tesseract(img, cache_dir=tmp_path, key="t1"))

    assert "ANDREW" in " ".join(w.text for w in words).upper()


@needs_tesseract
def test_second_run_uses_the_cache(tmp_path):
    """OCR is the slow stage; re-running a build must not repeat it."""
    from PIL import Image

    img = Image.new("L", (600, 200), 255)
    ocr.run_tesseract(img, cache_dir=tmp_path, key="k")
    cached = tmp_path / "k.hocr"
    cached.write_bytes(b"<html><body>sentinel</body></html>")

    assert ocr.run_tesseract(img, cache_dir=tmp_path, key="k") == cached.read_bytes()


def test_missing_tesseract_raises_a_readable_error(tmp_path, monkeypatch):
    monkeypatch.setattr(ocr, "find_tesseract", lambda: None)
    from PIL import Image

    with pytest.raises(ocr.OcrError) as e:
        ocr.run_tesseract(Image.new("L", (10, 10)), cache_dir=tmp_path, key="k")

    assert "Tesseract" in str(e.value)
