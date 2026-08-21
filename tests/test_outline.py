"""The outline parser, tested against what Tesseract really produced for
Vol 1 No 1 -- dot leaders read as noise and all.
"""
from srebook.core import outline

# Verbatim OCR of the contents page (sheet 2), from the Phase 0 spike.
REAL_TOC = [
    "THE UPPER SNAKE RIVER VALLEY HISTORICAL SOCIETY QUARTERLY",
    "Summer Issue, 1971 Volume 1, Number 1",
    "CONTENTS",
    "A GOAL IS ACHIEVED ne",
    "The editors comment about the Historical Society and its",
    "contributions to the furtherment. of the heritage of",
    "Eastern [dahiog 666037. FO ek ee ee ee mS",
    "ORAL HISTORY",
    "by Harold S. Forbush A program of recorded history of",
    "men and women who helped to make the events. ........ .'4",
    "EASTERN IDAHO HISTORY FAIR - 1971",
    "An experiment in the display of artifacts and heritage",
    "which drew interesite from ale over the states. 276. ee 7",
    "A BRIEF AUTOBIOGRAPHY AND ACCUMULATIVE HISTORY",
    "by J. Edgar Birch. A unique and interesting history of",
    "ANDREW HENRY",
    "by Louis J. Clements. A biography of the mountain man",
    "IDAHO POETRY",
    "by J. Bdgan Biren ee cs ie eae ee hse oO",
]

REAL_BODY = {
    3: ["A GOAL IS ACHIEVED!", "The Upper Snake River Valley"],
    4: ["4", "of the Historical Society,", "ORAL HISTORY"],
    5: ["The introduction of the magnetic"],
    6: ["6", "and a copy made of the original, so"],
    7: ["EASTERN IDAHO HISTORY FAIR - 1971", "An experiment"],
    8: ["8", "A BRIEF AUTOBIOGRAPHY", "There were several rifles"],
    9: ["dug into the bank of a native slough"],
    10: ["10", "know that the society will both"],
    11: ["ANDREW HENRY - FUR TRAPPER", "Andrew Henry was born in Fayette"],
    12: ["12", "commented about, He was tall and"],
}


# ------------------------------------------------------- candidate titles ----

def test_titles_survive_the_dot_leaders():
    """Tesseract reads rows of periods as random letters and swallows the page
    number with them. The title in front of the leader is still clean."""
    titles = outline.candidate_titles(REAL_TOC)

    assert "A GOAL IS ACHIEVED" in titles
    assert "ORAL HISTORY" in titles
    assert "EASTERN IDAHO HISTORY FAIR - 1971" in titles


def test_author_credits_are_not_mistaken_for_titles():
    """Capitalisation must be tested on the RAW line. Stripping lowercase first
    turns 'by Harold S. Forbush' into the plausible-looking title 'H S F'."""
    titles = outline.candidate_titles(REAL_TOC)

    assert not any("FORBUSH" in t.upper() for t in titles)
    assert not any(t.replace(" ", "") in ("HSF", "HSFA", "JEB") for t in titles)


def test_masthead_above_the_contents_heading_is_skipped():
    titles = outline.candidate_titles(REAL_TOC)

    assert not any("QUARTERLY" in t for t in titles)
    assert "CONTENTS" not in titles


def test_description_lines_are_not_titles():
    titles = outline.candidate_titles(REAL_TOC)

    assert not any(t.startswith("The editors comment") for t in titles)


def test_the_real_contents_page_yields_exactly_the_articles():
    assert outline.candidate_titles(REAL_TOC) == [
        "A GOAL IS ACHIEVED",
        "ORAL HISTORY",
        "EASTERN IDAHO HISTORY FAIR - 1971",
        "A BRIEF AUTOBIOGRAPHY AND ACCUMULATIVE HISTORY",
        "ANDREW HENRY",
        "IDAHO POETRY",
    ]


