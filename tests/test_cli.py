import pytest

from srebook import cli
from srebook.core import pipeline
from tests.test_pipeline import PAGE_TEXT, hocr_page  # noqa: F401


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


def test_draft_succeeds_and_says_where_the_sidecar_is(issue_folder, capsys):
    code = cli.main(["draft", str(issue_folder)])

    assert code == 0
    assert "SRE_1971_Vol1_No1.srebook.json" in capsys.readouterr().out


def test_draft_tells_the_operator_what_to_do_next(issue_folder, capsys):
    cli.main(["draft", str(issue_folder)])

    assert "build" in capsys.readouterr().out.lower()


def test_draft_reports_titles_it_could_not_place(tmp_path, make_sheet, capsys):
    """An unplaced title is the one thing the operator must act on."""
    folder = tmp_path / "issue"
    folder.mkdir()
    for n in (1, 2):
        src = make_sheet(name=f"X_{n:02d}.tif")
        src.replace(folder / src.name)
    cache = pipeline.cache_dir(folder)
    cache.mkdir(parents=True)
    (cache / "X_01.hocr").write_bytes(hocr_page(
        [("CONTENTS", (200, 300, 900, 360)), ("IDAHO POETRY", (200, 400, 1400, 460))]))
    (cache / "X_02.hocr").write_bytes(hocr_page([("prose here", (200, 300, 900, 360))]))

    cli.main(["draft", str(folder)])

    assert "Idaho Poetry" in capsys.readouterr().out


def test_build_succeeds_and_reports_the_pdf(issue_folder, capsys):
    cli.main(["draft", str(issue_folder)])
    capsys.readouterr()

    code = cli.main(["build", str(issue_folder)])

    out = capsys.readouterr().out
    assert code == 0
    assert "SRE_1971_Vol1_No1.pdf" in out


def test_build_reports_size_and_bookmark_count(issue_folder, capsys):
    cli.main(["draft", str(issue_folder)])
    capsys.readouterr()

    cli.main(["build", str(issue_folder)])

    out = capsys.readouterr().out
    assert "MB" in out
    assert "bookmark" in out.lower()


def test_a_missing_folder_is_a_sentence_not_a_traceback(tmp_path, capsys):
    code = cli.main(["draft", str(tmp_path / "nope")])

    err = capsys.readouterr().err
    assert code != 0
    assert "does not exist" in err
    assert "Traceback" not in err


def test_building_without_drafting_is_explained(issue_folder, capsys):
    code = cli.main(["build", str(issue_folder)])

    assert code != 0
    assert "draft" in capsys.readouterr().err.lower()


def test_embed_dpi_is_settable(issue_folder):
    cli.main(["draft", str(issue_folder), "--embed-dpi", "300"])

    from srebook.core.model import load_sidecar
    assert load_sidecar(pipeline.sidecar_path(issue_folder)).embed_dpi == 300


def test_force_redrafts_over_a_review(issue_folder):
    from srebook.core.model import Bookmark, load_sidecar, save_sidecar
    cli.main(["draft", str(issue_folder)])
    path = pipeline.sidecar_path(issue_folder)
    issue = load_sidecar(path)
    issue.bookmarks = [Bookmark("Hand Written", 1)]
    save_sidecar(issue, path)

    cli.main(["draft", str(issue_folder), "--force"])

    assert [b.title for b in load_sidecar(path).bookmarks] != ["Hand Written"]


def test_no_arguments_shows_usage(capsys):
    with pytest.raises(SystemExit):
        cli.main([])


def test_build_refuses_an_unreviewed_draft(issue_folder, capsys):
    """The operator is the accuracy backstop. Publishing unreviewed bookmarks
    is the one thing the flow must not do quietly."""
    from srebook.core.model import Bookmark, load_sidecar, save_sidecar
    cli.main(["draft", str(issue_folder)])
    path = pipeline.sidecar_path(issue_folder)
    issue = load_sidecar(path)
    issue.bookmarks = [Bookmark("IDAHO POETRY", 1, needs_review=True)]
    save_sidecar(issue, path)
    capsys.readouterr()

    code = cli.main(["build", str(issue_folder)])

    assert code != 0
    assert "IDAHO POETRY" in capsys.readouterr().err


