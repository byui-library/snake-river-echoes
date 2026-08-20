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
        app.body_sheet_var.set("3")

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
