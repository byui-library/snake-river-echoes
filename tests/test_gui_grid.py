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


# ------------------------------------------------ changing the mapping ----
# The operator types a starting printed page and expects every row to move
# with it. Vol 1 No 2 detected its cover as printed page 27 when the page
# itself prints 25, and correcting the field appeared to do nothing at all.

def test_setting_a_new_starting_page_moves_every_row():
    g = a_paginated_grid([Bookmark("Front Cover", 1), Bookmark("Article", 3),
                          Bookmark("Board", 24)])
    assert [g.printed_display(i) for i in range(3)] == ["25", "27", "48"]

    assert g.set_page_labels("1", "23")

    assert [g.printed_display(i) for i in range(3)] == ["23", "25", "46"]


def test_setting_a_new_starting_page_updates_the_range():
    g = a_paginated_grid([Bookmark("Front Cover", 1)])

    g.set_page_labels("1", "23")

    assert g.page_label_range() == "23 to 46"


def test_moving_the_anchor_sheet_makes_the_front_matter_roman():
    g = a_paginated_grid([Bookmark("Front Cover", 1), Bookmark("Contents", 2),
                          Bookmark("Article", 3)])

    assert g.set_page_labels("3", "1")

    assert [g.printed_display(i) for i in range(3)] == ["i", "ii", "1"]


def test_a_half_typed_field_leaves_the_mapping_alone():
    """She clears the box before typing the new number. Reading that as a
    change would blank the whole column mid-keystroke."""
    g = a_paginated_grid([Bookmark("Front Cover", 1)])

    assert not g.set_page_labels("1", "")
    assert not g.set_page_labels("", "25")
    assert not g.set_page_labels("1", "twenty")

    assert g.printed_display(0) == "25"


def test_there_is_no_printed_page_zero():
    g = a_paginated_grid([Bookmark("Front Cover", 1)])

    assert not g.set_page_labels("1", "0")
    assert not g.set_page_labels("0", "25")

    assert g.printed_display(0) == "25"


def test_an_anchor_past_the_last_sheet_is_refused():
    g = a_paginated_grid([Bookmark("Front Cover", 1)])

    assert not g.set_page_labels("25", "1")

    assert g.printed_display(0) == "25"


def test_setting_the_same_mapping_again_reports_no_change():
    """The widget layer redraws on a change; saying yes every keystroke would
    fight the operator's cursor."""
    g = a_paginated_grid([Bookmark("Front Cover", 1)])

    assert not g.set_page_labels("1", "25")


def test_changing_the_mapping_marks_the_issue_unsaved():
    g = a_paginated_grid([Bookmark("Front Cover", 1)])

    g.set_page_labels("1", "23")

    assert g.dirty


# ------------------------------------------------ pages not in the scan ----

def test_the_missing_pages_field_accepts_a_typed_list():
    g = a_paginated_grid()

    assert g.set_missing_pages("28, 29")

    assert g.issue.missing_pages == [28, 29]


def test_the_missing_list_is_shown_sorted_and_deduplicated():
    g = a_paginated_grid()

    g.set_missing_pages("29, 28, 29")

    assert g.missing_pages_text() == "28, 29"


def test_editing_the_missing_list_withdraws_the_acknowledgement():
    """A corrected gap must be looked at again before publishing."""
    g = a_paginated_grid()
    g.issue.gap_acknowledged = True

    g.set_missing_pages("28")

    assert g.issue.gap_acknowledged is False


def test_a_half_typed_missing_list_is_ignored():
    g = a_paginated_grid()
    g.set_missing_pages("28, 29")

    assert not g.set_missing_pages("28,")
    assert not g.set_missing_pages("twenty")

    assert g.issue.missing_pages == [28, 29]


def test_clearing_the_field_removes_every_gap():
    g = a_paginated_grid()
    g.set_missing_pages("28, 29")

    assert g.set_missing_pages("")

    assert g.issue.missing_pages == []


def test_setting_the_same_list_again_reports_no_change():
    g = a_paginated_grid()
    g.set_missing_pages("28, 29")

    assert not g.set_missing_pages("28, 29")


def test_a_gap_moves_the_printed_pages_after_it():
    g = a_paginated_grid([Bookmark("Article", 3), Bookmark("Later", 4)])
    g.set_page_labels("1", "25")

    g.set_missing_pages("28, 29")

    assert [g.printed_display(0), g.printed_display(1)] == ["27", "30"]


