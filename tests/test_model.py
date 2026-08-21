import json

import pytest

from srebook.core.model import (Bookmark, Issue, load_sidecar, page_labels,
                                printed_for_sheet, save_sidecar,
                                sheet_for_printed, validate)


def an_issue(**kw):
    base = dict(title="Snake River Echoes", volume=1, issue=1, year=1971,
                publisher="Upper Snake River Valley Historical Society")
    base.update(kw)
    return Issue(**base)


# ---------------------------------------------------------------- sidecar ----

def test_sidecar_round_trips_an_issue(tmp_path):
    issue = an_issue(bookmarks=[Bookmark("Front Cover", 1), Bookmark("Andrew Henry", 11)])
    path = tmp_path / "x.srebook.json"

    save_sidecar(issue, path)

    assert load_sidecar(path) == issue


def test_sidecar_round_trips_nested_bookmarks(tmp_path):
    issue = an_issue(bookmarks=[
        Bookmark("Idaho Poetry", 19, children=[
            Bookmark("My Home in Idaho", 19),
            Bookmark("The Grand Old Snake", 21),
        ]),
    ])
    path = tmp_path / "x.srebook.json"

    save_sidecar(issue, path)
    loaded = load_sidecar(path)

    assert [c.title for c in loaded.bookmarks[0].children] == [
        "My Home in Idaho", "The Grand Old Snake"]


def test_sidecar_is_readable_json_a_person_could_hand_edit(tmp_path):
    path = tmp_path / "x.srebook.json"
    save_sidecar(an_issue(bookmarks=[Bookmark("Cover", 1)]), path)

    data = json.loads(path.read_text(encoding="utf-8"))

    assert data["bookmarks"] == [{"title": "Cover", "sheet": 1}]


def test_childless_bookmarks_omit_the_children_key(tmp_path):
    """Keeps hand-edited sidecars uncluttered."""
    path = tmp_path / "x.srebook.json"
    save_sidecar(an_issue(bookmarks=[Bookmark("Cover", 1)]), path)

    assert "children" not in json.loads(path.read_text(encoding="utf-8"))["bookmarks"][0]


def test_embed_dpi_defaults_to_200():
    assert an_issue().embed_dpi == 200


# ------------------------------------------------------------- page labels ----

def test_front_matter_is_roman_and_body_is_arabic():
    issue = an_issue(body_starts_at_sheet=3, body_starts_at_printed=1)

    assert page_labels(issue, sheet_count=6) == ["i", "ii", "1", "2", "3", "4"]


def test_body_can_start_at_a_printed_number_other_than_one():
    issue = an_issue(body_starts_at_sheet=2, body_starts_at_printed=7)

    assert page_labels(issue, sheet_count=5) == ["i", "7", "8", "9", "10"]


def test_issue_with_no_front_matter_is_all_arabic():
    issue = an_issue(body_starts_at_sheet=1, body_starts_at_printed=1)

    assert page_labels(issue, sheet_count=3) == ["1", "2", "3"]


def test_roman_numerals_pass_ten():
    issue = an_issue(body_starts_at_sheet=12, body_starts_at_printed=1)

    assert page_labels(issue, sheet_count=12)[8:11] == ["ix", "x", "xi"]


# -------------------------------------------------------------- validation ----

def test_bookmark_past_the_last_sheet_is_reported():
    issue = an_issue(bookmarks=[Bookmark("Nowhere", 99)])

    problems = validate(issue, sheet_count=22)

    assert any("99" in p and "Nowhere" in p for p in problems)


def test_bookmark_on_sheet_zero_is_reported():
    issue = an_issue(bookmarks=[Bookmark("Bad", 0)])

    assert validate(issue, sheet_count=22)


def test_nested_bookmark_out_of_range_is_reported():
    issue = an_issue(bookmarks=[Bookmark("Poetry", 19, children=[Bookmark("Deep", 99)])])

    assert any("Deep" in p for p in validate(issue, sheet_count=22))


def test_body_start_past_the_last_sheet_is_reported():
    assert validate(an_issue(body_starts_at_sheet=99), sheet_count=22)


def test_a_sound_issue_reports_no_problems():
    issue = an_issue(body_starts_at_sheet=3, bookmarks=[
        Bookmark("Cover", 1),
        Bookmark("Poetry", 19, children=[Bookmark("Poem", 21)]),
    ])

    assert validate(issue, sheet_count=22) == []


def test_empty_bookmark_title_is_reported():
    assert validate(an_issue(bookmarks=[Bookmark("   ", 3)]), sheet_count=22)


def test_nesting_deeper_than_two_levels_is_rejected():
    """The spec fixes the outline at two levels; three would silently flatten."""
    deep = Bookmark("A", 1, children=[Bookmark("B", 2, children=[Bookmark("C", 3)])])

    assert any("two levels" in p.lower() for p in validate(an_issue(bookmarks=[deep]), 22))


# ------------------------------------------------------- needs review ----

def test_a_bookmark_can_be_marked_as_needing_review(tmp_path):
    """The drafter records which titles it could not place, rather than the GUI
    guessing from 'sheet == 1' -- which mislabels a real Front Cover bookmark."""
    issue = an_issue(bookmarks=[Bookmark("Idaho Poetry", 1, needs_review=True),
                                Bookmark("Front Cover", 1)])
    path = tmp_path / "x.srebook.json"

    save_sidecar(issue, path)
    loaded = load_sidecar(path)

    assert loaded.bookmarks[0].needs_review is True
    assert loaded.bookmarks[1].needs_review is False


