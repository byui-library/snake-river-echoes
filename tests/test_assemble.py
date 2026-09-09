import io

import pikepdf
import pytest
from PIL import Image

from srebook.core import assemble
from srebook.core.model import Bookmark, Issue
from srebook.core.ocr import Word

pdfium = pytest.importorskip("pypdfium2")

OCR_DPI = 300
PT_PER_PX = 72.0 / OCR_DPI


def jpeg(size):
    buf = io.BytesIO()
    Image.new("L", size, 240).save(buf, "JPEG", quality=70)
    return buf.getvalue()


def word(text, x0, y0, x1, y1, baseline=None):
    return Word(text, x0, y0, x1, y1, 95, float(baseline if baseline else y1))


def page(words=(), ocr_size=(2272, 3302), embed_dpi=200):
    embed_size = (round(ocr_size[0] * embed_dpi / OCR_DPI),
                  round(ocr_size[1] * embed_dpi / OCR_DPI))
    return assemble.PageInput(
        embed_jpeg=jpeg(embed_size), embed_size=embed_size,
        ocr_size=ocr_size, words=list(words),
    )


def an_issue(**kw):
    base = dict(title="Snake River Echoes", volume=1, issue=1, year=1971,
                publisher="Upper Snake River Valley Historical Society")
    base.update(kw)
    return Issue(**base)


def build(tmp_path, issue, pages, name="out.pdf"):
    out = tmp_path / name
    assemble.build_pdf(issue, pages, out)
    return out


# ------------------------------------------------------------- structure ----

def test_every_sheet_becomes_a_page(tmp_path):
    out = build(tmp_path, an_issue(), [page(), page(), page()])

    with pikepdf.open(out) as pdf:
        assert len(pdf.pages) == 3


def test_page_size_comes_from_the_scan_at_its_true_resolution(tmp_path):
    out = build(tmp_path, an_issue(), [page(ocr_size=(2400, 3300))])

    with pikepdf.open(out) as pdf:
        box = [float(v) for v in pdf.pages[0].MediaBox]
    assert box[2] == pytest.approx(2400 / OCR_DPI * 72, abs=0.01)
    assert box[3] == pytest.approx(3300 / OCR_DPI * 72, abs=0.01)


def test_jpeg_is_stored_without_re_encoding(tmp_path):
    """Passing the JPEG straight through as DCTDecode is what keeps the file
    small; re-encoding would both bloat and degrade it."""
    out = build(tmp_path, an_issue(), [page()])

    with pikepdf.open(out) as pdf:
        image = pdf.pages[0].Resources.XObject.Im0
        assert str(image.Filter) == "/DCTDecode"
        assert image.ColorSpace == pikepdf.Name.DeviceGray


def test_embedded_image_keeps_its_own_lower_resolution(tmp_path):
    """The page is 300 DPI-sized but carries a 200 DPI image. Decoupling those
    is the whole reason this project composes its own text layer."""
    out = build(tmp_path, an_issue(), [page(ocr_size=(2400, 3300), embed_dpi=200)])

    with pikepdf.open(out) as pdf:
        assert int(pdf.pages[0].Resources.XObject.Im0.Width) == 1600
        assert float(pdf.pages[0].MediaBox[2]) == pytest.approx(576.0, abs=0.01)


# ------------------------------------------------------------ text layer ----

def test_text_is_extractable(tmp_path):
    out = build(tmp_path, an_issue(), [page([word("ANDREW", 300, 400, 700, 450)])])

    text = pdfium.PdfDocument(str(out))[0].get_textpage().get_text_range()
    assert "ANDREW" in text


def test_the_text_layer_is_invisible(tmp_path):
    """Render mode 3. Without it the OCR would print on top of the scan."""
    out = build(tmp_path, an_issue(), [page([word("ANDREW", 300, 400, 700, 450)])])

    with pikepdf.open(out) as pdf:
        assert b"3 Tr" in pdf.pages[0].Contents.read_bytes()