def test_titles_are_not_repeated():
    assert outline.candidate_titles(["CONTENTS", "ORAL HISTORY", "ORAL HISTORY"]) == [
        "ORAL HISTORY"]


def test_a_page_with_no_contents_heading_still_yields_titles():
    """Not every issue prints the word CONTENTS."""
    assert outline.candidate_titles(["ORAL HISTORY", "by someone"]) == ["ORAL HISTORY"]


def test_very_short_all_caps_fragments_are_ignored():
    assert outline.candidate_titles(["CONTENTS", "A B", "OK", "ORAL HISTORY"]) == [
        "ORAL HISTORY"]


# ---------------------------------------------------------- locating them ----

def test_a_title_is_located_where_its_article_begins():
    located = outline.locate_titles(["ORAL HISTORY"], REAL_BODY)

    assert located == [("ORAL HISTORY", 4)]


def test_a_body_heading_may_carry_extra_words():
    """The contents says 'ANDREW HENRY'; the article says
    'ANDREW HENRY - FUR TRAPPER'."""
    assert outline.locate_titles(["ANDREW HENRY"], REAL_BODY) == [("ANDREW HENRY", 11)]


def test_a_body_heading_may_be_shorter_than_the_contents_entry():
    located = outline.locate_titles(["A BRIEF AUTOBIOGRAPHY AND ACCUMULATIVE HISTORY"],
                                    REAL_BODY)

    assert located == [("A BRIEF AUTOBIOGRAPHY AND ACCUMULATIVE HISTORY", 8)]


def test_punctuation_differences_do_not_prevent_a_match():
    """Contents: 'A GOAL IS ACHIEVED'. Body: 'A GOAL IS ACHIEVED!'."""
    assert outline.locate_titles(["A GOAL IS ACHIEVED"], REAL_BODY) == [
        ("A GOAL IS ACHIEVED", 3)]


def test_a_title_never_printed_in_the_body_is_reported_unlocated():
    """'IDAHO POETRY' is a section label. The operator supplies its sheet."""
    assert outline.locate_titles(["IDAHO POETRY"], REAL_BODY) == [("IDAHO POETRY", None)]


def test_the_earliest_occurrence_wins():
    body = {3: ["ORAL HISTORY"], 9: ["ORAL HISTORY"]}

    assert outline.locate_titles(["ORAL HISTORY"], body) == [("ORAL HISTORY", 3)]


def test_a_short_title_does_not_match_a_passing_mention():
    """'ANDREW HENRY' as running prose must not outrank the real heading."""
    body = {3: ["Andrew Henry was born in Fayette County"], 11: ["ANDREW HENRY"]}

    assert outline.locate_titles(["ANDREW HENRY"], body) == [("ANDREW HENRY", 11)]


def test_the_whole_real_contents_page_resolves():
    titles = outline.candidate_titles(REAL_TOC)
    located = dict(outline.locate_titles(titles, REAL_BODY))

    assert located["A GOAL IS ACHIEVED"] == 3
    assert located["ORAL HISTORY"] == 4
    assert located["EASTERN IDAHO HISTORY FAIR - 1971"] == 7
    assert located["A BRIEF AUTOBIOGRAPHY AND ACCUMULATIVE HISTORY"] == 8
    assert located["ANDREW HENRY"] == 11
    assert located["IDAHO POETRY"] is None


# ------------------------------------------------- detecting page numbers ----

def test_body_start_is_extrapolated_back_to_printed_page_one():
    """Sheet 4 prints '4' and sheet 6 prints '6', so sheet number equals printed
    page number -- which means printed page 1 is sheet 1, not sheet 4. Returning
    the first *numbered* sheet would label sheets 1-3 as roman i, ii, iii."""
    assert outline.detect_body_start(REAL_BODY) == (1, 1)


