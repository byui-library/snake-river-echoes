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

from srebook.core import outline, pipeline
from srebook.core.model import Issue, page_labels


def issue_folders() -> list[Path]:
    found = []
    for d in sorted((REPO / "Image Files").rglob("*")):
        if not d.is_dir() or "output" in d.parts or ".cache" in d.parts:
            continue
        tifs = [p for p in d.iterdir()
                if p.is_file() and p.suffix.lower() in (".tif", ".tiff")
                and not p.name.startswith("._")]
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

    issue = Issue()
    anchor = outline.detect_body_start(body)
    if anchor:
        issue.body_starts_at_sheet, issue.body_starts_at_printed = anchor
    folios = outline.printed_folios(body)
    gaps = outline.detect_gaps(folios)
    issue.missing_pages = gaps
    labels = page_labels(issue, len(sheets))
    cited = outline.cited_pages(front)
    absent = outline.pages_not_in_scan(cited, labels)

    return {
        "folder": str(folder.relative_to(REPO / "Image Files")),
        "sheets": len(sheets),
        "body_sheets": len(body),
        "contents_sheet": contents_sheet,
        "anchor": list(anchor) if anchor else None,
        "folios_read": len(folios),
        "folios": {str(k): v for k, v in sorted(folios.items())},
        "gaps_from_folios": gaps,
        "cited_pages": cited,
        "cited_but_absent": absent,
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