def test_words_land_where_the_ocr_found_them(tmp_path):
    """The regression test for Phase 0's worst bug. A misplaced text layer still
    looks perfect on screen and searches wrong."""
    w = word("ANDREW", 300, 400, 700, 450, baseline=444)
    out = build(tmp_path, an_issue(), [page([w], ocr_size=(2272, 3302))])

    doc = pdfium.PdfDocument(str(out))
    tp = doc[0].get_textpage()
    page_height = doc[0].get_height()

    boxes = [tp.get_charbox(i, loose=False) for i in range(tp.count_chars())]
    left = min(b[0] for b in boxes)
    right = max(b[2] for b in boxes)
    bottom = min(b[1] for b in boxes)
    top = max(b[3] for b in boxes)

    assert left == pytest.approx(w.x0 * PT_PER_PX, abs=1.0)
    assert right == pytest.approx(w.x1 * PT_PER_PX, abs=1.5)
    # hOCR counts down from the top; PDF counts up from the bottom.
    assert top == pytest.approx(page_height - w.y0 * PT_PER_PX, abs=1.5)
    assert bottom == pytest.approx(page_height - w.y1 * PT_PER_PX, abs=2.5)


def test_text_is_set_on_the_baseline_not_the_box_bottom(tmp_path):
    """Two words with identical boxes but different baselines must not render
    identically -- that was exactly the 1.73pt systematic error."""
    high = build(tmp_path, an_issue(),
                 [page([word("x", 300, 400, 340, 450, baseline=430)])], "a.pdf")
    low = build(tmp_path, an_issue(),
                [page([word("x", 300, 400, 340, 450, baseline=450)])], "b.pdf")

    def baseline_of(p):
        tp = pdfium.PdfDocument(str(p))[0].get_textpage()
        return tp.get_charbox(0, loose=False)[1]

    assert baseline_of(high) > baseline_of(low)


def test_typographic_apostrophes_survive(tmp_path):
    """The font declares WinAnsiEncoding; encoding the stream as latin-1 turned
    every curly apostrophe into '?'."""
    out = build(tmp_path, an_issue(), [page([word("Snake’s", 300, 400, 700, 450)])])

    text = pdfium.PdfDocument(str(out))[0].get_textpage().get_text_range()
    assert "’" in text


def test_a_page_with_no_words_still_builds(tmp_path):
    """A blank or failed page must never abort an issue."""
    out = build(tmp_path, an_issue(), [page([]), page([word("ok", 10, 10, 60, 40)])])

    with pikepdf.open(out) as pdf:
        assert len(pdf.pages) == 2


def test_degenerate_word_boxes_are_skipped_not_fatal(tmp_path):
    out = build(tmp_path, an_issue(), [page([
        word("zero", 300, 400, 300, 400),
        word("real", 300, 500, 700, 550),
    ])])

    text = pdfium.PdfDocument(str(out))[0].get_textpage().get_text_range()
    assert "real" in text


# -------------------------------------------------------------- outline ----

def test_bookmarks_appear_in_the_outline(tmp_path):
    issue = an_issue(bookmarks=[Bookmark("Front Cover", 1), Bookmark("Andrew Henry", 3)])
    out = build(tmp_path, issue, [page(), page(), page()])

    with pikepdf.open(out) as pdf, pdf.open_outline() as ol:
        assert [i.title for i in ol.root] == ["Front Cover", "Andrew Henry"]


def test_nested_bookmarks_are_nested(tmp_path):
    issue = an_issue(bookmarks=[Bookmark("Idaho Poetry", 1, children=[
        Bookmark("My Home in Idaho", 1), Bookmark("The Grand Old Snake", 3)])])
    out = build(tmp_path, issue, [page(), page(), page()])

    with pikepdf.open(out) as pdf, pdf.open_outline() as ol:
        assert [c.title for c in ol.root[0].children] == [
            "My Home in Idaho", "The Grand Old Snake"]


def test_a_parent_bookmark_navigates_to_its_own_sheet(tmp_path):
    """A grouping label that jumps nowhere is the commonest defect in
    hand-made PDF outlines."""
    issue = an_issue(bookmarks=[Bookmark("Idaho Poetry", 2,
                                         children=[Bookmark("Poem", 3)])])
    out = build(tmp_path, issue, [page(), page(), page()])

    with pikepdf.open(out) as pdf, pdf.open_outline() as ol:
        assert ol.root[0].destination is not None


