"""Survey every issue folder for pages missing from the scan.

Writes OCR cache into each folder's output/.cache. Writes NO sidecar, so no
saved review can be overwritten, and never touches the TIFFs.

Results are appended to survey.json after every folder, so the run can be
inspected while it works and resumed if it stops.
"""
import json
import sys
import time
import traceback
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "docs" / "scan-survey-data.json"
sys.path.insert(0, str(REPO))

from srebook.core import ingest, outline, pipeline
from srebook.core.model import Issue, page_labels


def issue_folders() -> list[Path]:
    found = []
    for d in sorted((REPO / "Image Files").rglob("*")):
        if not d.is_dir() or "output" in d.parts or ".cache" in d.parts:
            continue
        # ingest's rules, not a second copy: it also skips the AppleDouble
        # files a Mac leaves beside every scan.
        tifs = [p for p in d.iterdir()
                if p.is_file() and p.suffix.lower() in ingest.TIFF_SUFFIXES
                and not ingest.is_metadata_file(p)]
        if tifs:
            found.append(d)
    return found


def fully_cached(sheets: list[Path], folder: Path) -> bool:
    cache = pipeline.cache_dir(folder)
    return all((cache / f"{s.stem}.hocr").exists() for s in sheets)


def survey(folder: Path) -> dict:
    sheets = pipeline._sheets(folder)
    # Reading the text is the whole cost. Where every sheet is already cached
    # there is nothing to read, and re-running detection over the collection
    # takes seconds rather than an hour -- which is what makes it practical to
    # re-survey after changing how page numbers are recognised.
    if not fully_cached(sheets, folder):
        pipeline._ocr_sheets(sheets, folder, 200, None)
    text = pipeline._sheet_text(sheets, folder)

    contents_sheet = outline.find_contents_sheet(text)
    front: list[str] = []
    for s in range(1, contents_sheet + 1):
        front.extend(text.get(s, []))
    body = {s: l for s, l in text.items() if s > contents_sheet}

    # The same call draft makes, so the report can never describe a program
    # that no longer exists.
    scan = pipeline.assess_scan(front, body, len(sheets))

    issue = Issue(missing_pages=scan.gaps)
    if scan.anchor:
        issue.body_starts_at_sheet, issue.body_starts_at_printed = scan.anchor
    labels = page_labels(issue, len(sheets))

    return {
        "folder": str(folder.relative_to(REPO / "Image Files")),
        "sheets": len(sheets),
        "body_sheets": scan.body_sheets,
        "contents_sheet": contents_sheet,
        "anchor": list(scan.anchor) if scan.anchor else None,
        "folios_read": len(scan.folios),
        "numbering_readable": scan.numbering_readable,
        "folios": {str(k): v for k, v in sorted(scan.folios.items())},
        "gaps_from_folios": scan.gaps,
        "cited_pages": scan.cited,
        "cited_but_absent": scan.cited_but_absent,
        "first_label": labels[0] if labels else None,
        "last_label": labels[-1] if labels else None,
    }


def main() -> int:
    folders = issue_folders()
    results = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else []
    done = {r["folder"] for r in results}
    started = time.time()

    print(f"{len(folders)} issue folders; {len(done)} already surveyed", flush=True)
    for i, folder in enumerate(folders, start=1):
        name = str(folder.relative_to(REPO / "Image Files"))
        if name in done:
            continue
        began = time.time()
        try:
            record = survey(folder)
        except Exception as exc:
            record = {"folder": name, "error": f"{type(exc).__name__}: {exc}",
                      "traceback": traceback.format_exc()[-600:]}
        results.append(record)
        OUT.write_text(json.dumps(results, indent=1), encoding="utf-8")
        note = record.get("error") or (
            f"{record['sheets']:>3} sheets, {record['folios_read']:>3} folios, "
            f"gaps={record['gaps_from_folios']}, absent={record['cited_but_absent']}")
        print(f"[{i}/{len(folders)}] {time.time() - began:5.0f}s  {name}\n"
              f"          {note}", flush=True)

    print(f"\ndone in {(time.time() - started) / 60:.0f} min; "
          f"{len(results)} folders in {OUT}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