def test_body_start_extrapolates_across_an_offset():
    """Sheet 4 prints '2', so the offset is 2 and printed page 1 is sheet 3 --
    even though sheet 3 prints no number of its own."""
    body = {3: ["text"], 4: ["2", "text"], 6: ["4", "text"], 8: ["6", "text"]}

    assert outline.detect_body_start(body) == (3, 1)


def test_extrapolation_never_runs_off_the_front_of_the_issue():
    """If the body's first printed number is high, printed page 1 would land
    before sheet 1. Clamp instead."""
    body = {1: ["9", "text"], 2: ["10", "text"]}

    assert outline.detect_body_start(body) == (1, 9)


def test_body_start_returns_none_when_no_numbers_are_printed():
    assert outline.detect_body_start({3: ["text"], 4: ["more text"]}) is None


def test_a_single_stray_number_is_not_enough_to_conclude():
    """One match is coincidence. The offset has to repeat."""
    assert outline.detect_body_start({3: ["text"], 7: ["99"], 8: ["text"]}) is None


# ------------------------------------------------ where the contents page is ----

def test_the_contents_sheet_is_found_by_its_heading():
    """Titles must be located in the BODY, not matched against their own entry
    on the contents page."""
    sheets = {1: ["THE UPPER SNAKE RIVER VALLEY"], 2: REAL_TOC, 3: ["A GOAL IS ACHIEVED!"]}

    assert outline.find_contents_sheet(sheets) == 2


def test_contents_sheet_defaults_to_the_first_sheet_when_unmarked():
    """Not every issue prints the word CONTENTS."""
    assert outline.find_contents_sheet({1: ["ORAL HISTORY"], 2: ["prose"]}) == 1


def test_contents_heading_is_not_sought_deep_inside_the_issue():
    """A body page mentioning 'contents' must not be mistaken for the TOC."""
    sheets = {1: ["COVER"], 2: ["prose"], 9: ["CONTENTS"]}

    assert outline.find_contents_sheet(sheets) == 1


def test_trailing_leader_noise_is_stripped_from_titles():
    """Real OCR: 'WHO AND WHAT IN IDAHO. 99939) 0 2 Ao a'."""
    titles = outline.candidate_titles(
        ["CONTENTS", "WHO AND WHAT IN IDAHO. 99939) 0 2 Ao a"])

    assert titles == ["WHO AND WHAT IN IDAHO"]


def test_a_year_at_the_end_of_a_title_is_kept():
    """'EASTERN IDAHO HISTORY FAIR - 1971' ends in a number that belongs."""
    titles = outline.candidate_titles(["CONTENTS", "EASTERN IDAHO HISTORY FAIR - 1971"])

    assert titles == ["EASTERN IDAHO HISTORY FAIR - 1971"]


# ------------------------------------ real OCR from Vol 1 No 2 (a second issue) ----

REAL_TOC_2 = [
    "THE UPPER SNAKE RIVER VALLEY",
    "HISTORICAL SOCIETY QUARTERLY",
    "Fall Issue, 1971 Volume 1, Number 2",
    ". \u201cCONTENTS",
    "EASTERN IDAHO REVISITED!",
    "The Editor describes the early history of the area covered by the",
    "Historical Society 27",
    "THE BALTLE OF PIERRE\u2019S HOLE",
    "By Wendell Gillette. The story of this historic battle between the",
    "Valley, : __ 28",
    "ANNUAL FALL PUBLIC MEETING ANNOUNCEMENT 30",
    "COMMUNITY HISTORY",
    "Chapin is the town chosen for this publication to have its history",
    "told 31",
    "POETRY a i 83, 44, 45",
    "1971 SUMMER FIELD TRIP | 34",
    "PICTURES OF SUMMER FIELD TRIP 36-37",
    "THE COLLECTION OF HISTORICAL DOCUMENTS:",
    "A CITIZENS RESPONSIBILITY",
    "By Jerry L. Glenn. Mr. Glenn as a librarian at Ricks College is",
    "CHIEF TARGHEE",
    "By Brigham D. Madsen. This information reveals the life and",
    "BOOK LIST 46",
]


