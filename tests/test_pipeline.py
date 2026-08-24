"""The draft -> review -> build flow, exercised without needing Tesseract by
pre-seeding the hOCR cache the way a previous run would have left it.
"""
import pikepdf
import pytest

from srebook.core import pipeline
from srebook.core.model import Bookmark, load_sidecar, save_sidecar

# The drafter always bookmarks the front matter it can identify; tests about
# article detection filter these out rather than restate them everywhere.
FRONT_MATTER = {"Front Cover", "Table of Contents"}


def hocr_page(lines_with_boxes) -> bytes:
    spans = []
    for text, (lx0, ly0, lx1, ly1) in lines_with_boxes:
        words, x = [], lx0
        for token in text.split():
            w = len(token) * 30
            words.append(
                f"<span class='ocrx_word' title='bbox {x} {ly0} {x + w} {ly1}; "
                f"x_wconf 95'>{token}</span>"
            )
            x += w + 15
        spans.append(
            f"<span class='ocr_line' title=\"bbox {lx0} {ly0} {lx1} {ly1}; "
            f'baseline 0 -9">{"".join(words)}</span>'
        )
    return (
        "<html><body><div class='ocr_page' title='bbox 0 0 2272 3302'>"
        "<div class='ocr_carea' title='bbox 0 0 2272 3302'>"
        f"<p class='ocr_par' title='bbox 0 0 2272 3302'>{''.join(spans)}</p>"
        "</div></div></body></html>"
    ).encode("utf-8")


PAGE_TEXT = {
    1: [("THE UPPER SNAKE RIVER VALLEY", (200, 300, 1800, 360))],
    2: [("CONTENTS", (200, 300, 900, 360)),
        ("ORAL HISTORY", (200, 400, 1400, 460)),
        ("ANDREW HENRY", (200, 500, 1400, 560))],
    3: [("ORAL HISTORY", (200, 300, 1400, 360)),
        ("The introduction of the recorder", (200, 400, 1800, 460))],
    4: [("4", (200, 200, 260, 250)),
        ("and a copy was made", (200, 400, 1800, 460))],
    5: [("ANDREW HENRY", (200, 300, 1400, 360)),
        ("Andrew Henry was born", (200, 400, 1800, 460))],
    6: [("6", (200, 200, 260, 250)),
        ("in Fayette County", (200, 400, 1800, 460))],
}


@pytest.fixture
def issue_folder(tmp_path, make_sheet):
    folder = tmp_path / "SRE Vol 1 Number 1"
    folder.mkdir()
    for n in range(1, 7):
        src = make_sheet(name=f"SRE_1971_Vol1_No1_{n:02d}.tif")
        src.replace(folder / src.name)

    cache = pipeline.cache_dir(folder)
    cache.mkdir(parents=True, exist_ok=True)
    for n, lines in PAGE_TEXT.items():
        (cache / f"SRE_1971_Vol1_No1_{n:02d}.hocr").write_bytes(hocr_page(lines))
    return folder


# ----------------------------------------------------------------- draft ----

def test_draft_writes_a_sidecar(issue_folder):
    pipeline.draft(issue_folder)

    assert pipeline.sidecar_path(issue_folder).exists()


def test_draft_names_output_from_the_scan_filenames(issue_folder):
    pipeline.draft(issue_folder)

    assert pipeline.sidecar_path(issue_folder).name == "SRE_1971_Vol1_No1.srebook.json"


def test_draft_guesses_issue_metadata(issue_folder):
    issue = pipeline.draft(issue_folder)

    assert (issue.year, issue.volume, issue.issue) == (1971, 1, 1)


def test_draft_locates_article_titles(issue_folder):
    issue = pipeline.draft(issue_folder)

    assert ("Oral History", 3) in [(b.title, b.sheet) for b in issue.bookmarks]
    assert ("Andrew Henry", 5) in [(b.title, b.sheet) for b in issue.bookmarks]


def test_draft_detects_where_the_body_starts(issue_folder):
    """Sheet 4 prints '4' and sheet 6 prints '6', so sheet number equals printed
    page number -- meaning printed page 1 is sheet 1. The operator need not work
    it out, and sheets 1-3 are not mislabelled as roman front matter."""
    issue = pipeline.draft(issue_folder)

    assert (issue.body_starts_at_sheet, issue.body_starts_at_printed) == (1, 1)


