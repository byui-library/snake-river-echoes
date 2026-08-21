"""The issue data model, its sidecar file, and the rules that validate it.

The sidecar is the app's save-file and the record that makes a rebuild
reproducible. It is plain JSON so a person can hand-edit it.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

MAX_DEPTH = 2  # article, then optionally titled pieces within a department


@dataclass
class Bookmark:
    title: str
    sheet: int
    children: list["Bookmark"] = field(default_factory=list)
    # Set by the drafter when it could not locate this title in the body. The
    # sheet is a guess, and a person must confirm it. Recorded rather than
    # inferred from "sheet == 1", which mislabels a real Front Cover bookmark.
    needs_review: bool = False

    def to_dict(self) -> dict:
        d: dict = {"title": self.title, "sheet": self.sheet}
        if self.needs_review:
            d["needs_review"] = True
        if self.children:
            d["children"] = [c.to_dict() for c in self.children]
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Bookmark":
        return cls(
            title=d["title"],
            sheet=d["sheet"],
            children=[cls.from_dict(c) for c in d.get("children", [])],
            needs_review=d.get("needs_review", False),
        )


@dataclass
class Issue:
    title: str = ""
    volume: int | None = None
    issue: int | None = None
    year: int | None = None
    publisher: str = ""
    embed_dpi: int = 200
    body_starts_at_sheet: int = 1
    body_starts_at_printed: int = 1
    bookmarks: list[Bookmark] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "volume": self.volume,
            "issue": self.issue,
            "year": self.year,
            "publisher": self.publisher,
            "embed_dpi": self.embed_dpi,
            "page_labels": {
                "body_starts_at_sheet": self.body_starts_at_sheet,
                "body_starts_at_printed": self.body_starts_at_printed,
            },
            "bookmarks": [b.to_dict() for b in self.bookmarks],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Issue":
        labels = d.get("page_labels", {})
        return cls(
            title=d.get("title", ""),
            volume=d.get("volume"),
            issue=d.get("issue"),
            year=d.get("year"),
            publisher=d.get("publisher", ""),
            embed_dpi=d.get("embed_dpi", 200),
            body_starts_at_sheet=labels.get("body_starts_at_sheet", 1),
            body_starts_at_printed=labels.get("body_starts_at_printed", 1),
            bookmarks=[Bookmark.from_dict(b) for b in d.get("bookmarks", [])],
        )

    def display_title(self) -> str:
        """'Snake River Echoes, Vol. 1, No. 1 (1971)' from whatever parts exist."""
        parts = [self.title] if self.title else []
        vol_iss = []
        if self.volume is not None:
            vol_iss.append(f"Vol. {self.volume}")
        if self.issue is not None:
            vol_iss.append(f"No. {self.issue}")
        if vol_iss:
            parts.append(", ".join(vol_iss))
        text = ", ".join(parts)
        if self.year is not None:
            text = f"{text} ({self.year})" if text else str(self.year)
        return text


def save_sidecar(issue: Issue, path: Path) -> None:
    Path(path).write_text(
        json.dumps(issue.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
    )


def load_sidecar(path: Path) -> Issue:
    return Issue.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


# ------------------------------------------------------------- page labels ----

def _roman(n: int) -> str:
    numerals = [(1000, "m"), (900, "cm"), (500, "d"), (400, "cd"), (100, "c"),
                (90, "xc"), (50, "l"), (40, "xl"), (10, "x"), (9, "ix"),
                (5, "v"), (4, "iv"), (1, "i")]
    out = []
    for value, sym in numerals:
        while n >= value:
            out.append(sym)
            n -= value
    return "".join(out)


def page_labels(issue: Issue, sheet_count: int) -> list[str]:
    """The label each sheet carries, in sheet order.

    Front matter is lowercase roman; the body is decimal starting at the number
    the printer put on the page.
    """
    labels = []
    for sheet in range(1, sheet_count + 1):
        if sheet < issue.body_starts_at_sheet:
            labels.append(_roman(sheet))
        else:
            offset = sheet - issue.body_starts_at_sheet
            labels.append(str(issue.body_starts_at_printed + offset))
    return labels


def sheet_for_printed(issue: Issue, printed: int) -> int:
    """Which sheet carries a given printed page number."""
    return printed - issue.body_starts_at_printed + issue.body_starts_at_sheet


def printed_for_sheet(issue: Issue, sheet: int) -> int | None:
    """The printed page number on a sheet, or None if it is front matter."""
    if sheet < issue.body_starts_at_sheet:
        return None
    return issue.body_starts_at_printed + (sheet - issue.body_starts_at_sheet)


# -------------------------------------------------------------- validation ----

def _all_look_like_printed_pages(issue: Issue, sheet_count: int) -> bool:
    """Do the out-of-range bookmarks look like printed page numbers?

    An operator reads the numbers off the contents page and types them into a
    column headed Sheet. Every bookmark then points past the end, and saying so
    once per bookmark buries the one thing worth knowing.
    """
    if issue.body_starts_at_printed == issue.body_starts_at_sheet:
        return False        # the two numberings coincide; nothing to confuse

    def walk(bookmarks):
        for b in bookmarks:
            yield b
            yield from walk(b.children)

    marks = list(walk(issue.bookmarks))
    beyond = [b for b in marks if b.sheet > sheet_count]
    if len(beyond) < 2:
        return False
    return all(1 <= sheet_for_printed(issue, b.sheet) <= sheet_count for b in beyond)


def validate(issue: Issue, sheet_count: int) -> list[str]:
    """Problems that must be fixed before building, in plain English."""
    problems: list[str] = []

    if _all_look_like_printed_pages(issue, sheet_count):
        first = issue.body_starts_at_sheet
        return [
            f"These bookmarks look like printed page numbers rather than sheet "
            f"numbers. This issue has {sheet_count} sheets, carrying printed "
            f"pages {issue.body_starts_at_printed} to "
            f"{issue.body_starts_at_printed + sheet_count - first}. "
            f"Sheet {first} is printed page {issue.body_starts_at_printed}, so "
            f"printed page {issue.body_starts_at_printed} means sheet {first}. "
            "Use the Printed page column to enter them as they appear on the "
            "contents page."
        ]

    if not 1 <= issue.body_starts_at_sheet <= max(sheet_count, 1):
        problems.append(
            f"Printed page 1 is set to sheet {issue.body_starts_at_sheet}, "
            f"but this issue has {sheet_count} sheets."
        )

    def check(bookmarks: list[Bookmark], depth: int) -> None:
        for b in bookmarks:
            if not b.title.strip():
                problems.append(f"A bookmark on sheet {b.sheet} has no title.")
            if not 1 <= b.sheet <= sheet_count:
                problems.append(
                    f'Bookmark "{b.title}" points at sheet {b.sheet}, '
                    f"but this issue has {sheet_count} sheets."
                )
            if b.needs_review:
                problems.append(
                    f'Bookmark "{b.title}" was not found in the body, so sheet '
                    f"{b.sheet} is only a guess. Confirm it if it is right, set "
                    "the sheet it really starts on, or remove the bookmark."
                )
            if b.children and depth >= MAX_DEPTH:
                problems.append(
                    f'Bookmark "{b.title}" nests deeper than two levels, '
                    "which the outline does not support."
                )
            check(b.children, depth + 1)

    check(issue.bookmarks, 1)
    return problems