def test_a_title_continued_onto_a_second_line_is_one_bookmark_not_two():
    """Real failure on Vol 1 No 2: 'THE COLLECTION OF HISTORICAL DOCUMENTS:'
    and 'A CITIZENS RESPONSIBILITY' are one article, and produced two bookmarks
    both pointing at the same sheet."""
    titles = outline.candidate_titles(REAL_TOC_2)

    assert "THE COLLECTION OF HISTORICAL DOCUMENTS: A CITIZENS RESPONSIBILITY" in titles
    assert "A CITIZENS RESPONSIBILITY" not in titles


def test_two_unrelated_titles_in_a_row_stay_separate():
    """The line before ends with its page number, so it is complete."""
    titles = outline.candidate_titles(REAL_TOC_2)

    assert "ANNUAL FALL PUBLIC MEETING ANNOUNCEMENT" in titles
    assert "COMMUNITY HISTORY" in titles


def test_a_title_is_not_lost_to_trailing_page_number_debris():
    """'POETRY a i 83, 44, 45' was discarded entirely, so the operator never
    learned the issue had a poetry section. A flagged bookmark they must place
    beats an omission they will never notice."""
    assert "POETRY" in outline.candidate_titles(REAL_TOC_2)


def test_page_numbers_are_stripped_from_titles():
    titles = outline.candidate_titles(REAL_TOC_2)

    assert "BOOK LIST" in titles
    assert not any(t.endswith("46") for t in titles)


def test_the_second_issue_yields_its_articles():
    titles = outline.candidate_titles(REAL_TOC_2)

    assert titles == [
        "EASTERN IDAHO REVISITED!",
        "THE BALTLE OF PIERRE\u2019S HOLE",
        "ANNUAL FALL PUBLIC MEETING ANNOUNCEMENT",
        "COMMUNITY HISTORY",
        "POETRY",
        "1971 SUMMER FIELD TRIP",
        "PICTURES OF SUMMER FIELD TRIP",
        "THE COLLECTION OF HISTORICAL DOCUMENTS: A CITIZENS RESPONSIBILITY",
        "CHIEF TARGHEE",
        "BOOK LIST",
    ]


def test_the_first_issue_still_yields_exactly_its_articles():
    """Tuning for the second issue must not cost the first."""
    assert outline.candidate_titles(REAL_TOC) == [
        "A GOAL IS ACHIEVED",
        "ORAL HISTORY",
        "EASTERN IDAHO HISTORY FAIR - 1971",
        "A BRIEF AUTOBIOGRAPHY AND ACCUMULATIVE HISTORY",
        "ANDREW HENRY",
        "IDAHO POETRY",
    ]


# --------------------------- real OCR from Vol 1 No 3: a Title Case contents ----

REAL_TOC_3 = [
    "THE UPPER SNAKE RIVER VALLEY",
    "HISTORICAL SOCIETY QUARTERLY",
    "Winter Issue, 1971-1972",
    "Contents",
    "A Critical Look at Historical Editing",
    "The editor discusses the problems of writing history when",
    "Volume 1, Number 3",
    "The Massacre on Birch Creek",
    "War as it occured in Clark County",
    "Idaho Merchants Tokens",
    "Illustrations",
    "Community History",
    "its history told",
    "Annual Fall Public Meeting \u2018",
    "a knowledge of the area being written about is not clear 51",
    "By De Cost Smith. The story of part of the Nez Perce",
    "by Kendall Lee Ballard. An explanation of tokens and how",
]

REAL_BODY_3 = {
    3: ["A CRITICAL LOOK AT HISTORICAL EDITING", "As you wander through the libraries"],
    4: ["THE MASSACRE ON BIRCH CREEK", "The Editor"],
    8: ["IDAHO MERCHANTS TOKENS", "by Kendall Lee Ballard"],
    12: ["ANNUAL FALL PUBLIC MEETING", "This year the public meetings"],
}