def test_unlocated_titles_are_still_offered_to_the_operator(tmp_path, make_sheet):
    """A title with no sheet must appear in the grid, not vanish silently."""
    folder = tmp_path / "issue"
    folder.mkdir()
    for n in (1, 2):
        src = make_sheet(name=f"X_{n:02d}.tif")
        src.replace(folder / src.name)
    cache = pipeline.cache_dir(folder)
    cache.mkdir(parents=True)
    (cache / "X_01.hocr").write_bytes(hocr_page(
        [("CONTENTS", (200, 300, 900, 360)), ("IDAHO POETRY", (200, 400, 1400, 460))]))
    (cache / "X_02.hocr").write_bytes(hocr_page([("nothing here", (200, 300, 900, 360))]))

    issue = pipeline.draft(folder)

    articles = [b for b in issue.bookmarks if b.title not in FRONT_MATTER]
    assert [b.title for b in articles] == ["Idaho Poetry"]
    assert articles[0].sheet == 1  # parked on sheet 1 for the operator
    assert articles[0].needs_review


def test_draft_does_not_discard_operator_edits(issue_folder):
    """Re-drafting after a review must not throw away the review."""
    issue = pipeline.draft(issue_folder)
    issue.bookmarks = [Bookmark("Hand Written", 2)]
    issue.title = "Snake River Echoes"
    save_sidecar(issue, pipeline.sidecar_path(issue_folder))

    again = pipeline.draft(issue_folder)

    assert again.title == "Snake River Echoes"
    assert [b.title for b in again.bookmarks] == ["Hand Written"]


def test_redrafting_can_be_forced(issue_folder):
    issue = pipeline.draft(issue_folder)
    issue.bookmarks = [Bookmark("Hand Written", 2)]
    save_sidecar(issue, pipeline.sidecar_path(issue_folder))

    again = pipeline.draft(issue_folder, overwrite=True)

    assert [b.title for b in again.bookmarks] != ["Hand Written"]


# ----------------------------------------------------------------- build ----

def test_build_produces_a_pdf_with_one_page_per_sheet(issue_folder):
    pipeline.draft(issue_folder)

    out = pipeline.build(issue_folder)

    with pikepdf.open(out) as pdf:
        assert len(pdf.pages) == 6


def test_build_uses_the_reviewed_sidecar(issue_folder):
    pipeline.draft(issue_folder)
    path = pipeline.sidecar_path(issue_folder)
    issue = load_sidecar(path)
    issue.bookmarks = [Bookmark("Operator Chose This", 2)]
    save_sidecar(issue, path)

    out = pipeline.build(issue_folder)

    with pikepdf.open(out) as pdf, pdf.open_outline() as ol:
        assert [i.title for i in ol.root] == ["Operator Chose This"]


def test_build_writes_beside_the_sidecar(issue_folder):
    pipeline.draft(issue_folder)

    out = pipeline.build(issue_folder)

    assert out.name == "SRE_1971_Vol1_No1.pdf"
    assert out.parent == pipeline.output_dir(issue_folder)


def test_build_without_a_draft_is_refused_readably(issue_folder):
    with pytest.raises(pipeline.PipelineError) as e:
        pipeline.build(issue_folder)

    assert "draft" in str(e.value).lower()


def test_build_leaves_the_source_scans_untouched(issue_folder):
    before = {p.name: p.stat().st_mtime_ns for p in issue_folder.glob("*.tif")}
    pipeline.draft(issue_folder)
    pipeline.build(issue_folder)

    after = {p.name: p.stat().st_mtime_ns for p in issue_folder.glob("*.tif")}
    assert before == after


def test_empty_folder_is_refused_readably(tmp_path):
    (tmp_path / "empty").mkdir()

    with pytest.raises(pipeline.PipelineError) as e:
        pipeline.draft(tmp_path / "empty")

    assert "no page scans" in str(e.value).lower()