def test_small_outlines_ship_expanded(tmp_path):
    """Nesting is only safe when children are visible on load."""
    issue = an_issue(bookmarks=[Bookmark("Poetry", 1, children=[Bookmark("Poem", 2)])])
    out = build(tmp_path, issue, [page(), page()])

    with pikepdf.open(out) as pdf:
        parent = pdf.Root.Outlines.First
        assert int(parent.Count) > 0, "expanded nodes carry a positive /Count"


def test_large_outlines_ship_collapsed(tmp_path):
    """Past ~40 entries, scanning relief finally outweighs discoverability."""
    kids = [Bookmark(f"Item {i}", 1) for i in range(45)]
    issue = an_issue(bookmarks=[Bookmark("Department", 1, children=kids)])
    out = build(tmp_path, issue, [page(), page()])

    with pikepdf.open(out) as pdf:
        assert int(pdf.Root.Outlines.First.Count) < 0


def test_an_issue_with_no_bookmarks_builds_without_an_outline(tmp_path):
    out = build(tmp_path, an_issue(bookmarks=[]), [page()])

    with pikepdf.open(out) as pdf:
        assert "/Outlines" not in pdf.Root.keys()


def test_bookmark_pointing_past_the_last_sheet_is_refused(tmp_path):
    issue = an_issue(bookmarks=[Bookmark("Nowhere", 9)])

    with pytest.raises(assemble.AssembleError) as e:
        build(tmp_path, issue, [page()])

    assert "Nowhere" in str(e.value)


# ---------------------------------------------------------- page labels ----

def test_page_labels_are_written(tmp_path):
    issue = an_issue(body_starts_at_sheet=3, body_starts_at_printed=1)
    out = build(tmp_path, issue, [page(), page(), page(), page()])

    with pikepdf.open(out) as pdf:
        labels = pdf.Root.PageLabels.Nums
        assert int(labels[0]) == 0
        assert str(labels[1].S) == "/r"


def test_body_pages_are_labelled_with_the_printed_number(tmp_path):
    issue = an_issue(body_starts_at_sheet=3, body_starts_at_printed=7)
    out = build(tmp_path, issue, [page(), page(), page(), page()])

    with pikepdf.open(out) as pdf:
        nums = pdf.Root.PageLabels.Nums
        body = dict(zip([int(nums[i]) for i in range(0, len(nums), 2)],
                        [nums[i] for i in range(1, len(nums), 2)]))
        assert str(body[2].S) == "/D"
        assert int(body[2].St) == 7


def test_an_issue_with_no_front_matter_has_only_an_arabic_range(tmp_path):
    issue = an_issue(body_starts_at_sheet=1, body_starts_at_printed=1)
    out = build(tmp_path, issue, [page(), page()])

    with pikepdf.open(out) as pdf:
        assert len(pdf.Root.PageLabels.Nums) == 2


# ------------------------------------------------------------- metadata ----

def test_document_metadata_is_written(tmp_path):
    out = build(tmp_path, an_issue(), [page()])

    with pikepdf.open(out) as pdf, pdf.open_metadata() as meta:
        assert "Snake River Echoes" in meta["dc:title"]
        assert "1971" in meta["dc:title"]
        assert "Upper Snake River Valley" in "".join(meta["dc:creator"])


def test_metadata_survives_missing_optional_fields(tmp_path):
    out = build(tmp_path, Issue(title="Untitled Scans"), [page()])

    with pikepdf.open(out) as pdf, pdf.open_metadata() as meta:
        assert meta["dc:title"] == "Untitled Scans"


def test_a_bookmarked_pdf_opens_with_its_outline_showing(tmp_path):
    """Without /PageMode a viewer picks its own panel -- usually thumbnails --
    so the outline is there but invisible until the reader goes hunting for it.
    The whole point of the outline is that it is the first thing you see."""
    issue = an_issue(bookmarks=[Bookmark("Front Cover", 1), Bookmark("Andrew Henry", 2)])
    out = build(tmp_path, issue, [page(), page()])

    with pikepdf.open(out) as pdf:
        assert str(pdf.Root.PageMode) == "/UseOutlines"