def test_a_title_case_contents_page_yields_nothing_on_its_own():
    """Vol 1 No 3 sets its contents in Title Case, not caps. The strict rule
    finds nothing there, which is correct -- it cannot tell a title from a
    description line by capitalisation alone."""
    assert outline.candidate_titles(REAL_TOC_3) == []


def test_title_case_entries_are_offered_as_loose_candidates():
    loose = outline.loose_titles(REAL_TOC_3)

    assert "A Critical Look at Historical Editing" in loose
    assert "The Massacre on Birch Creek" in loose
    assert "Idaho Merchants Tokens" in loose


def test_description_lines_are_not_loose_candidates():
    """'War as it occured in Clark County' reads like a title but is a
    description; a lowercase word of real length gives it away."""
    loose = outline.loose_titles(REAL_TOC_3)

    assert "War as it occured in Clark County" not in loose
    assert not any(t.startswith("The editor discusses") for t in loose)
    assert not any(t.startswith("its history") for t in loose)
    assert not any("knowledge of the area" in t for t in loose)


def test_a_title_case_issue_resolves_against_its_body():
    """Loose candidates are only trustworthy once the body confirms them."""
    located = dict(outline.locate_titles(outline.loose_titles(REAL_TOC_3), REAL_BODY_3))

    assert located["A Critical Look at Historical Editing"] == 3
    assert located["The Massacre on Birch Creek"] == 4
    assert located["Idaho Merchants Tokens"] == 8
    assert located["Annual Fall Public Meeting"] == 12
    # Front-matter noise that happens to look like a title finds nothing.
    assert located.get("Volume 1, Number 3") is None


def test_an_all_caps_issue_produces_no_extra_loose_candidates():
    """Vol 1 No 1 is already handled strictly; loose matching must not add
    duplicates of what the strict pass already found."""
    strict = set(outline.candidate_titles(REAL_TOC))

    assert not (set(outline.loose_titles(REAL_TOC)) & strict)


def test_a_confirmed_loose_title_takes_its_wording_from_the_body():
    """Contents lines in small type OCR badly: 'Long Distance Rides and
    Raids" : ; tae' and 'Library Revi a ='. The printed heading is set larger,
    reads cleanly, and is the authoritative wording anyway."""
    toc = ["Contents", 'Long Distance Rides and Raids\u201d : ; tae', "Library Revi a ="]
    body = {18: ["66", "LONG DISTANCE RIDES AND RAIDS", "BY Lieutenant Colonel"],
            22: ["70", "LIBRARY HISTORY COLLECTIONS", "The Upper Snake River"]}

    found = outline.locate_loose_titles(outline.loose_titles(toc), body)

    assert ("Long Distance Rides and Raids", 18) in found


def test_a_contents_line_too_garbled_to_confirm_is_dropped():
    """'Library Revi a =' is not a prefix of the printed 'LIBRARY HISTORY
    COLLECTIONS', so nothing confirms it. Dropping it loses a real article the
    operator must add by hand -- which is better than publishing a bookmark
    titled "Library Revi". A known limitation, recorded rather than hidden."""
    body = {22: ["70", "LIBRARY HISTORY COLLECTIONS", "The Upper Snake River"]}

    found = outline.locate_loose_titles(outline.loose_titles(
        ["Contents", "Library Revi a ="]), body)

    assert found == []


def test_body_wording_is_presented_in_title_case():
    """A bookmark panel of shouting caps is harder to scan than title case."""
    body = {3: ["A CRITICAL LOOK AT HISTORICAL EDITING"]}

    found = outline.locate_loose_titles(["A Critical Look at Historical Editing"], body)

    assert found == [("A Critical Look at Historical Editing", 3)]