def test_build_reports_progress_per_sheet(issue_folder):
    pipeline.draft(issue_folder)
    seen = []

    pipeline.build(issue_folder, progress=lambda done, total, label: seen.append(done))

    assert seen and seen[-1] == 6


def test_a_body_heading_does_not_become_a_second_bookmark(tmp_path, make_sheet):
    """Real failure: the contents page gave 'A GOAL IS ACHIEVED' and the article
    heading gave 'A GOAL IS ACHIEVED!', producing two bookmarks for one article.
    Candidate titles must come from the front matter only."""
    folder = tmp_path / "issue"
    folder.mkdir()
    for n in (1, 2, 3):
        src = make_sheet(name=f"Y_{n:02d}.tif")
        src.replace(folder / src.name)
    cache = pipeline.cache_dir(folder)
    cache.mkdir(parents=True)
    (cache / "Y_01.hocr").write_bytes(hocr_page([("COVER", (200, 300, 900, 360))]))
    (cache / "Y_02.hocr").write_bytes(hocr_page(
        [("CONTENTS", (200, 300, 900, 360)),
         ("A GOAL IS ACHIEVED", (200, 400, 1400, 460))]))
    (cache / "Y_03.hocr").write_bytes(hocr_page(
        [("A GOAL IS ACHIEVED!", (200, 300, 1400, 360)),
         ("The Upper Snake River Valley", (200, 400, 1800, 460))]))

    issue = pipeline.draft(folder)

    articles = [b for b in issue.bookmarks if b.title not in FRONT_MATTER]
    assert [b.title for b in articles] == ["A Goal Is Achieved"]
    assert articles[0].sheet == 3


def test_draft_marks_only_the_titles_it_could_not_locate(tmp_path, make_sheet):
    """A located title is settled; an unlocated one is parked AND flagged, so a
    bookmark legitimately on sheet 1 is not mistaken for an unplaced one."""
    folder = tmp_path / "issue"
    folder.mkdir()
    for n in (1, 2, 3):
        src = make_sheet(name=f"Z_{n:02d}.tif")
        src.replace(folder / src.name)
    cache = pipeline.cache_dir(folder)
    cache.mkdir(parents=True)
    (cache / "Z_01.hocr").write_bytes(hocr_page([("COVER PAGE", (200, 300, 900, 360))]))
    (cache / "Z_02.hocr").write_bytes(hocr_page(
        [("CONTENTS", (200, 300, 900, 360)),
         ("ORAL HISTORY", (200, 400, 1400, 460)),
         ("IDAHO POETRY", (200, 500, 1400, 560))]))
    (cache / "Z_03.hocr").write_bytes(hocr_page([("ORAL HISTORY", (200, 300, 1400, 360))]))

    issue = pipeline.draft(folder)

    flags = {b.title: b.needs_review for b in issue.bookmarks}
    assert flags["Oral History"] is False
    assert flags["Idaho Poetry"] is True


def test_a_title_case_contents_page_still_produces_bookmarks(tmp_path, make_sheet):
    """Vol 1 No 3 sets its contents in Title Case. Only entries the body
    confirms become bookmarks; front-matter noise that merely looks like a
    title is dropped rather than parked."""
    folder = tmp_path / "issue"
    folder.mkdir()
    for n in range(1, 5):
        src = make_sheet(name=f"W_{n:02d}.tif")
        src.replace(folder / src.name)
    cache = pipeline.cache_dir(folder)
    cache.mkdir(parents=True)
    (cache / "W_01.hocr").write_bytes(hocr_page([("COVER", (200, 300, 900, 360))]))
    (cache / "W_02.hocr").write_bytes(hocr_page([
        ("Contents", (200, 300, 900, 360)),
        ("A Critical Look at Historical Editing", (200, 400, 1800, 460)),
        ("Volume 1, Number 3", (200, 500, 1400, 560)),
        ("The editor discusses the problems of writing", (200, 600, 1900, 660)),
    ]))
    (cache / "W_03.hocr").write_bytes(hocr_page([
        ("A CRITICAL LOOK AT HISTORICAL EDITING", (200, 300, 1900, 360)),
        ("As you wander through the libraries", (200, 400, 1800, 460))]))
    (cache / "W_04.hocr").write_bytes(hocr_page([("more prose", (200, 300, 900, 360))]))

    issue = pipeline.draft(folder)

    titles = [(b.title, b.sheet) for b in issue.bookmarks]
    assert ("A Critical Look at Historical Editing", 3) in titles
    assert not any("Volume 1" in t for t, _ in titles)
    assert not any(t.startswith("The editor") for t, _ in titles)


