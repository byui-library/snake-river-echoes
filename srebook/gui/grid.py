"""The bookmark grid's logic, flattened for display and rebuilt for saving.

Deliberately free of widgets and of tkinter, because this is where the operator
does the one job the machine cannot do and the rules deserve real tests.

The outline is two levels: an article, and optionally the separately-titled
pieces inside a printed department. The grid enforces that, so the widget layer
never has to.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path

from ..core.model import (Bookmark, Issue, label_for_sheet, page_labels,
                          printed_for_sheet,
                          save_sidecar, sheet_for_label, sheet_for_printed,
                          validate)

MAX_LEVEL = 1  # 0 = article, 1 = a piece within a department
UNPLACED_SHEET = "—"  # em dash: a guess, not an answer
UNDO_DEPTH = 50       # deep enough for a review session, bounded for memory


@dataclass
class Row:
    title: str
    sheet: int
    level: int = 0
    needs_review: bool = False
    review_reason: str = ""
    missing_page: int | None = None


@dataclass
class OutlineGrid:
    issue: Issue
    sheet_count: int
    rows: list[Row] = field(default_factory=list)
    dirty: bool = False
    _history: list[list[Row]] = field(default_factory=list, repr=False)

    def __post_init__(self):
        if not self.rows:
            self.rows = self._flatten(self.issue.bookmarks)

    # ------------------------------------------------------- structure ----

    @staticmethod
    def _flatten(bookmarks: list[Bookmark], level: int = 0) -> list[Row]:
        rows = []
        for b in bookmarks:
            rows.append(Row(b.title, b.sheet, level, b.needs_review,
                            b.review_reason, b.missing_page))
            rows.extend(OutlineGrid._flatten(b.children, level + 1))
        return rows

    def to_bookmarks(self) -> list[Bookmark]:
        """Rebuild the nested outline. A child with no parent above it is
        promoted rather than dropped -- the grid must never hand the model a
        structure the model would reject."""
        top: list[Bookmark] = []
        for row in self.rows:
            node = Bookmark(row.title, row.sheet, needs_review=row.needs_review,
                            review_reason=row.review_reason,
                            missing_page=row.missing_page)
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

    # ------------------------------------------------------------ undo ----

    def _remember(self) -> None:
        """Keep the list as it stands, before an action changes it.

        Merge and Remove destroy what they touch -- both titles and a sheet in
        one case, a whole branch in the other -- so there is nothing to compute
        an inverse from. A copy taken beforehand covers every action alike.

        One snapshot per action: `set_printed` and `set_printed_text` delegate
        to `edit`, which is the only one of the three that records.
        """
        self._history.append([replace(row) for row in self.rows])
        del self._history[:-UNDO_DEPTH]

    def can_undo(self) -> bool:
        return bool(self._history)

    def undo(self) -> bool:
        """Step back one action. Returns False when there is nothing to undo."""
        if not self._history:
            return False
        self.rows = self._history.pop()
        self.dirty = True
        return True

    # --------------------------------------------------------- editing ----

    def add(self, title: str = "", sheet: int = 1) -> int:
        self._remember()
        # Sheet 1 by default: visible and obviously wrong beats hidden.
        self.rows.append(Row(title, sheet, 0))
        self.dirty = True
        return len(self.rows) - 1

    def remove(self, index: int) -> None:
        self._remember()
        span = 1 + self._children_of(index)
        del self.rows[index:index + span]
        self.dirty = True

    def edit(self, index: int, title: str | None = None, sheet: int | None = None) -> None:
        self._remember()
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
        self._remember()
        span = 1 + self._children_of(index)
        for row in self.rows[index:index + span]:
            row.needs_review = False
        self.dirty = True

    # ----------------------------------------------------------- merge ----

    def can_merge_up(self, index: int) -> bool:
        # A row with children would leave them with no parent.
        return index > 0 and self._children_of(index) == 0

    def merge_up(self, index: int) -> int:
        """Fold a row into the one above it, and return the survivor.

        Some issues split an article across two bookmarks: the title, then the
        byline underneath it. Others break a long heading in half. Both want
        the same repair, and the operator was reduced to retyping the title by
        hand to get it.

        The earlier row's sheet wins: that is where the article starts, while
        the second row may have been parked anywhere.
        """
        if not self.can_merge_up(index):
            return index
        self._remember()
        above = self.rows[index - 1]
        above.title = " ".join(f"{above.title} {self.rows[index].title}".split())
        above.needs_review = False      # it has just been looked at
        above.missing_page = None
        del self.rows[index]
        self.dirty = True
        return index - 1

    # --------------------------------------------------------- nesting ----

    def can_indent(self, index: int) -> bool:
        if index == 0 or self.rows[index].level >= MAX_LEVEL:
            return False
        # Indenting a parent would drag its children to a third level.
        return self._children_of(index) == 0

    def indent(self, index: int) -> None:
        if self.can_indent(index):
            self._remember()
            self.rows[index].level += 1
            self.dirty = True

    def can_outdent(self, index: int) -> bool:
        return self.rows[index].level > 0

    def outdent(self, index: int) -> None:
        if self.can_outdent(index):
            self._remember()
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
        self._remember()
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
        self._remember()
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
        # A page that was never scanned still knows which page it is. Showing
        # the number is the whole point of keeping the bookmark.
        if row.review_reason == "missing" and row.missing_page is not None:
            return str(row.missing_page)
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

    def set_page_labels(self, sheet_text: str, printed_text: str) -> bool:
        """Apply the operator's "sheet N is printed page P" setting.

        Returns True only when the mapping actually changed, so the widget
        layer knows whether to redraw. It is called on every keystroke, and
        redrawing regardless would fight the operator's cursor.

        A field mid-edit -- empty, or not yet a number -- leaves the mapping
        alone. She has to clear the box before typing a new number, and
        treating that intermediate state as a change blanks the column
        underneath her.
        """
        sheet_text, printed_text = sheet_text.strip(), printed_text.strip()
        if not (sheet_text.isdigit() and printed_text.isdigit()):
            return False
        sheet, printed = int(sheet_text), int(printed_text)
        # There is no printed page zero, and no sheet zero. An anchor past the
        # end of the issue would label every sheet roman.
        if sheet < 1 or printed < 1 or sheet > self.sheet_count:
            return False
        if (sheet, printed) == (self.issue.body_starts_at_sheet,
                                self.issue.body_starts_at_printed):
            return False
        self.issue.body_starts_at_sheet = sheet
        self.issue.body_starts_at_printed = printed
        self.dirty = True
        return True

    # ------------------------------------------------- stepping sheets ----

    def sheet_caption(self, sheet: int) -> str:
        """Which sheet is on screen, and what the book calls it.

        The outline lists articles, so a leaf carrying none -- a blank inside
        the cover, a full-page photograph -- appears nowhere in it. Walking the
        sheets is the only way to confirm a scan is whole.
        """
        label = label_for_sheet(self.issue, sheet)
        where = (f"printed page {label}" if sheet >= self.issue.body_starts_at_sheet
                 else f"front matter {label}")
        return f"Sheet {sheet} of {self.sheet_count} · {where}"

    def step_sheet(self, sheet: int, delta: int) -> int:
        """The next sheet in that direction, stopping at either end."""
        return max(1, min(sheet + delta, self.sheet_count))

    # ------------------------------------------ pages not in the scan ----

    def missing_pages_text(self) -> str:
        return ", ".join(str(p) for p in self.issue.missing_pages)

    def set_missing_pages(self, text: str) -> bool:
        """Set which printed pages the scan does not contain.

        Detection reads these from the folios, but it is reading OCR of a
        forty-year-old page, so the operator has the last word. Returns True
        only when the list actually changed, so the window is not redrawn on
        every keystroke.
        """
        text = text.strip()
        if text:
            parts = [p.strip() for p in text.split(",")]
            if not all(p.isdigit() and int(p) > 0 for p in parts):
                return False        # still typing, or not a page number
            pages = sorted({int(p) for p in parts})
        else:
            pages = []
        if pages == self.issue.missing_pages:
            return False
        self.issue.missing_pages = pages
        # A corrected gap has not been looked at yet.
        self.issue.gap_acknowledged = False
        self.dirty = True
        return True

    def acknowledge_gap(self) -> None:
        """Record that a person has seen the gap and accepts it."""
        self.issue.gap_acknowledged = True
        self.dirty = True

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
        # None means no sheet carries that page -- it was never scanned, or it
        # falls before this issue starts.
        if sheet is None or not 1 <= sheet <= self.sheet_count:
            return False
        self.edit(index, sheet=sheet)
        return True

    # ---------------------------------------------------------- saving ----

    def save(self, path: Path) -> None:
        self.issue.bookmarks = self.to_bookmarks()
        save_sidecar(self.issue, path)
        self.dirty = False