def test_title_case_keeps_numbers_and_marks_intact():
    body = {16: ["DEDICATION OF MARKER #378"]}

    found = outline.locate_loose_titles(["Dedication of Marker #378 of the Daughters"], body)

    assert found == [("Dedication of Marker #378", 16)]


def test_an_unconfirmed_loose_title_is_not_returned():
    assert outline.locate_loose_titles(["Volume 1, Number 3"], {3: ["prose here"]}) == []


def test_a_one_word_fragment_does_not_claim_a_longer_title():
    """A stray 'LIBRARY' on the page is not the heading for 'Library Revi'.
    The shorter-heading rule exists for real abbreviations like 'A BRIEF
    AUTOBIOGRAPHY', not for single words."""
    body = {22: ["LIBRARY", "LIBRARY HISTORY COLLECTIONS"]}

    assert outline.locate_loose_titles(["Library Revi"], body) == []


def test_a_genuinely_shortened_heading_still_matches():
    """Vol 1 No 1: contents says 'A BRIEF AUTOBIOGRAPHY AND ACCUMULATIVE
    HISTORY', the article is headed 'A BRIEF AUTOBIOGRAPHY'."""
    located = outline.locate_titles(["A BRIEF AUTOBIOGRAPHY AND ACCUMULATIVE HISTORY"],
                                    {8: ["8", "A BRIEF AUTOBIOGRAPHY"]})

    assert located == [("A BRIEF AUTOBIOGRAPHY AND ACCUMULATIVE HISTORY", 8)]


# ------------------- Vol 1 No 4: the contents marker is buried in a header line ----

def test_a_contents_marker_inside_a_header_line_is_found():
    """Vol 1 No 4 prints 'Spring Issue, 1972 CONTENTS Volume 1, Number 4' as a
    single line. Requiring the line to be exactly CONTENTS missed it, the
    contents page was never found, and the cover's masthead became the outline."""
    sheets = {
        1: ["UPPER SNAKE RIVER VALLEY", "HISTORICAL SOCIETY", "QUARTERLY"],
        2: ["THE UPPER SNAKE RIVER VALLEY HISTORICAL SOCIETY QUARTERLY",
            "Spring Issue, 1972 CONTENTS Volume 1, Number 4",
            "Editorial"],
    }

    assert outline.find_contents_sheet(sheets) == 2


def test_the_masthead_above_an_inline_contents_marker_is_skipped():
    lines = [
        "UPPER SNAKE RIVER VALLEY",
        "HISTORICAL SOCIETY",
        "QUARTERLY",
        "VOLUME 1 NUMBER 4 SPRING 1972 . $1.25",
        "Spring Issue, 1972 CONTENTS Volume 1, Number 4",
        "SOMETHING REAL",
    ]

    titles = outline.candidate_titles(lines)

    assert titles == ["SOMETHING REAL"]


def test_the_word_contents_in_running_prose_is_not_a_marker():
    """A body page discussing 'the contents of the collection' must not be
    mistaken for the contents page."""
    sheets = {1: ["COVER"],
              2: ["we catalogued the contents of the collection in detail"]}

    assert outline.find_contents_sheet(sheets) == 1


def test_the_contents_sheet_is_reported_as_undetected_when_absent():
    """find_contents_sheet falls back to the first sheet so the title search
    has somewhere to start. The caller still needs to know it was a fallback,
    or it would bookmark sheet 1 as a contents page that does not exist."""
    assert outline.detect_contents_sheet({1: ["COVER"], 2: ["prose"]}) is None


def test_the_contents_sheet_is_reported_when_present():
    sheets = {1: ["COVER"], 2: ["CONTENTS", "ORAL HISTORY"], 3: ["ORAL HISTORY"]}

    assert outline.detect_contents_sheet(sheets) == 2


# ---------------------------------------- title case, asked for by an archivist ----

def test_shouting_titles_become_title_case():
    assert outline.title_case("A GOAL IS ACHIEVED") == "A Goal Is Achieved"
    assert outline.title_case("ORAL HISTORY") == "Oral History"


