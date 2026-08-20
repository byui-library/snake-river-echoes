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
LEADER = re.compile(r"[.…]{2,}|[.\s]{4,}")
MIN_TITLE_LETTERS = 5
MIN_UPPERCASE_RATIO = 0.85
# Below this many characters a "title" matches too much running prose to trust.
MIN_MATCH_LETTERS = 6
# The contents page is never deep into an issue.
FRONT_MATTER_SHEETS = 4


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
    start = 0
    for i, line in enumerate(lines):
        if CONTENTS_HEADING.match(line.strip()):
            start = i + 1
            break

    titles: list[str] = []
    for raw in lines[start:]:
        head = LEADER.split(raw.strip())[0].strip()
        letters = [c for c in head if c.isalpha()]
        if len(letters) < MIN_TITLE_LETTERS:
            continue
        if sum(c.isupper() for c in letters) / len(letters) < MIN_UPPERCASE_RATIO:
            continue

        # Trailing OCR noise from the leader: "A GOAL IS ACHIEVED ne", or
        # "WHO AND WHAT IN IDAHO. 99939) 0 2 Ao a".
        words = head.split()
        while len(words) > 2 and _is_leader_noise(words[-1]):
            words.pop()
        title = re.sub(r"\s+", " ", " ".join(words)).strip(" .,-")
        if not title or title.upper() == "CONTENTS":
            continue
        if len([c for c in title if c.isalpha()]) < MIN_TITLE_LETTERS:
            continue
        if title not in titles:
            titles.append(title)
    return titles


def find_contents_sheet(sheets: dict[int, list[str]]) -> int:
    """The sheet carrying the printed contents list.

    Titles must be located in the *body*; searching from sheet 1 would match
    each title against its own entry on the contents page.
    """
    for sheet in sorted(s for s in sheets if s <= FRONT_MATTER_SHEETS):
        for line in sheets[sheet]:
            if CONTENTS_HEADING.match(line.strip()):
                return sheet
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
        return _looks_like_a_heading(line)
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
