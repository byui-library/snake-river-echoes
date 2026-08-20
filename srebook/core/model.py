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

    def to_dict(self) -> dict:
        d: dict = {"title": self.title, "sheet": self.sheet}
        if self.children:
            d["children"] = [c.to_dict() for c in self.children]
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Bookmark":
        return cls(
            title=d["title"],
            sheet=d["sheet"],
            children=[cls.from_dict(c) for c in d.get("children", [])],
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


# -------------------------------------------------------------- validation ----

def validate(issue: Issue, sheet_count: int) -> list[str]:
    """Problems that must be fixed before building, in plain English."""
    problems: list[str] = []

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
            if b.children and depth >= MAX_DEPTH:
                problems.append(
                    f'Bookmark "{b.title}" nests deeper than two levels, '
                    "which the outline does not support."
                )
            check(b.children, depth + 1)

    check(issue.bookmarks, 1)
    return problems
