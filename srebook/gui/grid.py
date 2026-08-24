"""The bookmark grid's logic, flattened for display and rebuilt for saving.

Deliberately free of widgets and of tkinter, because this is where the operator
does the one job the machine cannot do and the rules deserve real tests.

The outline is two levels: an article, and optionally the separately-titled
pieces inside a printed department. The grid enforces that, so the widget layer
never has to.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..core.model import (Bookmark, Issue, label_for_sheet, page_labels,
                          printed_for_sheet,
                          save_sidecar, sheet_for_label, sheet_for_printed,
                          validate)

MAX_LEVEL = 1  # 0 = article, 1 = a piece within a department
UNPLACED_SHEET = "—"  # em dash: a guess, not an answer


@dataclass
class Row:
    title: str
    sheet: int
    level: int = 0
    needs_review: bool = False
    review_reason: str = ""


@dataclass
class OutlineGrid:
    issue: Issue
    sheet_count: int
    rows: list[Row] = field(default_factory=list)
    dirty: bool = False

    def __post_init__(self):
        if not self.rows:
            self.rows = self._flatten(self.issue.bookmarks)

    # ------------------------------------------------------- structure ----

    @staticmethod
    def _flatten(bookmarks: list[Bookmark], level: int = 0) -> list[Row]:
        rows = []
        for b in bookmarks:
            rows.append(Row(b.title, b.sheet, level, b.needs_review, b.review_reason))
            rows.extend(OutlineGrid._flatten(b.children, level + 1))
        return rows

    def to_bookmarks(self) -> list[Bookmark]:
        """Rebuild the nested outline. A child with no parent above it is
        promoted rather than dropped -- the grid must never hand the model a
        structure the model would reject."""
        top: list[Bookmark] = []
        for row in self.rows:
            node = Bookmark(row.title, row.sheet, needs_review=row.needs_review,
                            review_reason=row.review_reason)
            if row.level > 0 and top:
                top[-1].children.append(node)
            else:
                top.append(node)
        return top

    def _children_of(self, index: int) -> int:
        """How many rows immediately following `index` are its children."""
        if self.rows[index].level != 0:
            return 0
        count = 0
        for row in self.rows[index + 1:]:
            if row.level == 0:
                break
            count += 1
        return count

    # --------------------------------------------------------- editing ----

    def add(self, title: str = "", sheet: int = 1) -> int:
        # Sheet 1 by default: visible and obviously wrong beats hidden.
        self.rows.append(Row(title, sheet, 0))
        self.dirty = True
        return len(self.rows) - 1

    def remove(self, index: int) -> None:
        span = 1 + self._children_of(index)
        del self.rows[index:index + span]
        self.dirty = True

    def edit(self, index: int, title: str | None = None, sheet: int | None = None) -> None:
        if title is not None:
            self.rows[index].title = title
        if sheet is not None:
            self.rows[index].sheet = sheet
        # The operator has looked at it; that is what the flag was waiting for.
        self.rows[index].needs_review = False
        self.dirty = True

    def confirm(self, index: int) -> None:
        """Accept a parked row as it stands.

        The drafter parks a title it could not locate on sheet 1. For a Front
        Cover that is the right answer, so the operator needs a way to agree
        with it, not only a way to change it.
        """
        span = 1 + self._children_of(index)
        for row in self.rows[index:index + span]:
            row.needs_review = False
        self.dirty = True

    # --------------------------------------------------------- nesting ----

    def can_indent(self, index: int) -> bool:
        if index == 0 or self.rows[index].level >= MAX_LEVEL:
            return False
        # Indenting a parent would drag its children to a third level.
        return self._children_of(index) == 0

    def indent(self, index: int) -> None:
        if self.can_indent(index):
            self.rows[index].level += 1
            self.dirty = True

    def can_outdent(self, index: int) -> bool:
        return self.rows[index].level > 0

    def outdent(self, index: int) -> None:
        if self.can_outdent(index):
            self.rows[index].level -= 1
            self.dirty = True

    # ---------------------------------------------------------- moving ----

    def _block(self, index: int) -> tuple[int, int]:
        """A row and its children move as one."""
        if self.rows[index].level > 0:
            return index, 1
        return index, 1 + self._children_of(index)

    def can_move_up(self, index: int) -> bool:
        return index > 0

    def can_move_down(self, index: int) -> bool:
        start, span = self._block(index)
        return start + span < len(self.rows)

    def move_up(self, index: int) -> int:
        if not self.can_move_up(index):
            return index
        start, span = self._block(index)
        above_start = start - 1
        while above_start > 0 and self.rows[above_start].level > 0 \
                and self.rows[start].level == 0:
            above_start -= 1
        block = self.rows[start:start + span]
        del self.rows[start:start + span]
        self.rows[above_start:above_start] = block
        self.dirty = True
        return above_start

    def move_down(self, index: int) -> int:
        if not self.can_move_down(index):
            return index
        start, span = self._block(index)
        _, next_span = self._block(start + span)
        block = self.rows[start:start + span]
        del self.rows[start:start + span]
        insert_at = start + next_span
        self.rows[insert_at:insert_at] = block
        self.dirty = True
        return insert_at

    # ------------------------------------------------------ validation ----

    def problems(self) -> list[str]:
        issue = Issue(**{**self.issue.__dict__, "bookmarks": self.to_bookmarks()})
        return validate(issue, self.sheet_count)

    def needs_attention(self, index: int) -> bool:
        """A title the parser could not place. Valid, but unreviewed."""
        return self.rows[index].needs_review

    def sheet_display(self, index: int) -> str:
        """What to show in the Sheet column.

        An unplaced bookmark shows a dash rather than its placeholder sheet.
        Printing "1" makes a guess look like an answer, and reads as though the
        bookmark points at the cover or contents page.
        """
        row = self.rows[index]
        return UNPLACED_SHEET if self._sheet_is_a_guess(row) else str(row.sheet)

    @staticmethod
    def _sheet_is_a_guess(row: Row) -> bool:
        """A suggested heading was read off that very sheet, so its number is
        certain; only an unplaced title is parked somewhere arbitrary."""
        return row.needs_review and row.review_reason != "suggested"

    def printed_display(self, index: int) -> str:
        """The printed page number for a row, for the column beside the sheet."""
        row = self.rows[index]
        if self._sheet_is_a_guess(row):
            return UNPLACED_SHEET
        # Front matter carries a roman label, not nothing. Showing a dash there
        # left an operator unable to tell whether asking for roman had worked.
        return label_for_sheet(self.issue, row.sheet) or UNPLACED_SHEET

    def page_label_range(self) -> str:
        """How this issue's sheets are numbered, for an error message."""
        labels = page_labels(self.issue, self.sheet_count)
        if not labels:
            return "not at all"
        return f"{labels[0]} to {labels[-1]}"

    def set_printed_text(self, index: int, text: str) -> bool:
        """Place a row by the label printed on the page, roman or arabic."""
        sheet = sheet_for_label(self.issue, text, self.sheet_count)
        if sheet is None:
            return False
        self.edit(index, sheet=sheet)
        return True

    def set_printed(self, index: int, printed: int) -> bool:
        """Place a row by the number printed on the page.

        The contents page gives printed pages, so an operator naturally reads
        one off and types it in. Making her convert it to a sheet by hand is
        what put an entire issue's bookmarks past the end of the book.
        """
        sheet = sheet_for_printed(self.issue, printed)
        if not 1 <= sheet <= self.sheet_count:
            return False
        self.edit(index, sheet=sheet)
        return True

    # ---------------------------------------------------------- saving ----

    def save(self, path: Path) -> None:
        self.issue.bookmarks = self.to_bookmarks()
        save_sidecar(self.issue, path)
        self.dirty = False
