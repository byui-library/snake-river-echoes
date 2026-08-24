"""Folder of TIFFs -> ordered sheets, plus a guess at the issue's metadata.

A *sheet* is a 1-based physical position in scan order. It is not a printed page
number. See CLAUDE.md on vocabulary.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

TIFF_SUFFIXES = {".tif", ".tiff"}

# Volume and issue: "SRE_1971_Vol1_No1_01.tif", "SRE_Vol4_No1_01.TIF".
# The year is matched separately, because Volume 4's scans do not carry one and
# requiring it left volume and issue blank when both were in the name.
VOL_ISSUE = re.compile(
    r"vol(?:ume)?[._\- ]*(?P<volume>\d+)[._\- ]*no?(?:\.|[._\- ])*(?P<issue>\d+)",
    re.IGNORECASE,
)
YEAR = re.compile(r"(?<!\d)(?P<year>1[5-9]\d{2}|20\d{2})(?!\d)")

MIN_YEAR, MAX_YEAR = 1800, 2100


class IngestError(Exception):
    """Something about the input folder is wrong, in terms a person can act on."""


@dataclass
class IssueMetadata:
    year: int | None = None
    volume: int | None = None
    issue: int | None = None


def _is_metadata_file(path: Path) -> bool:
    """A companion file the operating system left behind, not a page scan.

    A Mac writing to a network share or a USB drive leaves an AppleDouble file,
    "._SRE_Vol4_No1_01.TIF", beside every real one. They hold resource-fork
    metadata, not an image. Counting them doubled the sheet count on scans from
    the archive's capture station and then failed to open the first one, which
    reads as a problem with the scans rather than with the folder.
    """
    return path.name.startswith("._") or path.name.startswith(".")


def _natural_key(path: Path):
    """Split digit runs out so _2 sorts before _10."""
    return [
        int(tok) if tok.isdigit() else tok.lower()
        for tok in re.split(r"(\d+)", path.name)
    ]


def find_sheets(folder: Path) -> list[Path]:
    """Every TIFF in `folder`, in scan order."""
    folder = Path(folder)
    if not folder.exists():
        raise IngestError(f"The folder {folder} does not exist.")
    if not folder.is_dir():
        raise IngestError(f"{folder} is a file, not a folder of page scans.")

    sheets = [
        p for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in TIFF_SUFFIXES
        and not _is_metadata_file(p)
    ]
    sheets = sorted(sheets, key=_natural_key)
    _refuse_multipage(sheets)
    return sheets


def _refuse_multipage(sheets: list[Path]) -> None:
    """A TIFF can hold many pages, and some scanners write a whole issue into
    one file. Every stage here treats a file as a sheet, so such a file would be
    read as its first page and the rest would vanish without a word.

    Refusing is not the ideal answer -- reading the pages out would be -- but
    losing pages quietly is the worst thing this program could do, and a person
    can split the file in a minute.
    """
    from PIL import Image, UnidentifiedImageError

    for path in sheets:
        try:
            with Image.open(path) as image:
                frames = getattr(image, "n_frames", 1)
        except (UnidentifiedImageError, OSError):
            continue  # a corrupt file is prepare's to report, with its name
        if frames > 1:
            raise IngestError(
                f"{path.name} holds {frames} pages in one file. This program "
                "needs one page per file, so that each scan is a sheet it can "
                "bookmark and label. Split the file and try again."
            )


def guess_metadata(sheets: list[Path]) -> IssueMetadata:
    """Best-effort read of year/volume/issue from the filenames.

    Deliberately conservative: other archives will not use this naming
    convention, and a wrong guess the operator has to notice and undo is worse
    than a blank field.
    """
    for path in sheets:
        stem = path.stem
        m = VOL_ISSUE.search(stem)
        if not m:
            continue

        # A year is welcome but not required, and it may sit either side of the
        # volume and issue.
        year = None
        for candidate in YEAR.finditer(stem):
            value = int(candidate.group("year"))
            if MIN_YEAR <= value <= MAX_YEAR:
                year = value
                break

        return IssueMetadata(year=year,
                             volume=int(m.group("volume")),
                             issue=int(m.group("issue")))
    return IssueMetadata()
