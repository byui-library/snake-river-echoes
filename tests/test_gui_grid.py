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


# ------------------------------------- entering printed pages, not sheets ----

def a_paginated_grid(bookmarks=None):
    """Vol 2 No 2: 24 sheets carrying printed pages 25-48."""
    issue = Issue(title="SRE", body_starts_at_sheet=1, body_starts_at_printed=25,
                  bookmarks=bookmarks or [])
    return grid.OutlineGrid(issue, sheet_count=24)


def test_the_grid_shows_the_printed_page_beside_the_sheet():
    g = a_paginated_grid([Bookmark("Front Cover", 1), Bookmark("Board", 24)])

    assert g.printed_display(0) == "25"
    assert g.printed_display(1) == "48"


def test_a_printed_page_can_be_entered_instead_of_a_sheet():
    """She reads 27 off the contents page; the program works out the sheet.
    Requiring her to compute 27 - 25 + 1 is what caused every bookmark in an
    issue to point past the end."""
    g = a_paginated_grid([Bookmark("Battle of Pierre's Hole", 1)])

    g.set_printed(0, 27)

    assert g.rows[0].sheet == 3
    assert g.printed_display(0) == "27"


def test_setting_a_printed_page_counts_as_reviewing_the_row():
    g = a_paginated_grid([Bookmark("Poetry", 1, needs_review=True)])

    g.set_printed(0, 30)

    assert not g.needs_attention(0)


def test_a_printed_page_outside_the_issue_is_refused():
    g = a_paginated_grid([Bookmark("Somewhere", 1)])

    assert not g.set_printed(0, 99)
    assert g.rows[0].sheet == 1, "the row is left as it was"


def test_front_matter_shows_the_label_the_pdf_will_carry():
    """Front matter is labelled i, ii in the finished PDF, so that is what the
    column shows. A dash would say "unknown", which is a different thing."""
    issue = Issue(title="SRE", body_starts_at_sheet=3, body_starts_at_printed=1,
                  bookmarks=[Bookmark("Front Cover", 1), Bookmark("Article", 3)])
    g = grid.OutlineGrid(issue, sheet_count=22)

    assert g.printed_display(0) == "i"
    assert g.printed_display(1) == "1"


def test_an_unplaced_bookmark_shows_no_printed_page_either():
    g = a_paginated_grid([Bookmark("Poetry", 1, needs_review=True)])

    assert g.printed_display(0) == "—"


def test_a_suggested_heading_shows_its_sheet():
    """We know exactly where it is -- we read it there. Only an unplaced title
    has a sheet worth hiding behind a dash."""
    g = a_paginated_grid([Bookmark("Board of Directors", 24, needs_review=True,
                                   review_reason="suggested")])

    assert g.sheet_display(0) == "24"
    assert g.printed_display(0) == "48"
    assert g.needs_attention(0), "still wants a decision, just not about where"


def test_an_unplaced_title_still_hides_its_placeholder_sheet():
    g = a_paginated_grid([Bookmark("Idaho Poetry", 1, needs_review=True,
                                   review_reason="unplaced")])

    assert g.sheet_display(0) == "—"


def test_front_matter_shows_its_roman_label_not_a_dash():
    """An operator asked whether the cover and contents could be roman. They
    can -- setting 'sheet 3 is printed page 1' does it -- but the column showed
    a dash, so there was nothing to tell her it had worked."""
    issue = Issue(title="SRE", body_starts_at_sheet=3, body_starts_at_printed=1,
                  bookmarks=[Bookmark("Front Cover", 1),
                             Bookmark("Table of Contents", 2),
                             Bookmark("Black Gold", 3)])
    g = grid.OutlineGrid(issue, sheet_count=22)

    assert g.printed_display(0) == "i"
    assert g.printed_display(1) == "ii"
    assert g.printed_display(2) == "1"


def test_an_unplaced_bookmark_still_shows_a_dash_not_a_numeral():
    """The dash means "no page known", which is different from "front matter"."""
    issue = Issue(title="SRE", body_starts_at_sheet=3, body_starts_at_printed=1,
                  bookmarks=[Bookmark("Poetry", 1, needs_review=True,
                                      review_reason="unplaced")])
    g = grid.OutlineGrid(issue, sheet_count=22)

    assert g.printed_display(0) == "—"


def test_a_roman_page_can_be_typed_back_in():
    """Whatever the column shows, the operator must be able to enter it."""
    issue = Issue(title="SRE", body_starts_at_sheet=3, body_starts_at_printed=1,
                  bookmarks=[Bookmark("Front Cover", 5)])
    g = grid.OutlineGrid(issue, sheet_count=22)

    assert g.set_printed_text(0, "ii")
    assert g.rows[0].sheet == 2


def test_an_arabic_page_still_works(): 
    issue = Issue(title="SRE", body_starts_at_sheet=3, body_starts_at_printed=1,
                  bookmarks=[Bookmark("Article", 1)])
    g = grid.OutlineGrid(issue, sheet_count=22)

    assert g.set_printed_text(0, "6")
    assert g.rows[0].sheet == 8
