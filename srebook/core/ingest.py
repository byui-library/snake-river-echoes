"""Folder of TIFFs -> ordered sheets, plus a guess at the issue's metadata.

A *sheet* is a 1-based physical position in scan order. It is not a printed page
number. See CLAUDE.md on vocabulary.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

TIFF_SUFFIXES = {".tif", ".tiff"}

# SRE_1971_Vol1_No1_01.tif
SRE_NAME = re.compile(
    r"(?P<year>\d{4})[_\- ]*vol[._\- ]*(?P<volume>\d+)[_\- ]*no[._\- ]*(?P<issue>\d+)",
    re.IGNORECASE,
)

MIN_YEAR, MAX_YEAR = 1800, 2100


class IngestError(Exception):
    """Something about the input folder is wrong, in terms a person can act on."""


@dataclass
class IssueMetadata:
    year: int | None = None
    volume: int | None = None
    issue: int | None = None


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
    ]
    return sorted(sheets, key=_natural_key)


def guess_metadata(sheets: list[Path]) -> IssueMetadata:
    """Best-effort read of year/volume/issue from the filenames.

    Deliberately conservative: other archives will not use this naming
    convention, and a wrong guess the operator has to notice and undo is worse
    than a blank field.
    """
    for path in sheets:
        m = SRE_NAME.search(path.stem)
        if not m:
            continue
        year = int(m.group("year"))
        if not MIN_YEAR <= year <= MAX_YEAR:
            continue
        return IssueMetadata(
            year=year,
            volume=int(m.group("volume")),
            issue=int(m.group("issue")),
        )
    return IssueMetadata()