def test_draft_bookmarks_the_cover_and_the_contents_page(issue_folder):
    """The drafter knows where the contents page is -- it found it in order to
    search past it -- and sheet 1 is the cover. Both were being left out of the
    outline, or parked for the operator to place by hand."""
    issue = pipeline.draft(issue_folder)

    placed = [(b.title, b.sheet, b.needs_review) for b in issue.bookmarks]
    assert ("Front Cover", 1, False) in placed
    assert ("Table of Contents", 2, False) in placed


def test_the_cover_and_contents_lead_the_outline(issue_folder):
    issue = pipeline.draft(issue_folder)

    assert [b.title for b in issue.bookmarks][:2] == ["Front Cover", "Table of Contents"]


def test_a_contents_entry_describing_the_cover_is_not_duplicated(tmp_path, make_sheet):
    """Several issues list COVER on the contents page, describing the artwork.
    That must not produce a second cover bookmark."""
    folder = tmp_path / "issue"
    folder.mkdir()
    for n in (1, 2, 3):
        src = make_sheet(name=f"V_{n:02d}.tif")
        src.replace(folder / src.name)
    cache = pipeline.cache_dir(folder)
    cache.mkdir(parents=True)
    (cache / "V_01.hocr").write_bytes(hocr_page([("THE QUARTERLY", (200, 300, 1400, 360))]))
    (cache / "V_02.hocr").write_bytes(hocr_page([
        ("CONTENTS", (200, 300, 900, 360)),
        ("ORAL HISTORY", (200, 400, 1400, 460)),
        ("COVER", (200, 500, 900, 560))]))
    (cache / "V_03.hocr").write_bytes(hocr_page([("ORAL HISTORY", (200, 300, 1400, 360))]))

    issue = pipeline.draft(folder)

    titles = [b.title for b in issue.bookmarks]
    assert titles.count("Front Cover") == 1
    assert "COVER" not in titles
    assert titles.count("Table of Contents") == 1


def test_no_contents_bookmark_when_there_is_no_contents_page(tmp_path, make_sheet):
    """A folder of body scans with no front matter must not gain a bookmark
    pointing at a contents page that does not exist."""
    folder = tmp_path / "issue"
    folder.mkdir()
    for n in (1, 2):
        src = make_sheet(name=f"U_{n:02d}.tif")
        src.replace(folder / src.name)
    cache = pipeline.cache_dir(folder)
    cache.mkdir(parents=True)
    (cache / "U_01.hocr").write_bytes(hocr_page([("some prose here", (200, 300, 1400, 360))]))
    (cache / "U_02.hocr").write_bytes(hocr_page([("more prose", (200, 300, 1400, 360))]))

    issue = pipeline.draft(folder)

    assert "Table of Contents" not in [b.title for b in issue.bookmarks]


def test_drafted_bookmarks_are_title_case(issue_folder):
    """Asked for by a special collections archivist: a bookmark panel of
    shouting caps is not how a catalogue reads."""
    issue = pipeline.draft(issue_folder)

    titles = [b.title for b in issue.bookmarks]
    assert "Oral History" in titles
    assert "ORAL HISTORY" not in titles


def test_title_case_is_applied_once_at_draft_time_only(issue_folder):
    """An operator's own wording must never be re-cased behind their back."""
    from srebook.core.model import Bookmark, load_sidecar, save_sidecar
    pipeline.draft(issue_folder)
    path = pipeline.sidecar_path(issue_folder)
    issue = load_sidecar(path)
    issue.bookmarks = [Bookmark("WPA Records and the CCC", 3)]
    save_sidecar(issue, path)

    again = pipeline.draft(issue_folder)

    assert [b.title for b in again.bookmarks] == ["WPA Records and the CCC"]


