"""Pages, words, outline and labels -> the finished PDF.

The page is sized from the scan at its true resolution, and the embedded JPEG is
stretched to fill it. That is what lets OCR read 300 DPI while the file carries
200 DPI, and it means changing the embed resolution never requires re-OCRing.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pikepdf

from .model import Bookmark, Issue, page_labels, validate
from .ocr import Word

OCR_DPI = 300
COURIER_ASCENT = 0.629   # em above the baseline, from the Courier metrics
COURIER_ADVANCE = 0.600  # Courier is fixed-pitch, so natural width is exact
MAX_HORIZONTAL_SCALE = 1000.0
EXPANDED_ENTRY_LIMIT = 40  # past this, collapse: scanning beats discoverability


class AssembleError(Exception):
    """The issue cannot be built as described, in terms a person can act on."""


@dataclass
class PageInput:
    embed_jpeg: bytes
    embed_size: tuple[int, int]
    ocr_size: tuple[int, int]
    words: list[Word] = field(default_factory=list)


def _escape(text: str) -> str:
    out = []
    for ch in text:
        # The font declares WinAnsiEncoding, so the round-trip is cp1252.
        ch = ch.encode("cp1252", "replace").decode("cp1252")
        out.append("\\" + ch if ch in "()\\" else ch)
    return "".join(out)


def _content_stream(page: PageInput, page_w: float, page_h: float) -> bytes:
    px_to_pt = 72.0 / OCR_DPI
    ops = [f"q {page_w:.4f} 0 0 {page_h:.4f} 0 0 cm /Im0 Do Q", "BT 3 Tr"]

    for w in page.words:
        width_pt = (w.x1 - w.x0) * px_to_pt
        if width_pt <= 0 or w.y1 <= w.y0 or not w.text:
            continue
        # Size from the measured ascent so glyph tops line up with the ink.
        size = (w.ascent * px_to_pt) / COURIER_ASCENT
        natural = COURIER_ADVANCE * size * len(w.text)
        if natural <= 0:
            continue
        scale = min(MAX_HORIZONTAL_SCALE, max(1.0, 100.0 * width_pt / natural))
        x = w.x0 * px_to_pt
        y = page_h - (w.baseline_y * px_to_pt)  # hOCR counts down from the top
        ops.append(
            f"/F1 {size:.3f} Tf {scale:.2f} Tz 1 0 0 1 {x:.3f} {y:.3f} Tm "
            f"({_escape(w.text)}) Tj"
        )

    ops.append("ET")
    # cp1252, NOT latin-1: latin-1 has no curly quotes or dashes, and encoding
    # there silently replaces every typographic apostrophe with '?'.
    return "\n".join(ops).encode("cp1252", "replace")


def _add_page(pdf: pikepdf.Pdf, page: PageInput) -> pikepdf.Object:
    ocr_w, ocr_h = page.ocr_size
    page_w = ocr_w / OCR_DPI * 72.0
    page_h = ocr_h / OCR_DPI * 72.0

    image = pikepdf.Stream(pdf, page.embed_jpeg)
    image.Type = pikepdf.Name.XObject
    image.Subtype = pikepdf.Name.Image
    image.Width, image.Height = page.embed_size
    image.ColorSpace = pikepdf.Name.DeviceGray
    image.BitsPerComponent = 8
    image.Filter = pikepdf.Name.DCTDecode  # raw JPEG passthrough

    font = pdf.make_indirect(pikepdf.Dictionary(
        Type=pikepdf.Name.Font, Subtype=pikepdf.Name.Type1,
        BaseFont=pikepdf.Name.Courier, Encoding=pikepdf.Name.WinAnsiEncoding,
    ))

    obj = pdf.make_indirect(pikepdf.Dictionary(
        Type=pikepdf.Name.Page,
        MediaBox=[0, 0, round(page_w, 4), round(page_h, 4)],
        Resources=pikepdf.Dictionary(
            XObject=pikepdf.Dictionary(Im0=image),
            Font=pikepdf.Dictionary(F1=font),
        ),
        Contents=pdf.make_stream(_content_stream(page, page_w, page_h)),
    ))
    pdf.pages.append(pikepdf.Page(obj))
    return obj


def _count_entries(bookmarks: list[Bookmark]) -> int:
    return sum(1 + _count_entries(b.children) for b in bookmarks)


def _add_outline(pdf: pikepdf.Pdf, issue: Issue, pages: list[pikepdf.Object]) -> None:
    if not issue.bookmarks:
        return

    expanded = _count_entries(issue.bookmarks) < EXPANDED_ENTRY_LIMIT

    def build(bookmarks: list[Bookmark], parent: pikepdf.Object) -> tuple:
        items = []
        for b in bookmarks:
            item = pdf.make_indirect(pikepdf.Dictionary(
                Title=pikepdf.String(b.title),
                Parent=parent,
                # Every node navigates. A grouping label that jumps nowhere is
                # the commonest defect in hand-made PDF outlines.
                Dest=pikepdf.Array([pages[b.sheet - 1], pikepdf.Name.Fit]),
            ))
            if b.children:
                first, last, count = build(b.children, item)
                item.First, item.Last = first, last
                item.Count = count if expanded else -count
            items.append(item)

        for i, item in enumerate(items):
            if i:
                item.Prev = items[i - 1]
            if i < len(items) - 1:
                item.Next = items[i + 1]
        # A parent's /Count includes descendants only when they are visible.
        total = sum(1 + (int(it.Count) if "/Count" in it.keys()
                         and int(it.Count) > 0 else 0) for it in items)
        return items[0], items[-1], total

    outlines = pdf.make_indirect(pikepdf.Dictionary(Type=pikepdf.Name.Outlines))
    first, last, count = build(issue.bookmarks, outlines)
    outlines.First, outlines.Last, outlines.Count = first, last, count
    pdf.Root.Outlines = outlines

    # Tell the viewer to open showing the outline. Without this a reader gets
    # whichever panel the viewer prefers -- usually page thumbnails -- and the
    # outline is present but invisible until they go looking for it.
    pdf.Root.PageMode = pikepdf.Name.UseOutlines


def _add_page_labels(pdf: pikepdf.Pdf, issue: Issue, sheet_count: int) -> None:
    """Ranges, not per-page entries: front matter roman, body decimal."""
    nums = pikepdf.Array()
    labels = page_labels(issue, sheet_count)
    if not labels:
        return

    body_index = max(issue.body_starts_at_sheet - 1, 0)
    if body_index > 0:
        nums.append(0)
        nums.append(pikepdf.Dictionary(S=pikepdf.Name.r))
    if body_index < sheet_count:
        nums.append(body_index)
        nums.append(pikepdf.Dictionary(
            S=pikepdf.Name.D, St=max(issue.body_starts_at_printed, 1)))

    pdf.Root.PageLabels = pdf.make_indirect(pikepdf.Dictionary(Nums=nums))


def _add_metadata(pdf: pikepdf.Pdf, issue: Issue) -> None:
    with pdf.open_metadata(set_pikepdf_as_editor=False) as meta:
        meta["dc:title"] = issue.display_title() or "Untitled"
        if issue.publisher:
            meta["dc:creator"] = [issue.publisher]
            meta["dc:publisher"] = [issue.publisher]
        keywords = [p for p in (issue.title, str(issue.year) if issue.year else "",
                                issue.publisher) if p]
        if keywords:
            meta["pdf:Keywords"] = "; ".join(keywords)


def build_pdf(issue: Issue, pages: list[PageInput], output: Path) -> Path:
    problems = validate(issue, sheet_count=len(pages))
    if problems:
        raise AssembleError(" ".join(problems))

    pdf = pikepdf.Pdf.new()
    page_objects = [_add_page(pdf, p) for p in pages]
    _add_outline(pdf, issue, page_objects)
    _add_page_labels(pdf, issue, len(pages))
    _add_metadata(pdf, issue)

    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    pdf.save(output, compress_streams=True)
    return output
