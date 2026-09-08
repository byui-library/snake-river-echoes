import subprocess
import sys

import pytest


def test_core_does_not_import_tkinter():
    """A hard constraint: core is the testable surface, and a GUI import there
    makes the whole pipeline untestable headless. Checked in a fresh interpreter
    so an earlier import in this process cannot mask it."""
    code = (
        "import srebook.core.pipeline, srebook.core.assemble, srebook.core.ocr, sys; "
        "print(any(m == 'tkinter' or m.startswith('tkinter.') for m in sys.modules))"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "False"


def test_grid_logic_does_not_import_tkinter():
    """grid.py holds the outline rules, so they must be testable without a display."""
    code = ("import srebook.gui.grid, sys; "
            "print(any(m == 'tkinter' or m.startswith('tkinter.') for m in sys.modules))")
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)

    assert result.stdout.strip() == "False"


# ------------------------------------------------------------- widgets ----

def _tk_or_skip():
    tk = pytest.importorskip("tkinter")
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("no display available")
    root.withdraw()
    return tk, root


def test_the_window_builds():
    _tk, root = _tk_or_skip()
    from srebook.gui.app import App
    try:
        app = App(root)
        # ttk hands back a Tcl object, not a str.
        assert str(app.build_button["state"]) == "disabled", \
            "nothing to build until a folder is chosen"
    finally:
        root.destroy()


def test_quality_choice_maps_to_embed_dpi():
    _tk, root = _tk_or_skip()
    from srebook.gui.app import App
    try:
        app = App(root)
        app.quality_var.set("High (300 DPI)")
        assert app._embed_dpi() == 300
        app.quality_var.set("Small (150 DPI)")
        assert app._embed_dpi() == 150
    finally:
        root.destroy()


def test_metadata_fields_are_collected_onto_the_issue():
    _tk, root = _tk_or_skip()
    from srebook.core.model import Bookmark, Issue
    from srebook.gui.app import App
    from srebook.gui.grid import OutlineGrid
    try:
        app = App(root)
        app.grid_model = OutlineGrid(Issue(), sheet_count=5,
                                     rows=OutlineGrid._flatten([Bookmark("A", 1)]))
        app.title_var.set("Snake River Echoes")
        app.volume_var.set("1")
        app.year_var.set("1971")
        app.label_sheet_var.set("3")

        app._collect_metadata()

        issue = app.grid_model.issue
        assert (issue.title, issue.volume, issue.year) == ("Snake River Echoes", 1, 1971)
        assert issue.body_starts_at_sheet == 3
    finally:
        root.destroy()


def test_blank_number_fields_become_none_not_zero():
    """Other archives will not fill these in. Blank must mean unknown."""
    _tk, root = _tk_or_skip()
    from srebook.core.model import Issue
    from srebook.gui.app import App
    from srebook.gui.grid import OutlineGrid
    try:
        app = App(root)
        app.grid_model = OutlineGrid(Issue(), sheet_count=5)
        app.volume_var.set("")
        app.year_var.set("  ")

        app._collect_metadata()

        assert app.grid_model.issue.volume is None
        assert app.grid_model.issue.year is None
    finally:
        root.destroy()


def test_the_window_can_re_analyse_an_issue():
    """draft() returns a previously saved review when one exists, so without
    this the window shows a stale result forever and the operator has no way to
    re-run the analysis. That is exactly how an issue drafted by an older,
    worse parser kept showing one bookmark."""
    _tk, root = _tk_or_skip()
    from srebook.gui.app import App
    try:
        app = App(root)
        assert hasattr(app, "reanalyse")
        assert str(app.reanalyse_button["state"]) == "disabled", "nothing to re-analyse yet"
    finally:
        root.destroy()