def test_draft_offers_headings_the_contents_page_never_listed(tmp_path, make_sheet):
    """An archivist asked for poems by their own titles rather than the
    category. They are printed as headings; the parser simply never looked."""
    folder = tmp_path / "issue"
    folder.mkdir()
    for n in range(1, 5):
        src = make_sheet(name=f"P_{n:02d}.tif")
        src.replace(folder / src.name)
    cache = pipeline.cache_dir(folder)
    cache.mkdir(parents=True)
    (cache / "P_01.hocr").write_bytes(hocr_page([("THE QUARTERLY", (200, 300, 1400, 360))]))
    (cache / "P_02.hocr").write_bytes(hocr_page([
        ("CONTENTS", (200, 300, 900, 360)),
        ("IDAHO POETRY", (200, 400, 1400, 460))]))
    (cache / "P_03.hocr").write_bytes(hocr_page([
        ("MY HOME IN IDAHO", (200, 300, 1500, 360)),
        ("I come to this place a long time ago", (200, 400, 1800, 460))]))
    (cache / "P_04.hocr").write_bytes(hocr_page([
        ("THE GRAND OLD SNAKE", (200, 300, 1600, 360)),
        ("So oft I have sat beside the mighty Snake", (200, 400, 1800, 460))]))

    issue = pipeline.draft(folder)

    found = {(b.title, b.sheet) for b in issue.bookmarks}
    assert ("My Home in Idaho", 3) in found
    assert ("The Grand Old Snake", 4) in found


def test_suggested_headings_are_flagged_for_review(tmp_path, make_sheet):
    """They come from the parser's own reading, not from the printed contents,
    so a person confirms them before they are published."""
    folder = tmp_path / "issue"
    folder.mkdir()
    for n in (1, 2, 3):
        src = make_sheet(name=f"Q_{n:02d}.tif")
        src.replace(folder / src.name)
    cache = pipeline.cache_dir(folder)
    cache.mkdir(parents=True)
    (cache / "Q_01.hocr").write_bytes(hocr_page([("THE QUARTERLY", (200, 300, 1400, 360))]))
    (cache / "Q_02.hocr").write_bytes(hocr_page([("CONTENTS", (200, 300, 900, 360))]))
    (cache / "Q_03.hocr").write_bytes(hocr_page([
        ("BOARD OF DIRECTORS", (200, 300, 1500, 360)),
        ("Harold Forbush, Chairman", (200, 400, 1800, 460))]))

    issue = pipeline.draft(folder)

    suggested = [b for b in issue.bookmarks if b.title == "Board of Directors"]
    assert suggested and suggested[0].needs_review
    assert suggested[0].sheet == 3


def test_unplaced_bookmarks_sort_after_the_ones_with_a_real_page(tmp_path, make_sheet):
    """Sorting purely by sheet drops a title parked on sheet 1 between the
    cover and the contents page, which reads as though it belongs there.
    A bookmark with no known page belongs at the end, out of the way."""
    folder = tmp_path / "issue"
    folder.mkdir()
    for n in range(1, 5):
        src = make_sheet(name=f"R_{n:02d}.tif")
        src.replace(folder / src.name)
    cache = pipeline.cache_dir(folder)
    cache.mkdir(parents=True)
    (cache / "R_01.hocr").write_bytes(hocr_page([("THE QUARTERLY", (200, 300, 1400, 360))]))
    (cache / "R_02.hocr").write_bytes(hocr_page([
        ("CONTENTS", (200, 300, 900, 360)),
        ("ORAL HISTORY", (200, 400, 1400, 460)),
        ("IDAHO POETRY", (200, 500, 1400, 560))]))
    (cache / "R_03.hocr").write_bytes(hocr_page([("ORAL HISTORY", (200, 300, 1400, 360))]))
    (cache / "R_04.hocr").write_bytes(hocr_page([("more prose", (200, 300, 900, 360))]))

    issue = pipeline.draft(folder)

    titles = [b.title for b in issue.bookmarks]
    assert titles.index("Table of Contents") < titles.index("Idaho Poetry"), titles
    assert titles[-1] == "Idaho Poetry", titles