def test_a_pdf_without_bookmarks_does_not_ask_for_an_outline_panel(tmp_path):
    """Opening an empty outline panel looks broken."""
    out = build(tmp_path, an_issue(bookmarks=[]), [page()])

    with pikepdf.open(out) as pdf:
        assert "/PageMode" not in pdf.Root.keys() or str(pdf.Root.PageMode) != "/UseOutlines"


# --------------------------------------------------- a gap in the scan ----

def test_page_labels_restart_after_a_gap(tmp_path):
    """Vol 1 No 2 carries 25, 26, 27 then jumps to 30. /PageLabels is a number
    tree and says so in two runs."""
    issue = an_issue(body_starts_at_sheet=1, body_starts_at_printed=25,
                     missing_pages=[28, 29], gap_acknowledged=True)

    out = build(tmp_path, issue, [page() for _ in range(5)])

    with pikepdf.open(out) as pdf:
        nums = pdf.Root.PageLabels.Nums       # flat: index, dict, index, dict
        assert len(nums) == 4
        assert (int(nums[0]), int(nums[1].St)) == (0, 25)
        assert (int(nums[2]), int(nums[3].St)) == (3, 30)


def test_a_complete_scan_still_gets_one_run(tmp_path):
    issue = an_issue(body_starts_at_sheet=1, body_starts_at_printed=49)

    out = build(tmp_path, issue, [page() for _ in range(4)])

    with pikepdf.open(out) as pdf:
        assert len(pdf.Root.PageLabels.Nums) == 2


def test_a_bookmark_for_an_unscanned_page_is_not_written_to_the_pdf(tmp_path):
    """It waits in the saved review instead. A bookmark that jumps to the
    wrong page is worse than no bookmark, because a reader cannot tell."""
    issue = an_issue(missing_pages=[28], gap_acknowledged=True, bookmarks=[
        Bookmark("Front Cover", 1),
        Bookmark("The Battle of Pierre's Hole", 1, needs_review=True,
                 review_reason="missing", missing_page=28)])

    out = build(tmp_path, issue, [page() for _ in range(3)])

    with pikepdf.open(out) as pdf:
        titles = [item.title for item in pdf.open_outline().root]
        assert titles == ["Front Cover"]


# ------------------------------------------------------------- colour ----

def _colour_page(embed_dpi=200, ocr_size=(2272, 3302)):
    """A page whose embedded JPEG is RGB, as a colour scan now produces."""
    embed_size = (round(ocr_size[0] * embed_dpi / OCR_DPI),
                  round(ocr_size[1] * embed_dpi / OCR_DPI))
    buf = io.BytesIO()
    Image.new("RGB", embed_size, (200, 120, 60)).save(buf, "JPEG", quality=70)
    return assemble.PageInput(embed_jpeg=buf.getvalue(), embed_size=embed_size,
                              ocr_size=ocr_size, words=[])


def test_a_colour_page_is_declared_as_colour(tmp_path):
    """The JPEG carries three bytes per pixel. Declaring DeviceGray makes the
    viewer read each of them as a separate grey pixel, and the page comes out
    smeared and three times too wide."""
    out = build(tmp_path, an_issue(), [_colour_page()])

    with pikepdf.open(out) as pdf:
        image = pdf.pages[0].Resources.XObject.Im0
        assert str(image.ColorSpace) == "/DeviceRGB"


def test_a_grey_page_is_still_declared_as_grey(tmp_path):
    out = build(tmp_path, an_issue(), [page()])

    with pikepdf.open(out) as pdf:
        assert str(pdf.pages[0].Resources.XObject.Im0.ColorSpace) == "/DeviceGray"


def test_the_declared_width_matches_the_jpeg(tmp_path):
    """A mismatch here is the same bug seen from the other side."""
    out = build(tmp_path, an_issue(), [_colour_page()])

    with pikepdf.open(out) as pdf:
        image = pdf.pages[0].Resources.XObject.Im0
        decoded = Image.open(io.BytesIO(bytes(image.get_raw_stream_buffer())))
        assert (int(image.Width), int(image.Height)) == decoded.size