def test_reviewed_bookmarks_omit_the_flag(tmp_path):
    path = tmp_path / "x.srebook.json"
    save_sidecar(an_issue(bookmarks=[Bookmark("Cover", 1)]), path)

    assert "needs_review" not in json.loads(path.read_text(encoding="utf-8"))["bookmarks"][0]


def test_a_bookmark_still_flagged_for_review_blocks_the_build():
    """The drafter parks titles it cannot locate on sheet 1. Publishing that
    silently gives the reader a bookmark that goes to the wrong page with no
    indication anything is wrong."""
    issue = an_issue(bookmarks=[Bookmark("Front Cover", 1),
                                Bookmark("Idaho Poetry", 1, needs_review=True)])

    problems = validate(issue, sheet_count=22)

    assert any("Idaho Poetry" in p for p in problems)
    assert not any("Front Cover" in p for p in problems)


def test_the_review_message_says_what_to_do():
    issue = an_issue(bookmarks=[Bookmark("Idaho Poetry", 1, needs_review=True)])

    message = " ".join(validate(issue, sheet_count=22))

    assert "sheet" in message.lower()


def test_a_flagged_child_blocks_the_build_too():
    issue = an_issue(bookmarks=[Bookmark("Poetry", 19, children=[
        Bookmark("Poem", 1, needs_review=True)])])

    assert any("Poem" in p for p in validate(issue, sheet_count=22))


def test_a_reviewed_issue_still_builds():
    issue = an_issue(bookmarks=[Bookmark("Front Cover", 1), Bookmark("Poetry", 19)])

    assert validate(issue, sheet_count=22) == []


def test_the_review_message_offers_confirming_as_well_as_changing():
    """Sheet 1 is right for a Front Cover. The operator must be told they can
    confirm it, not only that they can change or delete it."""
    issue = an_issue(bookmarks=[Bookmark("COVER", 1, needs_review=True)])

    message = " ".join(validate(issue, sheet_count=22))

    assert "confirm" in message.lower()


# ------------------------------------- sheets and printed pages, both ways ----

def test_the_sheet_for_a_printed_page():
    """Vol 2 No 2 runs pages 25-48 across 24 sheets."""
    issue = an_issue(body_starts_at_sheet=1, body_starts_at_printed=25)

    assert sheet_for_printed(issue, 25) == 1
    assert sheet_for_printed(issue, 48) == 24


def test_the_printed_page_for_a_sheet():
    issue = an_issue(body_starts_at_sheet=1, body_starts_at_printed=25)

    assert printed_for_sheet(issue, 1) == 25
    assert printed_for_sheet(issue, 24) == 48


def test_front_matter_has_no_printed_page():
    issue = an_issue(body_starts_at_sheet=3, body_starts_at_printed=1)

    assert printed_for_sheet(issue, 1) is None
    assert printed_for_sheet(issue, 3) == 1


def test_printed_page_numbers_typed_into_the_sheet_column_are_recognised():
    """What actually happened: an operator read the numbers off the contents
    page and typed them into a column headed Sheet. Seventeen bookmarks then
    pointed past the end, and the program said so seventeen times."""
    issue = an_issue(body_starts_at_sheet=1, body_starts_at_printed=25,
                     bookmarks=[Bookmark("Front Cover", 25),
                                Bookmark("Table of Contents", 26),
                                Bookmark("Board of Directors", 48)])

    problems = validate(issue, sheet_count=24)

    assert len(problems) == 1, "one explanation, not one per bookmark"
    joined = problems[0].lower()
    assert "printed page" in joined
    assert "sheet" in joined


def test_a_single_bookmark_past_the_end_is_still_reported_plainly():
    """Not every out-of-range bookmark is the printed-page mistake."""
    issue = an_issue(bookmarks=[Bookmark("Nowhere", 99)])

    problems = validate(issue, sheet_count=22)

    assert any("Nowhere" in p and "99" in p for p in problems)


# ------------------------------- two different reasons to want a second look ----

def test_an_unplaced_title_says_its_sheet_is_a_guess():
    issue = an_issue(bookmarks=[Bookmark("Idaho Poetry", 1, needs_review=True,
                                         review_reason="unplaced")])

    message = validate(issue, sheet_count=22)[0]

    assert "not found in the body" in message
    assert "guess" in message


def test_a_suggested_heading_says_where_it_was_found():
    """It was found in the body -- that is where it came from. What is uncertain
    is whether it is an article, not where it is. Telling the operator to 'set
    the sheet it really starts on' is simply wrong for these."""
    issue = an_issue(bookmarks=[Bookmark("Board of Directors", 24, needs_review=True,
                                         review_reason="suggested")])

    message = validate(issue, sheet_count=24)[0]

    assert "sheet 24" in message
    assert "not listed on the contents page" in message
    assert "guess" not in message


def test_the_reason_survives_the_sidecar(tmp_path):
    issue = an_issue(bookmarks=[Bookmark("Board", 24, needs_review=True,
                                         review_reason="suggested")])
    path = tmp_path / "x.srebook.json"

    save_sidecar(issue, path)

    assert load_sidecar(path).bookmarks[0].review_reason == "suggested"


def test_a_reviewed_bookmark_carries_no_reason(tmp_path):
    path = tmp_path / "x.srebook.json"
    save_sidecar(an_issue(bookmarks=[Bookmark("Cover", 1)]), path)

    assert "review_reason" not in json.loads(path.read_text(encoding="utf-8"))["bookmarks"][0]