def test_the_status_says_when_a_saved_review_was_loaded():
    """Otherwise 'only the cover' looks like the analysis failed, rather than
    like an old result being shown back."""
    _tk, root = _tk_or_skip()
    from srebook.core.model import Bookmark, Issue
    from srebook.gui.app import App
    try:
        app = App(root)
        app.sheets = [None] * 22
        app._on_drafted(Issue(bookmarks=[Bookmark("Cover", 1)]), False)
        assert "saved" in app.status["text"].lower()

        app._on_drafted(Issue(bookmarks=[Bookmark("Cover", 1)]), True)
        assert "saved" not in app.status["text"].lower()
    finally:
        root.destroy()


def test_the_window_can_express_a_volume_that_does_not_start_at_page_one():
    """Vol 1 No 2 runs pages 27-46. A single 'printed page 1 is sheet N' field
    cannot say that, and silently relabelled the whole issue 1, 2, 3..."""
    _tk, root = _tk_or_skip()
    from srebook.core.model import Issue
    from srebook.gui.app import App
    from srebook.gui.grid import OutlineGrid
    try:
        app = App(root)
        app.grid_model = OutlineGrid(Issue(), sheet_count=20)
        app.label_sheet_var.set("1")
        app.label_printed_var.set("27")

        app._collect_metadata()

        issue = app.grid_model.issue
        assert (issue.body_starts_at_sheet, issue.body_starts_at_printed) == (1, 27)
    finally:
        root.destroy()


def test_the_detected_page_mapping_is_shown_to_the_operator():
    """What the drafter worked out must appear in the fields, or the operator
    cannot tell it was detected -- nor correct it if it is wrong."""
    _tk, root = _tk_or_skip()
    from srebook.core.model import Issue
    from srebook.gui.app import App
    try:
        app = App(root)
        app.sheets = [None] * 20
        app._on_drafted(Issue(body_starts_at_sheet=1, body_starts_at_printed=27), True)

        assert app.label_sheet_var.get() == "1"
        assert app.label_printed_var.get() == "27"
    finally:
        root.destroy()


def test_the_status_line_distinguishes_the_two_kinds_of_review():
    """'7 need a sheet number' is wrong when most of them have a correct sheet
    and want a keep-or-remove decision instead."""
    _tk, root = _tk_or_skip()
    from srebook.core.model import Bookmark, Issue
    from srebook.gui.app import App
    try:
        app = App(root)
        app.sheets = [None] * 24
        app._on_drafted(Issue(bookmarks=[
            Bookmark("Front Cover", 1),
            Bookmark("Idaho Poetry", 1, needs_review=True, review_reason="unplaced"),
            Bookmark("Board of Directors", 24, needs_review=True,
                     review_reason="suggested"),
            Bookmark("Western History Books", 23, needs_review=True,
                     review_reason="suggested"),
        ]), True)

        status = app.status["text"]
        assert "1 need" in status or "1 needs" in status, status
        assert "2" in status, status
        assert "keep or remove" in status.lower(), status
    finally:
        root.destroy()


# ------------------------------------------------------- page labels ----
# Vol 1 No 2 was drafted as "sheet 1 is printed page 27" when its pages print
# 25 onward. Correcting the field changed nothing on screen, because the two
# entries were only read when saving, so the program looked as though it had
# stopped adjusting page numbers at all.

def _paginated_app(root, printed=27):
    from srebook.core.model import Bookmark, Issue
    from srebook.gui.app import App
    from srebook.gui.grid import OutlineGrid
    app = App(root)
    app.sheets = [None] * 20
    issue = Issue(body_starts_at_sheet=1, body_starts_at_printed=printed,
                  bookmarks=[Bookmark("Front Cover", 1), Bookmark("Article", 3)])
    app.grid_model = OutlineGrid(issue, sheet_count=20)
    app._refresh_tree()
    return app


def test_typing_a_new_starting_page_redraws_the_printed_column():
    _tk, root = _tk_or_skip()
    try:
        app = _paginated_app(root)
        assert app.tree.item("0", "values")[0] == "27"

        app.label_printed_var.set("25")

        assert app.tree.item("0", "values")[0] == "25"
        assert app.tree.item("1", "values")[0] == "27"
        assert app.grid_model.issue.body_starts_at_printed == 25
    finally:
        root.destroy()


