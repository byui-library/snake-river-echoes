"""The bookmark grid's logic, which holds no widgets and imports no tkinter.

The grid is where the operator does the one job the machine cannot do, so its
rules are worth testing properly rather than trusting to the widget layer.
"""
import pytest

from srebook.core.model import Bookmark, Issue
from srebook.gui import grid


def rows_of(g):
    return [(r.title, r.sheet, r.level) for r in g.rows]


def a_grid(bookmarks=None):
    return grid.OutlineGrid(Issue(title="SRE", bookmarks=bookmarks or []), sheet_count=22)


# ----------------------------------------------------------- flattening ----

def test_nested_bookmarks_flatten_to_indented_rows():
    g = a_grid([
        Bookmark("Idaho Poetry", 19, children=[
            Bookmark("My Home in Idaho", 19), Bookmark("The Grand Old Snake", 21)]),
        Bookmark("Board of Directors", 22),
    ])

    assert rows_of(g) == [
        ("Idaho Poetry", 19, 0),
        ("My Home in Idaho", 19, 1),
        ("The Grand Old Snake", 21, 1),
        ("Board of Directors", 22, 0),
    ]


def test_rows_rebuild_into_the_same_nesting():
    original = [Bookmark("Poetry", 19, children=[Bookmark("Poem", 21)]),
                Bookmark("Board", 22)]
    g = a_grid(original)

    assert g.to_bookmarks() == original


def test_a_child_before_any_parent_is_promoted_when_rebuilt():
    """The grid must never produce a structure the model would reject."""
    g = a_grid()
    g.add(title="Orphan", sheet=3)
    g.rows[0].level = 1

    assert g.to_bookmarks() == [Bookmark("Orphan", 3)]


# ------------------------------------------------------------- editing ----

def test_add_appends_a_row():
    g = a_grid([Bookmark("First", 1)])

    g.add(title="Second", sheet=4)

    assert rows_of(g) == [("First", 1, 0), ("Second", 4, 0)]


def test_add_defaults_to_sheet_one_so_it_is_visible_and_wrong_not_hidden():
    g = a_grid()

    g.add()

    assert g.rows[0].sheet == 1


def test_remove_takes_the_children_with_it():
    g = a_grid([Bookmark("Poetry", 19, children=[Bookmark("Poem", 21)]),
                Bookmark("Board", 22)])

    g.remove(0)

    assert rows_of(g) == [("Board", 22, 0)]


def test_removing_a_child_leaves_the_parent():
    g = a_grid([Bookmark("Poetry", 19, children=[Bookmark("Poem", 21)])])

    g.remove(1)

    assert rows_of(g) == [("Poetry", 19, 0)]


def test_edit_changes_a_row():
    g = a_grid([Bookmark("Typo", 5)])

    g.edit(0, title="Fixed", sheet=6)

    assert rows_of(g) == [("Fixed", 6, 0)]


# ------------------------------------------------------------- nesting ----

def test_indent_makes_a_row_a_child_of_the_one_above():
    g = a_grid([Bookmark("Poetry", 19), Bookmark("Poem", 21)])

    g.indent(1)

    assert rows_of(g) == [("Poetry", 19, 0), ("Poem", 21, 1)]


def test_the_first_row_cannot_be_indented():
    """There is nothing above it to be a child of."""
    g = a_grid([Bookmark("First", 1)])

    assert not g.can_indent(0)


def test_a_row_cannot_be_indented_twice():
    """The outline is fixed at two levels; a third would silently flatten."""
    g = a_grid([Bookmark("Poetry", 19), Bookmark("Poem", 21)])
    g.indent(1)

    assert not g.can_indent(1)


def test_indenting_a_parent_that_has_children_is_refused():
    """It would drag its children to a third level."""
    g = a_grid([Bookmark("A", 1),
                Bookmark("Poetry", 19, children=[Bookmark("Poem", 21)])])

    assert not g.can_indent(1)


def test_outdent_promotes_a_child():
    g = a_grid([Bookmark("Poetry", 19, children=[Bookmark("Poem", 21)])])

    g.outdent(1)

    assert rows_of(g) == [("Poetry", 19, 0), ("Poem", 21, 0)]


def test_a_top_level_row_cannot_be_outdented():
    assert not a_grid([Bookmark("A", 1)]).can_outdent(0)


# -------------------------------------------------------------- moving ----

def test_move_up_swaps_with_the_row_above():
    g = a_grid([Bookmark("A", 1), Bookmark("B", 2)])

    g.move_up(1)

    assert rows_of(g) == [("B", 2, 0), ("A", 1, 0)]


