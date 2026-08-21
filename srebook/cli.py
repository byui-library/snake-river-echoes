"""Command line front end. Also the harness the GUI will sit on top of.

Two steps, because the pause between them is where the operator's review lives:

    srebook draft "Image Files/SRE Vol 1 Number 1"
    srebook build "Image Files/SRE Vol 1 Number 1"
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .core import ocr, pipeline
from .core.model import Issue, load_sidecar


def _progress(done: int, total: int, label: str) -> None:
    if done < total:
        print(f"\r  OCR {done + 1}/{total}  {label[:40]:<40}", end="", flush=True)
    else:
        print(f"\r  OCR {total}/{total} complete{' ' * 34}")


def _describe_draft(issue: Issue, folder: Path) -> None:
    print(f"\nDrafted {pipeline.sidecar_path(folder).name}")
    if issue.year:
        print(f"  Issue        {issue.display_title() or '(untitled)'}")
    # State the mapping, not an assumption about it. A quarterly paginated
    # continuously across the volume starts at page 27, not page 1.
    print(f"  Page labels  sheet {issue.body_starts_at_sheet} is printed page "
          f"{issue.body_starts_at_printed}")
    print(f"  Bookmarks    {len(issue.bookmarks)}")
    for b in issue.bookmarks:
        print(f"      sheet {b.sheet:>3}  {b.title}")

    # Two different problems needing opposite advice: one wants a page number,
    # the other wants a yes or no.
    unplaced = [b.title for b in issue.bookmarks
                if b.needs_review and b.review_reason != "suggested"]
    if unplaced:
        print("\n  These could not be located in the body, so their sheet is a guess.")
        print("  Give them a page number before building:")
        for title in unplaced:
            print(f"      {title}")

    suggested = [(b.title, b.sheet) for b in issue.bookmarks
                 if b.needs_review and b.review_reason == "suggested"]
    if suggested:
        print("\n  These are printed in the issue but not listed on the contents")
        print("  page. Keep or remove each one before building:")
        for title, sheet in suggested:
            print(f"      sheet {sheet:>3}  {title}")

    print(f"\nReview {pipeline.sidecar_path(folder)}")
    print(f'then run:  srebook build "{folder}"')


def _cmd_draft(args) -> int:
    folder = Path(args.folder)
    issue = pipeline.draft(folder, embed_dpi=args.embed_dpi,
                           overwrite=args.force, progress=_progress)
    _describe_draft(issue, folder)
    return 0


def _cmd_build(args) -> int:
    folder = Path(args.folder)
    out = pipeline.build(folder, progress=_progress, force=args.force)
    issue = load_sidecar(pipeline.sidecar_path(folder))

    def count(bookmarks):
        return sum(1 + count(b.children) for b in bookmarks)

    print(f"\nBuilt {out.name}")
    print(f"  {out}")
    print(f"  {out.stat().st_size / 1e6:.2f} MB, {count(issue.bookmarks)} bookmarks")
    return 0


def _cmd_pages(args) -> int:
    """Show the order the scans will be read in, and what each sheet will be
    labelled. Exists because an operator reported pages not arriving as their
    file names implied, and there was no way to see what order was chosen.
    """
    folder = Path(args.folder)
    sheets = pipeline._sheets(folder)

    labels = []
    side = pipeline.sidecar_path(folder)
    if side.exists():
        from .core.model import page_labels
        labels = page_labels(load_sidecar(side), len(sheets))

    print(f"\n{len(sheets)} scans in {folder.name}, in reading order:\n")
    print(f"  {'sheet':>5}  {'printed page':>12}  file")
    for i, path in enumerate(sheets, start=1):
        printed = labels[i - 1] if labels else "-"
        print(f"  {i:>5}  {printed:>12}  {path.name}")

    if not labels:
        print("\nNo draft yet, so printed page numbers are not known.")
    return 0


def _cmd_doctor(_args) -> int:
    """Report what this copy of the program can actually do.

    Exists so a clean-machine test can assert that the *bundled* Tesseract ran,
    not merely that OCR succeeded -- on a developer machine those look identical.
    """
    import sys

    frozen = bool(getattr(sys, "frozen", False))
    print("SRE Book Builder")
    print(f"  running     {'packaged' if frozen else 'from source'}")
    print(f"  python      {sys.version.split()[0]}")

    for label, module in (("Pillow", "PIL"), ("pikepdf", "pikepdf"), ("lxml", "lxml")):
        try:
            mod = __import__(module)
            version = getattr(mod, "__version__", "present")
        except ImportError:
            version = "MISSING"
        print(f"  {label:<11} {version}")

    binary = ocr.find_tesseract()
    source = ocr.tesseract_source()
    print(f"  tesseract   {source}")
    if binary is None:
        print(f"              expected at {ocr.bundled_tesseract()}")
        print("\nTesseract is not available, so this copy cannot read any scans.")
        return 1

    print(f"              {binary}")
    tessdata = Path(binary).parent / "tessdata"
    languages = (sorted(p.stem for p in tessdata.glob("*.traineddata"))
                 if tessdata.is_dir() else [])
    print(f"  languages   {', '.join(languages) if languages else 'none found'}")

    if not languages:
        print("\nNo language data found, so Tesseract cannot read anything.")
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="srebook",
        description="Turn a folder of TIFF page scans into a searchable, "
                    "bookmarked PDF.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    draft = sub.add_parser("draft", help="OCR an issue and propose an outline")
    draft.add_argument("folder", help="folder of TIFF page scans")
    draft.add_argument("--embed-dpi", type=int, default=200,
                       help="resolution of the images in the PDF (default 200)")
    draft.add_argument("--force", action="store_true",
                       help="re-draft, discarding an existing review")
    draft.set_defaults(func=_cmd_draft)

    build = sub.add_parser("build", help="build the PDF from a reviewed draft")
    build.add_argument("folder", help="folder of TIFF page scans")
    build.add_argument("--force", action="store_true",
                       help="build even though some bookmarks are unreviewed")
    build.set_defaults(func=_cmd_build)

    pages = sub.add_parser(
        "pages", help="show the reading order of the scans and their page numbers")
    pages.add_argument("folder", help="folder of TIFF page scans")
    pages.set_defaults(func=_cmd_pages)

    doctor = sub.add_parser(
        "doctor", help="check this installation can read scans and build PDFs")
    doctor.set_defaults(func=_cmd_doctor)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except pipeline.PipelineError as exc:
        # Errors are sentences, not tracebacks.
        print(f"\n{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
