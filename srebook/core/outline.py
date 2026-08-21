"""Drafting the bookmark outline from the issue's own printed contents page.

Phase 0 established that dot leaders cannot be parsed: Tesseract reads rows of
periods as random letters and swallows the trailing page number with them. The
titles in front of the leaders survive intact, and article titles are reprinted
in the body where the article starts -- so titles are *located*, never derived
from a printed page number.

Everything here is a head start for the operator, not a source of truth.
"""
from __future__ import annotations

import re
from collections import Counter

CONTENTS_HEADING = re.compile(r"^\W*CONTENTS\W*$", re.IGNORECASE)
# Some issues print the marker inside a header line: "Spring Issue, 1972
# CONTENTS Volume 1, Number 4". Requiring a line of its own missed those, and
# the cover's masthead became the outline instead.
CONTENTS_INLINE = re.compile(r"\bCONTENTS\b", re.IGNORECASE)
# A header line is short. "we catalogued the contents of the collection" is not.
MAX_CONTENTS_HEADER_WORDS = 9
LEADER = re.compile(r"[.…]{2,}|[.\s]{4,}")
MIN_TITLE_LETTERS = 5
MIN_UPPERCASE_RATIO = 0.85
# Below this many characters a "title" matches too much running prose to trust.
MIN_MATCH_LETTERS = 6
# The contents page is never deep into an issue.
FRONT_MATTER_SHEETS = 4

# Words a Title Case title may legitimately leave lowercase.
SMALL_WORDS = {"a", "an", "the", "of", "on", "at", "in", "to", "for", "and",
               "or", "as", "by", "from", "with", "into", "over", "up"}
# A lowercase word this long is prose, not a title's connective tissue.
PROSE_WORD_LETTERS = 4
MAX_TITLE_WORDS = 12
# Fewer words than this is a fragment, not a shortened heading.
MIN_SHORTENED_HEADING_WORDS = 3


def _contents_line(lines: list[str]) -> int | None:
    """Index of the line announcing the contents list, or None."""
    for i, line in enumerate(lines):
        text = line.strip()
        if CONTENTS_HEADING.match(text):
            return i
        if (CONTENTS_INLINE.search(text)
                and len(text.split()) <= MAX_CONTENTS_HEADER_WORDS
                and _looks_like_a_header(text)):
            return i
    return None


def _looks_like_a_header(text: str) -> bool:
    """A masthead line, not a sentence.

    "Spring Issue, 1972 CONTENTS Volume 1, Number 4" is a header. "we
    catalogued the contents of the collection" merely uses the word.
    """
    for word in text.split():
        letters = "".join(c for c in word if c.isalpha())
        if len(letters) >= 3 and not letters[0].isupper():
            return False
    return True