def test_minor_words_stay_lower_case():
    assert outline.title_case("WHO AND WHAT IN IDAHO") == "Who and What in Idaho"


def test_the_first_word_is_capitalised_even_if_minor():
    assert outline.title_case("THE MASSACRE ON BIRCH CREEK") == "The Massacre on Birch Creek"


def test_a_word_after_a_colon_is_capitalised():
    """'...DOCUMENTS: A CITIZENS RESPONSIBILITY' -- the A begins a new phrase."""
    assert outline.title_case("THE COLLECTION OF HISTORICAL DOCUMENTS: A CITIZENS RESPONSIBILITY") \
        == "The Collection of Historical Documents: A Citizens Responsibility"


def test_words_that_begin_with_a_number_still_capitalise_their_letters():
    assert outline.title_case("1971-SUMMER FIELD TRIP") == "1971-Summer Field Trip"


def test_an_apostrophe_does_not_start_a_new_word():
    assert outline.title_case("PIERRE'S HOLE RENDEZVOUS") == "Pierre's Hole Rendezvous"
    assert outline.title_case("THE BATTLE OF PIERRE\u2019S HOLE") \
        == "The Battle of Pierre\u2019s Hole"


def test_a_year_or_number_is_left_alone():
    assert outline.title_case("EASTERN IDAHO HISTORY FAIR - 1971") \
        == "Eastern Idaho History Fair - 1971"
    assert outline.title_case("DEDICATION OF MARKER #378") == "Dedication of Marker #378"


def test_already_cased_titles_are_not_disturbed():
    """An operator's own wording, and titles taken from a Title Case contents
    page, must survive unchanged."""
    assert outline.title_case("A Critical Look at Historical Editing") \
        == "A Critical Look at Historical Editing"


# ------------- headings the contents page never lists, asked for by an archivist ----

def test_a_poem_headed_in_the_body_is_offered_as_its_own_bookmark():
    """The contents page says only "IDAHO POETRY". The poems carry their own
    printed headings, and an archivist wants those, not the category."""
    body = {19: ["MY HOME IN IDAHO", "by J. Edgar Birch", "I come to this place"],
            21: ["THE GRAND OLD SNAKE", "by J. Edgar Birch", "So oft I've sat"]}

    found = outline.unclaimed_headings(body, claimed=["Idaho Poetry"])

    assert ("My Home in Idaho", 19) in found
    assert ("The Grand Old Snake", 21) in found


def test_a_heading_already_claimed_is_not_offered_twice():
    body = {4: ["ORAL HISTORY", "The introduction of the recorder"]}

    assert outline.unclaimed_headings(body, claimed=["Oral History"]) == []


def test_a_running_head_is_not_offered():
    """The society's name across the top of every page is not an article."""
    body = {s: ["UPPER SNAKE RIVER VALLEY HISTORICAL SOCIETY", "prose"]
            for s in range(3, 9)}

    assert outline.unclaimed_headings(body, claimed=[]) == []


def test_prose_is_not_offered():
    body = {5: ["As you wander through the libraries of Idaho and look for books"]}

    assert outline.unclaimed_headings(body, claimed=[]) == []


def test_a_heading_deep_in_the_page_is_not_offered():
    """An article opens at the top of its page. A shout mid-column is usually a
    pull quote or a subheading."""
    body = {5: ["prose", "prose", "prose", "prose", "SOMETHING SHOUTED"]}

    assert outline.unclaimed_headings(body, claimed=[]) == []


def test_the_earliest_sheet_wins_for_a_repeated_heading():
    body = {7: ["CHIEF TARGHEE", "prose"], 9: ["CHIEF TARGHEE", "prose"]}

    assert outline.unclaimed_headings(body, claimed=[]) == [("Chief Targhee", 7)]