def test_moving_the_anchor_sheet_redraws_the_front_matter_as_roman():
    _tk, root = _tk_or_skip()
    try:
        app = _paginated_app(root, printed=1)

        app.label_sheet_var.set("3")

        assert app.tree.item("0", "values")[0] == "i"
        assert app.tree.item("1", "values")[0] == "1"
    finally:
        root.destroy()


def test_clearing_the_field_to_retype_does_not_blank_the_column():
    """She must clear the box before typing a new number."""
    _tk, root = _tk_or_skip()
    try:
        app = _paginated_app(root)

        app.label_printed_var.set("")

        assert app.tree.item("0", "values")[0] == "27"
    finally:
        root.destroy()


def test_loading_a_drafted_issue_does_not_rewrite_its_mapping():
    """_on_drafted fills the fields in; that must not read straight back out
    and overwrite the mapping the drafter just detected."""
    _tk, root = _tk_or_skip()
    from srebook.core.model import Bookmark, Issue
    from srebook.gui.app import App
    try:
        app = _paginated_app(root)
        app._on_drafted(Issue(body_starts_at_sheet=1, body_starts_at_printed=49,
                              bookmarks=[Bookmark("Front Cover", 1)]), True)

        assert app.grid_model.issue.body_starts_at_printed == 49
        assert app.tree.item("0", "values")[0] == "49"
    finally:
        root.destroy()


# --------------------------------------------- pages not in the scan ----

def _gapped_app(root):
    from srebook.core.model import Bookmark, Issue
    from srebook.gui.app import App
    from srebook.gui.grid import OutlineGrid
    app = App(root)
    app.sheets = [None] * 20
    issue = Issue(body_starts_at_sheet=1, body_starts_at_printed=25,
                  bookmarks=[Bookmark("Front Cover", 1), Bookmark("Article", 3),
                             Bookmark("Later", 4)])
    app.grid_model = OutlineGrid(issue, sheet_count=20)
    app._refresh_tree()
    return app


def test_typing_a_gap_moves_the_pages_after_it():
    _tk, root = _tk_or_skip()
    try:
        app = _gapped_app(root)
        assert app.tree.item("2", "values")[0] == "28"

        app.missing_var.set("28, 29")

        assert app.tree.item("1", "values")[0] == "27"
        assert app.tree.item("2", "values")[0] == "30"
        assert app.grid_model.issue.missing_pages == [28, 29]
    finally:
        root.destroy()


def test_a_half_typed_gap_does_not_disturb_the_column():
    _tk, root = _tk_or_skip()
    try:
        app = _gapped_app(root)

        app.missing_var.set("28,")

        assert app.tree.item("2", "values")[0] == "28"
    finally:
        root.destroy()


def test_acknowledging_the_gap_clears_the_build_problem():
    _tk, root = _tk_or_skip()
    try:
        app = _gapped_app(root)
        app.missing_var.set("28, 29")
        assert app.grid_model.problems() != []

        app.acknowledge_gap()

        assert app.grid_model.problems() == []
    finally:
        root.destroy()


def test_a_bookmark_waiting_on_an_unscanned_page_is_counted_separately():
    _tk, root = _tk_or_skip()
    from srebook.core.model import Bookmark, Issue
    from srebook.gui.app import App
    try:
        app = App(root)
        app.sheets = [None] * 20
        app._on_drafted(Issue(missing_pages=[28], bookmarks=[
            Bookmark("Front Cover", 1),
            Bookmark("The Battle of Pierre's Hole", 1, needs_review=True,
                     review_reason="missing", missing_page=28),
            Bookmark("Community History", 1, needs_review=True,
                     review_reason="unplaced"),
        ]), False)

        status = app.status["text"]
        assert "not in this scan" in status.lower() or "not scanned" in status.lower(), status
        assert "1 need" in status or "1 needs" in status, status
    finally:
        root.destroy()