def _normalize(text: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", text.upper())


def _is_leader_noise(token: str) -> bool:
    """A trailing token that is debris from the dot leader rather than title.

    A year belongs to the title ("EASTERN IDAHO HISTORY FAIR - 1971"); a stray
    page number or misread run of periods ("99939)", "0", "2", "Ao") does not.
    """
    digits = "".join(c for c in token if c.isdigit())
    if len(digits) == 4 and 1500 <= int(digits) <= 2100:
        return False
    return len([c for c in token if c.isalpha()]) <= 2


def candidate_titles(lines: list[str]) -> list[str]:
    """Article titles from the OCR of the contents page.

    A title is a line that is overwhelmingly uppercase once its dot leader is
    removed. Capitalisation is tested on the RAW line: stripping lowercase first
    would reduce an author credit like "by Harold S. Forbush" to "H S F", which
    then looks exactly like a title.
    """
    marker = _contents_line(lines)
    start = 0 if marker is None else marker + 1

    titles: list[str] = []
    pending: str | None = None   # a title whose line ended mid-phrase

    for raw in lines[start:]:
        title = _title_from_line(raw)
        if title is None:
            # A description or author credit ends any continuation.
            if pending and pending not in titles:
                titles.append(pending)
            pending = None
            continue

        if pending:
            # The previous line ended in a colon, so this one completes it:
            # "THE COLLECTION OF HISTORICAL DOCUMENTS:" / "A CITIZENS
            # RESPONSIBILITY" is one article, not two.
            title = f"{pending} {title}"
            pending = None

        if title.rstrip().endswith(":"):
            pending = title
            continue
        if title not in titles:
            titles.append(title)

    if pending and pending not in titles:
        titles.append(pending)
    return titles


def _title_from_line(raw: str) -> str | None:
    """The article title on this contents line, or None if it is not one."""
    head = LEADER.split(raw.strip())[0].strip()

    # Strip trailing debris BEFORE judging capitalisation. A page number or a
    # misread run of leader dots drags the ratio down and loses a real title:
    # "POETRY a i 83, 44, 45" was discarded entirely.
    words = head.split()
    while len(words) > 1 and _is_leader_noise(words[-1]):
        words.pop()
    if words and _is_leader_noise(words[-1]) and len(words) == 1:
        return None

    title = re.sub(r"\s+", " ", " ".join(words)).strip(" .,-")
    letters = [c for c in title if c.isalpha()]
    if len(letters) < MIN_TITLE_LETTERS:
        return None
    if sum(c.isupper() for c in letters) / len(letters) < MIN_UPPERCASE_RATIO:
        return None
    if title.upper().strip(" .:") == "CONTENTS":
        return None
    return title


def loose_titles(lines: list[str]) -> list[str]:
    """Title Case contents entries, for issues that do not set theirs in caps.

    Vol 1 No 3 lists "A Critical Look at Historical Editing" where Vol 1 No 1
    would have shouted it. Capitalisation alone cannot separate those from the
    description lines beneath them, so these are only *candidates*: the caller
    keeps the ones the body confirms and discards the rest. That is why an
    unconfirmed loose title is dropped rather than parked -- most of them are
    "Volume 1, Number 3", not articles.
    """
    marker = _contents_line(lines)
    start = 0 if marker is None else marker + 1

    titles: list[str] = []
    for raw in lines[start:]:
        title = _loose_title_from_line(raw)
        if title and title not in titles:
            titles.append(title)
    return titles


def _loose_title_from_line(raw: str) -> str | None:
    head = LEADER.split(raw.strip())[0].strip()
    words = head.split()
    while len(words) > 1 and _is_leader_noise(words[-1]):
        words.pop()
    title = re.sub(r"\s+", " ", " ".join(words)).strip(" .,-‘’")

    letters = [c for c in title if c.isalpha()]
    if len(letters) < MIN_TITLE_LETTERS:
        return None
    # Already handled by the strict pass; do not offer it twice.
    if sum(c.isupper() for c in letters) / len(letters) >= MIN_UPPERCASE_RATIO:
        return None

    words = title.split()
    if not words or len(words) > MAX_TITLE_WORDS:
        return None
    for word in words:
        clean = "".join(c for c in word if c.isalpha())
        if not clean:
            continue
        if clean[0].isupper():
            continue
        if clean.lower() in SMALL_WORDS:
            continue
        # A lowercase word of real length means this is a sentence.
        if len(clean) >= PROSE_WORD_LETTERS:
            return None
    if not any(c.isalpha() for c in words[0]):
        return None
    return title


def detect_contents_sheet(sheets: dict[int, list[str]]) -> int | None:
    """The sheet carrying the printed contents list, or None if there is none."""
    for sheet in sorted(s for s in sheets if s <= FRONT_MATTER_SHEETS):
        if _contents_line(sheets[sheet]) is not None:
            return sheet
    return None


def find_contents_sheet(sheets: dict[int, list[str]]) -> int:
    """Where to start searching the body for titles.

    Titles must be located in the *body*; searching from sheet 1 would match
    each title against its own entry on the contents page. Falls back to the
    first sheet, so callers that need to know whether a contents page really
    exists should use detect_contents_sheet.
    """
    detected = detect_contents_sheet(sheets)
    if detected is not None:
        return detected
    return min(sheets) if sheets else 1


def _looks_like_a_heading(line: str) -> bool:
    letters = [c for c in line if c.isalpha()]
    if not letters:
        return False
    return sum(c.isupper() for c in letters) / len(letters) >= MIN_UPPERCASE_RATIO


def _matches_heading(want: str, line: str) -> bool:
    """Does `line` open the article titled `want`?

    A body heading may carry extra words ("ANDREW HENRY - FUR TRAPPER") or be
    shortened ("A BRIEF AUTOBIOGRAPHY"). But running prose also begins with the
    title -- "Andrew Henry was born in Fayette County" -- so a line materially
    longer than the title must additionally look like a heading, not a sentence.
    """
    got = _normalize(line)
    if not got:
        return False

    if got == want:
        return True
    if got.startswith(want):
        extra = len(got) - len(want)
        return extra <= 3 or _looks_like_a_heading(line)
    if len(got) >= MIN_MATCH_LETTERS and want.startswith(got):
        # A shortened heading is a real pattern ("A BRIEF AUTOBIOGRAPHY" for
        # "A BRIEF AUTOBIOGRAPHY AND ACCUMULATIVE HISTORY"), but a one- or
        # two-word fragment is not one: a stray "LIBRARY" on the page would
        # otherwise claim the article titled "Library Revi".
        words = [w for w in line.split() if any(c.isalnum() for c in w)]
        return len(words) >= MIN_SHORTENED_HEADING_WORDS and _looks_like_a_heading(line)
    return False


def locate_titles(titles: list[str], sheets: dict[int, list[str]]
                  ) -> list[tuple[str, int | None]]:
    """Find the sheet where each title's article begins.

    Returns the sheet or None. None is not a failure -- section labels like
    "IDAHO POETRY" are never printed in the body, and the operator supplies
    those from the grid.
    """
    located: list[tuple[str, int | None]] = []
    for title in titles:
        want = _normalize(title)
        if len(want) < MIN_MATCH_LETTERS:
            located.append((title, None))
            continue

        best: int | None = None
        for sheet in sorted(sheets):
            for line in sheets[sheet]:
                if _matches_heading(want, line):
                    best = sheet
                    break
            if best is not None:
                break
        located.append((title, best))
    return located


def title_case(text: str) -> str:
    """A printed heading is set in caps; a bookmark panel reads better without
    the shouting, and archivists expect title case.

    Minor words stay lower case unless they lead or follow a colon. Letters are
    capitalised at the start of a word or after a hyphen or slash, so
    "1971-SUMMER" becomes "1971-Summer" -- but never after an apostrophe, which
    would give "Pierre'S".
    """
    words = text.split()
    out = []
    start_of_phrase = True
    for word in words:
        letters = "".join(c for c in word if c.isalpha())
        if not letters:
            out.append(word)
            if word.endswith(":"):
                start_of_phrase = True
            continue

        lower = word.lower()
        if not start_of_phrase and letters.lower() in SMALL_WORDS:
            cased = lower
        else:
            cased = _capitalise_runs(lower)
        out.append(cased)
        start_of_phrase = word.endswith(":")
    return " ".join(out)


def _capitalise_runs(word: str) -> str:
    """Upper-case the first letter of each alphabetic run, apostrophes aside."""
    chars = list(word)
    fresh = True
    for i, ch in enumerate(chars):
        if ch.isalpha():
            if fresh:
                chars[i] = ch.upper()
            fresh = False
        elif ch in "'’":
            fresh = False          # Pierre's, not Pierre'S
        else:
            fresh = True
    return "".join(chars)


# Kept for internal callers that predate the public name.
_title_case = title_case


def locate_loose_titles(titles: list[str], sheets: dict[int, list[str]]
                        ) -> list[tuple[str, int]]:
    """Confirm Title Case candidates against the body, and take their wording
    from it.

    Only confirmed candidates are returned: an unconfirmed one is front-matter
    noise far more often than an article. The body heading supplies the text
    because contents lines are set small and OCR them badly -- "Library Revi
    a =" against a printed "LIBRARY HISTORY COLLECTIONS".
    """
    found: list[tuple[str, int]] = []
    for title in titles:
        want = _normalize(title)
        if len(want) < MIN_MATCH_LETTERS:
            continue
        for sheet in sorted(sheets):
            match = next((line for line in sheets[sheet]
                          if _matches_heading(want, line)), None)
            if match is None:
                continue
            display = _title_case(re.sub(r"\s+", " ", match).strip(" .,:;-"))
            if display and (display, sheet) not in found:
                found.append((display, sheet))
            break
    return found


HEADING_TOP_LINES = 3        # an article opens at the top of its page
RUNNING_HEAD_SHEETS = 3      # the same shout on this many pages is furniture
MAX_HEADING_WORDS = 8        # longer than this is a caption or a sentence
INDEX_ENTRY_COMMAS = 2       # "AHLSTROM, PETER, 61, 91" is an index line


def unclaimed_headings(sheets: dict[int, list[str]],
                       claimed: list[str]) -> list[tuple[str, int]]:
    """Printed headings in the body that the contents page never listed.

    A contents page says "IDAHO POETRY"; the poems underneath carry their own
    headings, and those are what a reader wants in the outline. The same is
    true of a book list headed "WESTERN HISTORY BOOKS".

    Only shouted lines near the top of a page qualify, a heading repeated
    across several pages is page furniture rather than an article, and anything
    already claimed by a contents entry is left alone.
    """
    already = {_normalize(t) for t in claimed}

    seen: dict[str, list[int]] = {}
    text_of: dict[str, str] = {}
    for sheet in sorted(sheets):
        for line in sheets[sheet][:HEADING_TOP_LINES]:
            stripped = line.strip()
            letters = [c for c in stripped if c.isalpha()]
            if len(letters) < MIN_TITLE_LETTERS:
                continue
            if sum(c.isupper() for c in letters) / len(letters) < MIN_UPPERCASE_RATIO:
                continue
            if not _could_be_a_heading(stripped):
                continue
            key = _normalize(stripped)
            if len(key) < MIN_MATCH_LETTERS:
                continue
            seen.setdefault(key, []).append(sheet)
            text_of.setdefault(key, stripped)

    found: list[tuple[str, int]] = []
    for key, on_sheets in seen.items():
        if len(on_sheets) >= RUNNING_HEAD_SHEETS:
            continue
        # The body may split a claimed title over two lines, so neither half
        # matches it from either end -- check containment both ways.
        if any(key in c or c in key for c in already):
            continue
        heading = text_of[key].strip(" .,:;-").split()
        # A stray letter the scanner found in the margin: "WESTERN HISTORY
        # BOOKS e". Never strip below two words, or a real one-word heading
        # would disappear.
        while len(heading) > 2 and len([c for c in heading[-1] if c.isalpha()]) <= 1:
            heading.pop()
        found.append((title_case(" ".join(heading)), min(on_sheets)))
    return sorted(found, key=lambda pair: pair[1])


def _could_be_a_heading(text: str) -> bool:
    """Reject the things that shout but are not article headings."""
    if len(text.split()) > MAX_HEADING_WORDS:
        return False
    if text.rstrip().endswith((".", ",", ";")):
        return False
    # An index entry: several commas and a page number or two.
    if text.count(",") >= INDEX_ENTRY_COMMAS and any(c.isdigit() for c in text):
        return False
    return True


MASTHEAD = re.compile(r"\b(volume|vol|number|no)\b\.?\s*\d+\s*$", re.IGNORECASE)
CITED_PAGE = re.compile(r"(\d{1,4})(?:\s*[-–]\s*(\d{1,4}))?\s*$")


def cited_pages(lines: list[str]) -> list[int]:
    """The page numbers the contents page quotes, in the order it quotes them.

    Only a number ending the line counts: that is where a contents entry puts
    it, after the leader. A four-digit year is a date, not a page.
    """
    marker = _contents_line(lines)
    start = 0 if marker is None else marker + 1

    pages: list[int] = []
    for raw in lines[start:]:
        text = raw.strip()
        if MASTHEAD.search(text):
            continue          # "Fall Issue, 1971 Volume 1, Number 2"
        m = CITED_PAGE.search(text)
        if not m:
            continue
        for group in m.groups():
            if group is None:
                continue
            page = int(group)
            if len(group) == 4 and 1500 <= page <= 2100:
                continue                      # a year
            if 1 <= page <= 2000:
                pages.append(page)
    return pages


def printed_folios(sheets: dict[int, list[str]]) -> dict[int, int]:
    """The page number printed on each sheet that shows one."""
    folios: dict[int, int] = {}
    for sheet, lines in sheets.items():
        for line in lines[:2]:
            text = line.strip()
            if text.isdigit() and 1 <= int(text) <= 2000:
                folios[sheet] = int(text)
                break
    return folios


def missing_pages(cited: list[int], folios: dict[int, int],
                  sheet_count: int, first_body_sheet: int) -> list[int]:
    """Pages the contents page cites that no body sheet in this scan carries.

    Vol 1 No 2 cites pages 27 and 28, yet every folio printed in it follows
    printed = sheet + 26, which puts those two on the cover and the contents
    page. They are not there: two pages were missed at the scanner, and two
    articles went with them. Silence about that leaves an archivist hunting for
    articles that were never scanned.
    """
    if not folios:
        return []
    # Real folios include OCR slips -- 40 read as 49, 45 as 47. Demanding that
    # every folio agree made the check give up exactly where it was needed, so
    # take the offset most of them support.
    tally = Counter(sheet - printed for sheet, printed in folios.items())
    offset, agreeing = tally.most_common(1)[0]
    if agreeing < 2 or agreeing <= len(folios) / 2:
        return []                    # no offset commands a majority

    return sorted({p for p in cited
                   if not first_body_sheet <= p + offset <= sheet_count})


def detect_body_start(sheets: dict[int, list[str]]) -> tuple[int, int] | None:
    """Infer (sheet, printed page number) from numbers printed on body sheets.

    Returns None unless the same sheet-to-page offset appears at least twice --
    one bare number on a page is coincidence, not a folio.
    """
    offsets: Counter[int] = Counter()
    seen: dict[int, int] = {}
    for sheet, lines in sheets.items():
        for line in lines[:2]:
            text = line.strip()
            if text.isdigit():
                printed = int(text)
                if 1 <= printed <= 2000:
                    offsets[sheet - printed] += 1
                    seen.setdefault(sheet - printed, sheet)
                break

    if not offsets:
        return None
    offset, count = offsets.most_common(1)[0]
    if count < 2:
        return None

    # Extrapolate back to printed page 1 rather than reporting the first sheet
    # that happens to print a number. Not every body page prints its folio, and
    # reporting the first numbered sheet would label the ones before it as front
    # matter -- roman i, ii, iii over what are really printed pages 1, 2, 3.
    sheet = offset + 1
    if sheet < 1:
        return 1, 1 - offset
    return sheet, 1
