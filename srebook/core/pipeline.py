"""The draft -> review -> build flow.

Drafting does the slow work (OCR) and proposes an outline. A person reviews it.
Building assembles the PDF from the reviewed sidecar, reusing the OCR cache, so
fixing a bookmark and rebuilding takes about a second.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Callable

from . import assemble, ingest, ocr, outline, prepare
from .model import Bookmark, Issue, load_sidecar, save_sidecar

Progress = Callable[[int, int, str], None]

OUTPUT_DIRNAME = "output"
CACHE_DIRNAME = ".cache"
FRONT_MATTER_SEARCH_SHEETS = 4  # the contents page is never deep into an issue
FRONT_COVER_TITLE = "Front Cover"
CONTENTS_TITLE = "Table of Contents"
# Contents entries that merely name the front matter we bookmark ourselves.
FRONT_MATTER_TITLES = {"COVER", "FRONTCOVER", "CONTENTS", "TABLEOFCONTENTS"}


def _normalise_title(title: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", title.upper())


class PipelineError(Exception):
    """The issue cannot be processed as asked, in terms a person can act on."""


# ------------------------------------------------------------------ paths ----

def output_dir(folder: Path) -> Path:
    return Path(folder) / OUTPUT_DIRNAME


def cache_dir(folder: Path) -> Path:
    return output_dir(folder) / CACHE_DIRNAME


def output_stem(sheets: list[Path], folder: Path) -> str:
    """Name outputs after the scans, so files stay recognisable on a drive.

    SRE_1971_Vol1_No1_01.tif ... -> SRE_1971_Vol1_No1
    """
    if sheets:
        stems = [p.stem for p in sheets]
        prefix = os.path.commonprefix(stems)
        prefix = re.sub(r"[\s_\-.]*\d*$", "", prefix)
        if len(prefix) >= 3:
            return prefix
    return re.sub(r"\s+", "_", Path(folder).name.strip())


def sidecar_path(folder: Path) -> Path:
    sheets = _sheets(folder)
    return output_dir(folder) / f"{output_stem(sheets, folder)}.srebook.json"


def pdf_path(folder: Path) -> Path:
    sheets = _sheets(folder)
    return output_dir(folder) / f"{output_stem(sheets, folder)}.pdf"


def _sheets(folder: Path) -> list[Path]:
    try:
        sheets = ingest.find_sheets(Path(folder))
    except ingest.IngestError as exc:
        raise PipelineError(str(exc)) from exc
    if not sheets:
        raise PipelineError(f"There are no page scans (.tif) in {folder}.")
    return sheets


# ------------------------------------------------------------------- OCR ----

def _ocr_sheets(sheets: list[Path], folder: Path, embed_dpi: int,
                progress: Progress | None) -> list[assemble.PageInput]:
    pages = []
    cache = cache_dir(folder)
    for i, path in enumerate(sheets, start=1):
        if progress:
            progress(i - 1, len(sheets), path.name)
        try:
            sheet = prepare.prepare_sheet(path, embed_dpi=embed_dpi)
        except prepare.PrepareError as exc:
            raise PipelineError(str(exc)) from exc

        try:
            hocr = ocr.run_tesseract(sheet.ocr_image, cache_dir=cache, key=path.stem)
            words = ocr.parse_hocr(hocr)
        except ocr.OcrError:
            # A page that will not OCR is included image-only. One bad sheet
            # must never abort an issue.
            words = []

        pages.append(assemble.PageInput(
            embed_jpeg=sheet.embed_jpeg, embed_size=sheet.embed_size,
            ocr_size=sheet.ocr_image.size, words=words,
        ))
    if progress:
        progress(len(sheets), len(sheets), "done")
    return pages


def _sheet_text(sheets: list[Path], folder: Path) -> dict[int, list[str]]:
    cache = cache_dir(folder)
    text = {}
    for i, path in enumerate(sheets, start=1):
        cached = cache / f"{path.stem}.hocr"
        if cached.exists():
            text[i] = ocr.text_lines(cached.read_bytes())
    return text


# ----------------------------------------------------------------- draft ----

def draft(folder: Path, embed_dpi: int = 200, overwrite: bool = False,
          progress: Progress | None = None) -> Issue:
    """OCR the issue and propose metadata, page labels and an outline.

    An existing sidecar wins unless `overwrite`: re-drafting after a review must
    never throw the review away.
    """
    folder = Path(folder)
    sheets = _sheets(folder)
    existing = sidecar_path(folder)
    if existing.exists() and not overwrite:
        return load_sidecar(existing)

    _ocr_sheets(sheets, folder, embed_dpi, progress)
    text = _sheet_text(sheets, folder)

    meta = ingest.guess_metadata(sheets)
    issue = Issue(volume=meta.volume, issue=meta.issue, year=meta.year,
                  embed_dpi=embed_dpi)

    contents_sheet = outline.find_contents_sheet(text)
    detected_contents = outline.detect_contents_sheet(text)
    # Candidates come from the front matter only. Reading further would pick up
    # article headings as titles in their own right, so an article whose heading
    # is punctuated differently from its contents entry ("A GOAL IS ACHIEVED"
    # against "A GOAL IS ACHIEVED!") would earn a second, duplicate bookmark.
    front_matter: list[str] = []
    for sheet in range(1, contents_sheet + 1):
        front_matter.extend(text.get(sheet, []))

    # Search for titles strictly after the contents page, or each title matches
    # its own entry there instead of the article it names.
    body = {s: lines for s, lines in text.items() if s > contents_sheet}
    if detected := outline.detect_body_start(body):
        issue.body_starts_at_sheet, issue.body_starts_at_printed = detected

    titles = outline.candidate_titles(front_matter)
    placed = {t for t, sheet in outline.locate_titles(titles, body) if sheet}

    # Some issues set their contents in Title Case rather than caps, and then
    # capitalisation cannot separate a title from the description beneath it.
    # Those candidates are only trustworthy once the body confirms them, so an
    # unconfirmed one is dropped rather than parked -- most are front-matter
    # noise like "Volume 1, Number 3".
    for title, sheet in outline.locate_loose_titles(
            outline.loose_titles(front_matter), body):
        if title not in placed and title not in titles:
            titles.append(title)

    # The front matter is known, not guessed: sheet 1 is the cover, and the
    # contents sheet was found in order to search past it. Leaving these for
    # the operator to place by hand was needless work.
    if detected_contents is not None and detected_contents > 1:
        issue.bookmarks.append(Bookmark(FRONT_COVER_TITLE, 1))
    if detected_contents is not None:
        issue.bookmarks.append(Bookmark(CONTENTS_TITLE, detected_contents))

    for title, sheet in outline.locate_titles(titles, body):
        if _normalise_title(title) in FRONT_MATTER_TITLES:
            # Several issues list COVER on the contents page, describing the
            # artwork. That is the bookmark we have already made.
            continue
        # An unlocated title is parked on sheet 1 rather than dropped -- the
        # operator needs to see it in the grid to place it -- and flagged, so
        # nothing downstream has to guess which sheet-1 entries are unplaced.
        # Cased here and only here, so an operator's own wording is never
        # rewritten behind their back on a later draft.
        issue.bookmarks.append(
            Bookmark(outline.title_case(title), sheet if sheet else 1,
                     needs_review=sheet is None,
                     review_reason="unplaced" if sheet is None else ""))

    # Headings printed in the body that the contents page never listed: the
    # individual poems under a "POETRY" category, a book list headed something
    # else entirely. Flagged, because these come from the parser's own reading
    # rather than from the issue's own table of contents.
    for title, sheet in outline.unclaimed_headings(
            body, [b.title for b in issue.bookmarks]):
        issue.bookmarks.append(
            Bookmark(title, sheet, needs_review=True, review_reason="suggested"))

    issue.bookmarks.sort(key=lambda b: b.sheet)

    output_dir(folder).mkdir(parents=True, exist_ok=True)
    save_sidecar(issue, existing)
    return issue


def _clear_review_flags(bookmarks) -> None:
    for b in bookmarks:
        b.needs_review = False
        _clear_review_flags(b.children)


# ----------------------------------------------------------------- build ----

def build(folder: Path, progress: Progress | None = None,
          force: bool = False) -> Path:
    """Assemble the reviewed issue into its PDF.

    Refuses while any bookmark is still flagged unreviewed: those are parked on
    a guessed sheet, and publishing them gives a reader a bookmark that goes to
    the wrong page with nothing to indicate it. `force` is for unattended use
    and has to be asked for.
    """
    folder = Path(folder)
    sheets = _sheets(folder)
    side = sidecar_path(folder)
    if not side.exists():
        raise PipelineError(
            f"No draft has been made for {folder.name} yet. Run draft first."
        )

    issue = load_sidecar(side)
    if force:
        _clear_review_flags(issue.bookmarks)
    pages = _ocr_sheets(sheets, folder, issue.embed_dpi, progress)

    try:
        return assemble.build_pdf(issue, pages, pdf_path(folder))
    except assemble.AssembleError as exc:
        raise PipelineError(str(exc)) from exc