def test_a_missing_bookmark_shows_the_page_it_is_waiting_for():
    g = a_paginated_grid([
        Bookmark("The Battle of Pierre's Hole", 1, needs_review=True,
                 review_reason="missing", missing_page=28)])

    assert g.printed_display(0) == "28"
    assert g.sheet_display(0) == grid.UNPLACED_SHEET


def test_acknowledging_the_gap_is_remembered():
    g = a_paginated_grid()
    g.set_missing_pages("28, 29")

    g.acknowledge_gap()

    assert g.issue.gap_acknowledged is True


# ------------------------------------------------------ stepping sheets ----
# The outline lists articles, so a blank leaf appears nowhere in it. An
# operator checking a scan for completeness needs to walk every sheet.

def test_a_body_sheet_names_its_printed_page():
    g = a_paginated_grid()

    assert g.sheet_caption(3) == "Sheet 3 of 24 · printed page 27"


def test_a_front_matter_sheet_says_it_carries_no_printed_number():
    issue = Issue(title="SRE", body_starts_at_sheet=4, body_starts_at_printed=1)
    g = grid.OutlineGrid(issue, sheet_count=28)

    assert g.sheet_caption(2) == "Sheet 2 of 28 · front matter ii"


def test_stepping_moves_one_sheet():
    g = a_paginated_grid()

    assert g.step_sheet(5, 1) == 6
    assert g.step_sheet(5, -1) == 4


def test_stepping_stops_at_the_first_and_last_sheet():
    g = a_paginated_grid()

    assert g.step_sheet(1, -1) == 1
    assert g.step_sheet(24, 1) == 24


def test_a_sheet_outside_the_issue_is_pulled_back_in():
    g = a_paginated_grid()

    assert g.step_sheet(99, 1) == 24
    assert g.step_sheet(0, -1) == 1


# --------------------------------------------------------------- merge ----
# Vol 4 No 2 & 3 splits an article across two bookmarks: the title, then the
# byline. Retyping the title to join them by hand is what the operator was
# reduced to.

def test_merge_up_joins_the_titles():
    g = a_grid([Bookmark("The Rigby Star: 79 Years", 11),
                Bookmark("By A.R. Chandler", 11)])

    g.merge_up(1)

    assert rows_of(g) == [("The Rigby Star: 79 Years By A.R. Chandler", 11, 0)]


def test_merge_keeps_the_first_rows_sheet():
    """The title's sheet is where the article starts; the byline may have been
    parked somewhere else entirely."""
    g = a_grid([Bookmark("Heise Ferry Crossing", 12), Bookmark("By Virginia Morgan", 1)])

    g.merge_up(1)

    assert g.rows[0].sheet == 12


def test_merge_also_reunites_a_title_the_parser_split():
    g = a_grid([Bookmark("Jefferson Historical Society Seeks", 29),
                Bookmark("To Preserve County Heritage", 29)])

    g.merge_up(1)

    assert g.rows[0].title == "Jefferson Historical Society Seeks To Preserve County Heritage"


def test_merge_tidies_the_spacing():
    g = a_grid([Bookmark("Camus  ", 24), Bookmark("  By Ada Smith", 24)])

    g.merge_up(1)

    assert g.rows[0].title == "Camus By Ada Smith"


def test_the_first_row_cannot_merge_up():
    g = a_grid([Bookmark("Front Cover", 1)])

    assert not g.can_merge_up(0)


def test_a_row_with_children_cannot_merge_up():
    """Its children would be left with no parent."""
    g = a_grid([Bookmark("A", 1),
                Bookmark("Poetry", 19, children=[Bookmark("Poem", 21)])])

    assert not g.can_merge_up(1)


def test_merging_counts_as_reviewing_the_result():
    g = a_grid([Bookmark("Token Tales", 23),
                Bookmark("By Kendall Ballard", 1, needs_review=True,
                         review_reason="unplaced")])

    g.merge_up(1)

    assert not g.needs_attention(0)
    assert g.dirty


def test_merge_returns_the_surviving_row():
    g = a_grid([Bookmark("A", 1), Bookmark("B", 2), Bookmark("C", 3)])

    assert g.merge_up(2) == 1
    assert rows_of(g) == [("A", 1, 0), ("B C", 2, 0)]