def test_a_parent_moves_with_its_children():
    g = a_grid([Bookmark("A", 1),
                Bookmark("Poetry", 19, children=[Bookmark("Poem", 21)])])

    g.move_up(1)

    assert rows_of(g) == [("Poetry", 19, 0), ("Poem", 21, 1), ("A", 1, 0)]


def test_the_first_row_cannot_move_up():
    assert not a_grid([Bookmark("A", 1)]).can_move_up(0)


def test_the_last_row_cannot_move_down():
    g = a_grid([Bookmark("A", 1), Bookmark("B", 2)])

    assert not g.can_move_down(1)


# ---------------------------------------------------------- validation ----

def test_a_sheet_past_the_end_is_reported():
    g = a_grid([Bookmark("Nowhere", 99)])

    assert any("99" in p for p in g.problems())


def test_an_empty_title_is_reported():
    g = a_grid([Bookmark("  ", 3)])

    assert g.problems()


def test_a_sound_grid_reports_nothing():
    g = a_grid([Bookmark("Poetry", 19, children=[Bookmark("Poem", 21)])])

    assert g.problems() == []


def test_only_bookmarks_the_drafter_flagged_need_attention():
    """Both sit on sheet 1, but only one is unplaced. Inferring this from the
    sheet number mislabels a real Front Cover bookmark as unreviewed."""
    g = a_grid([Bookmark("Idaho Poetry", 1, needs_review=True),
                Bookmark("Front Cover", 1)])

    assert g.needs_attention(0)
    assert not g.needs_attention(1)


def test_editing_a_flagged_row_clears_the_flag():
    """The operator has now looked at it, which is what the flag was waiting for."""
    g = a_grid([Bookmark("Idaho Poetry", 1, needs_review=True)])

    g.edit(0, sheet=19)

    assert not g.needs_attention(0)


def test_the_flag_survives_a_save_and_reload(tmp_path):
    from srebook.core.model import load_sidecar
    g = a_grid([Bookmark("Idaho Poetry", 1, needs_review=True)])
    path = tmp_path / "x.srebook.json"

    g.save(path)

    assert load_sidecar(path).bookmarks[0].needs_review is True


# --------------------------------------------------------------- dirty ----

def test_a_fresh_grid_is_clean():
    assert not a_grid([Bookmark("A", 1)]).dirty


def test_editing_marks_the_grid_dirty():
    g = a_grid([Bookmark("A", 1)])

    g.edit(0, title="B")

    assert g.dirty


def test_saving_clears_dirty(tmp_path):
    g = a_grid([Bookmark("A", 1)])
    g.add()

    g.save(tmp_path / "x.srebook.json")

    assert not g.dirty


def test_saving_writes_the_edited_outline(tmp_path):
    from srebook.core.model import load_sidecar
    g = a_grid([Bookmark("Poetry", 19)])
    g.add(title="Poem", sheet=21)
    g.indent(1)
    path = tmp_path / "x.srebook.json"

    g.save(path)

    saved = load_sidecar(path)
    assert saved.bookmarks[0].children[0].title == "Poem"


def test_a_flagged_row_can_be_confirmed_without_changing_it():
    """The drafter parks an unlocated title on sheet 1. For a Front Cover that
    is the right answer, so the operator needs a way to say 'yes, that is
    correct' -- not only a way to change it."""
    g = a_grid([Bookmark("COVER", 1, needs_review=True)])

    g.confirm(0)

    assert not g.needs_attention(0)
    assert g.rows[0].sheet == 1
    assert g.dirty


def test_confirming_a_parent_confirms_its_children():
    g = a_grid([Bookmark("Poetry", 19, needs_review=True, children=[
        Bookmark("Poem", 21, needs_review=True)])])

    g.confirm(0)

    assert not any(r.needs_review for r in g.rows)


def test_confirming_an_already_reviewed_row_is_harmless():
    g = a_grid([Bookmark("Cover", 1)])

    g.confirm(0)

    assert not g.needs_attention(0)


def test_an_unplaced_bookmark_does_not_show_a_confident_sheet_number():
    """The drafter parks what it cannot find on sheet 1. Displaying "1" makes a
    placeholder look like an answer, and reads as though the bookmark points at
    the contents page."""
    g = a_grid([Bookmark("POETRY", 1, needs_review=True), Bookmark("Cover", 1)])

    assert g.sheet_display(0) == "—"
    assert g.sheet_display(1) == "1"


def test_confirming_reveals_the_sheet_number():
    g = a_grid([Bookmark("COVER", 1, needs_review=True)])

    g.confirm(0)

    assert g.sheet_display(0) == "1"