def test_index_entries_are_not_offered_as_headings():
    """Vol 1 No 4 ends with a volume index set in caps."""
    body = {20: ["AHLSTROM, PETER, 61, 91", "GLASS, HUGH, 15, 17"]}

    assert outline.unclaimed_headings(body, claimed=[]) == []


def test_a_caption_sentence_is_not_offered():
    body = {14: ["TRANSPORTATION IN EASTERN IDAHO WAS OF GRAVE CONCERN TO THOSE "
                 "INTERESTED IN THE BUILDING UP OF COMMUNITIES AND TRADE."]}

    assert outline.unclaimed_headings(body, claimed=[]) == []


def test_a_fragment_of_a_claimed_title_is_not_offered():
    """The body splits 'THE COLLECTION OF HISTORICAL DOCUMENTS: A CITIZENS
    RESPONSIBILITY' over two lines; neither half is a new article."""
    body = {12: ["THE COLLECTION OF HISTORICAL", "DOCUMENTS", "A CITIZENS RESPONSIBILITY"]}

    found = outline.unclaimed_headings(
        body, claimed=["The Collection of Historical Documents: A Citizens Responsibility"])

    assert found == []


def test_ocr_debris_is_stripped_from_a_suggested_heading():
    """Real output: 'WESTERN HISTORY BOOKS é' -- a stray letter the scanner
    found in the margin."""
    body = {23: ["WESTERN HISTORY BOOKS \u00e9", "The following list of books"]}

    assert outline.unclaimed_headings(body, claimed=[]) == [("Western History Books", 23)]


# -------------------------------- page numbers the contents page cites ----

def test_page_numbers_are_read_off_the_contents_page():
    lines = ["CONTENTS",
             "Historical Society 27",
             "Valley, : __ 28",
             "ANNUAL FALL PUBLIC MEETING ANNOUNCEMENT 30",
             "told 31",
             "BOOK LIST 46"]

    assert outline.cited_pages(lines) == [27, 28, 30, 31, 46]


def test_a_year_in_the_contents_is_not_a_page_number():
    assert outline.cited_pages(["CONTENTS", "Fall Issue, 1971 Volume 1, Number 2"]) == []


def test_a_page_range_cites_both_ends():
    assert outline.cited_pages(["CONTENTS", "PICTURES OF SUMMER FIELD TRIP 36-37"]) \
        == [36, 37]


def test_pages_the_scan_does_not_contain_are_reported():
    """Vol 1 No 2's contents cites pages 27 and 28, but every folio printed in
    the issue follows printed = sheet + 26, so 28 and 29 are in no scan at all.
    Two pages were missed at the scanner, and two articles went with them."""
    missing = outline.missing_pages(cited=[27, 28, 30, 31, 46],
                                    folios={4: 30, 5: 31, 6: 32},
                                    sheet_count=20, first_body_sheet=3)

    assert missing == [27, 28]


def test_nothing_is_reported_when_the_scan_is_complete():
    missing = outline.missing_pages(cited=[3, 4, 7], folios={4: 4, 6: 6},
                                    sheet_count=22, first_body_sheet=3)

    assert missing == []


def test_a_misread_folio_does_not_silence_the_missing_page_check():
    """Real folios include OCR slips -- 40 read as 49, 45 as 47. Demanding that
    every folio agree meant the check gave up exactly where it was needed."""
    folios = {4: 30, 5: 31, 6: 32, 7: 33, 14: 49, 19: 47}   # two misreads

    missing = outline.missing_pages(cited=[27, 28, 30, 31], folios=folios,
                                    sheet_count=20, first_body_sheet=3)

    assert missing == [27, 28]


def test_folios_too_scattered_to_agree_report_nothing():
    """If no offset commands a majority, the scan is not understood well enough
    to accuse it of missing pages."""
    missing = outline.missing_pages(cited=[27, 28], folios={4: 30, 6: 40},
                                    sheet_count=20, first_body_sheet=3)

    assert missing == []
