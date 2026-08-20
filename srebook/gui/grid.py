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

from ..core.model import Bookmark, Issue, save_sidecar, validate

MAX_LEVEL = 1  # 0 = article, 1 = a piece within a department


@dataclass
class Row:
    title: str
    sheet: int
    level: int = 0
    needs_review: bool = False


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
            rows.append(Row(b.title, b.sheet, level, b.needs_review))
            rows.extend(OutlineGrid._flatten(b.children, level + 1))
        return rows

    def to_bookmarks(self) -> list[Bookmark]:
        """Rebuild the nested outline. A child with no parent above it is
        promoted rather than dropped -- the grid must never hand the model a
        structure the model would reject."""
        top: list[Bookmark] = []
        for row in self.rows:
            node = Bookmark(row.title, row.sheet, needs_review=row.needs_review)
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

    # ---------------------------------------------------------- saving ----

    def save(self, path: Path) -> None:
        self.issue.bookmarks = self.to_bookmarks()
        save_sidecar(self.issue, path)
        self.dirty = False