def test_build_can_be_forced_for_unattended_use(issue_folder, capsys):
    """Automation needs a way through, but it has to be asked for."""
    from srebook.core.model import Bookmark, load_sidecar, save_sidecar
    cli.main(["draft", str(issue_folder)])
    path = pipeline.sidecar_path(issue_folder)
    issue = load_sidecar(path)
    issue.bookmarks = [Bookmark("IDAHO POETRY", 1, needs_review=True)]
    save_sidecar(issue, path)

    code = cli.main(["build", str(issue_folder), "--force"])

    assert code == 0


def test_draft_states_the_page_mapping_accurately(issue_folder, capsys):
    """A continuously paginated volume starts at page 27, not page 1. Saying
    'Printed p.1 is sheet 1' is simply false there."""
    from srebook.core.model import load_sidecar, save_sidecar
    cli.main(["draft", str(issue_folder)])
    path = pipeline.sidecar_path(issue_folder)
    issue = load_sidecar(path)
    issue.body_starts_at_sheet, issue.body_starts_at_printed = 1, 27
    save_sidecar(issue, path)
    capsys.readouterr()

    cli.main(["draft", str(issue_folder)])

    out = capsys.readouterr().out
    assert "27" in out
    assert "Printed p.1  sheet 1" not in out


def test_pages_lists_the_reading_order(issue_folder, capsys):
    """An operator reported pages not coming in as their file names implied.
    There was no way to see what order the program had actually chosen."""
    code = cli.main(["pages", str(issue_folder)])

    out = capsys.readouterr().out
    assert code == 0
    assert "SRE_1971_Vol1_No1_01.tif" in out
    assert "sheet" in out.lower()


def test_pages_shows_the_printed_page_each_sheet_will_carry(issue_folder, capsys):
    from srebook.core.model import load_sidecar, save_sidecar
    cli.main(["draft", str(issue_folder)])
    path = pipeline.sidecar_path(issue_folder)
    issue = load_sidecar(path)
    issue.body_starts_at_sheet, issue.body_starts_at_printed = 1, 27
    save_sidecar(issue, path)
    capsys.readouterr()

    cli.main(["pages", str(issue_folder)])

    out = capsys.readouterr().out
    assert "27" in out and "32" in out


def test_pages_refuses_a_folder_with_no_scans(tmp_path, capsys):
    (tmp_path / "empty").mkdir()

    code = cli.main(["pages", str(tmp_path / "empty")])

    assert code != 0


def test_draft_separates_unplaced_titles_from_suggested_headings(tmp_path, make_sheet, capsys):
    """They need opposite advice: one needs a page number, the other needs a
    yes or no."""
    from tests.test_pipeline import hocr_page
    folder = tmp_path / "issue"
    folder.mkdir()
    for n in (1, 2, 3):
        src = make_sheet(name=f"S_{n:02d}.tif")
        src.replace(folder / src.name)
    cache = pipeline.cache_dir(folder)
    cache.mkdir(parents=True)
    (cache / "S_01.hocr").write_bytes(hocr_page([("THE QUARTERLY", (200, 300, 1400, 360))]))
    (cache / "S_02.hocr").write_bytes(hocr_page([
        ("CONTENTS", (200, 300, 900, 360)),
        ("IDAHO POETRY", (200, 400, 1400, 460))]))
    (cache / "S_03.hocr").write_bytes(hocr_page([
        ("BOARD OF DIRECTORS", (200, 300, 1500, 360)),
        ("Harold Forbush, Chairman", (200, 400, 1800, 460))]))

    cli.main(["draft", str(folder)])

    out = capsys.readouterr().out
    assert "could not be located" in out
    assert "printed in the issue" in out

    unplaced_section, suggested_section = out.split("printed in the issue")
    unplaced_section = unplaced_section.split("could not be located")[1]
    assert "Idaho Poetry" in unplaced_section
    assert "Board of Directors" not in unplaced_section
    assert "Board of Directors" in suggested_section
