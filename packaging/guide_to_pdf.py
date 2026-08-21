"""Render the operator guide to a printable PDF.

    py packaging/guide_to_pdf.py

Handles the Markdown this guide actually uses -- headings, paragraphs, bullets,
block quotes, tables, rules, and inline bold/italic/code/links -- rather than
pretending to be a general converter. If the guide grows a construct this does
not know, it will come through as plain text, which is a visible failure rather
than a silent one.
"""
from __future__ import annotations

import html
import re
import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (HRFlowable, Image as PdfImage, KeepTogether,
                                Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "docs" / "operator-guide.md"
TARGET = ROOT / "docs" / "operator-guide.pdf"

INK = colors.HexColor("#1a1a1a")
MUTED = colors.HexColor("#5a5a5a")
RULE = colors.HexColor("#c8c8c8")
ACCENT = colors.HexColor("#8a3324")      # the journal's cover ink, near enough
PANEL = colors.HexColor("#f2f0ec")
MAX_FIGURE_HEIGHT = 355          # points; keeps a figure with its heading


def styles() -> dict:
    base = getSampleStyleSheet()
    body = ParagraphStyle(
        "Body", parent=base["BodyText"], fontName="Helvetica", fontSize=9.6,
        leading=14.2, textColor=INK, spaceAfter=7, alignment=TA_LEFT,
    )
    return {
        "body": body,
        "title": ParagraphStyle("Title", parent=body, fontName="Helvetica-Bold",
                                fontSize=20, leading=24, spaceAfter=4,
                                textColor=INK),
        "lede": ParagraphStyle("Lede", parent=body, fontSize=10.5, leading=15,
                               textColor=MUTED, spaceAfter=16),
        "h2": ParagraphStyle("H2", parent=body, fontName="Helvetica-Bold",
                             fontSize=13.5, leading=17, spaceBefore=17,
                             spaceAfter=7, textColor=ACCENT),
        "h3": ParagraphStyle("H3", parent=body, fontName="Helvetica-Bold",
                             fontSize=10.8, leading=14, spaceBefore=11,
                             spaceAfter=4, textColor=INK),
        "caption": ParagraphStyle("Caption", parent=body, fontSize=8.4,
                                  leading=11, textColor=MUTED, spaceAfter=0),
        "bullet": ParagraphStyle("Bullet", parent=body, leftIndent=16,
                                 bulletIndent=4, spaceAfter=3),
        "quote": ParagraphStyle("Quote", parent=body, leftIndent=10,
                                rightIndent=6, spaceBefore=3, spaceAfter=3,
                                textColor=INK),
        "cell": ParagraphStyle("Cell", parent=body, fontSize=9, leading=12.4,
                               spaceAfter=0),
        "cellhead": ParagraphStyle("CellHead", parent=body, fontSize=9,
                                   leading=12.4, spaceAfter=0,
                                   fontName="Helvetica-Bold"),
    }


# Helvetica is WinAnsi-encoded; anything outside it draws as a black box.
# Substitute rather than silently ship squares.
UNSUPPORTED = {"⟨": "[", "⟩": "]", "→": "->", "≤": "<=",
               "≥": ">=", "×": "x"}

IMAGE = re.compile(r"^!\[([^\]]*)\]\(([^)]+)\)$")
LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
BOLD = re.compile(r"\*\*(.+?)\*\*")
ITALIC = re.compile(r"(?<!\*)\*([^*]+)\*(?!\*)")
CODE = re.compile(r"`([^`]+)`")


def inline(text: str) -> str:
    """Markdown inline markup -> reportlab's mini-HTML."""
    for unavailable, substitute in UNSUPPORTED.items():
        text = text.replace(unavailable, substitute)
    text = LINK.sub(r"\1", text)                     # links print as their text
    text = html.escape(text, quote=False)
    text = CODE.sub(r'<font face="Courier" size="8.8">\1</font>', text)
    text = BOLD.sub(r"<b>\1</b>", text)
    text = ITALIC.sub(r"<i>\1</i>", text)
    return text


def split_row(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def build_table(rows: list[list[str]], st: dict, width: float) -> Table:
    head, *body = rows
    data = [[Paragraph(inline(c), st["cellhead"]) for c in head]]
    data += [[Paragraph(inline(c), st["cell"]) for c in r] for r in body]

    # First column carries the condition; give it room, share the rest.
    columns = len(head)
    if columns == 2:
        widths = [width * 0.42, width * 0.58]
    else:
        widths = [width / columns] * columns

    table = Table(data, colWidths=widths, hAlign="LEFT", repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PANEL),
        ("LINEBELOW", (0, 0), (-1, 0), 0.7, RULE),
        ("LINEBELOW", (0, 1), (-1, -2), 0.3, colors.HexColor("#e4e2de")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("BOX", (0, 0), (-1, -1), 0.7, RULE),
    ]))
    return table


def quote_panel(lines: list[str], st: dict, width: float) -> Table:
    paragraphs, current = [], []
    for line in lines:
        if line.strip():
            current.append(line.strip())
        elif current:
            paragraphs.append(" ".join(current))
            current = []
    if current:
        paragraphs.append(" ".join(current))
    inner = [Paragraph(inline(t), st["quote"]) for t in paragraphs]
    panel = Table([[inner]], colWidths=[width], hAlign="LEFT")
    panel.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PANEL),
        ("LINEBEFORE", (0, 0), (0, -1), 2.5, ACCENT),
        ("LEFTPADDING", (0, 0), (-1, -1), 11),
        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    return panel


def _next_content(lines: list[str], start: int) -> str | None:
    for line in lines[start:]:
        if line.strip():
            return line.strip()
    return None


def _figure(source: str, caption: str, st: dict, width: float,
            bare: bool = False) -> list:
    """A screenshot, sized to the text column and kept with its caption."""
    from PIL import Image as PilImage

    path = (ROOT / "docs" / source).resolve()
    if not path.exists():
        return [Paragraph(f"[missing image: {source}]", st["body"])]

    with PilImage.open(path) as probe:
        pixel_width, pixel_height = probe.size
    draw_width = min(width, pixel_width * 0.62)      # screenshots are 96 DPI-ish
    draw_height = draw_width * pixel_height / pixel_width
    # Cap the height so a tall screenshot still follows its heading on the same
    # page, instead of pushing the whole group over and leaving half a page white.
    if draw_height > MAX_FIGURE_HEIGHT:
        draw_width *= MAX_FIGURE_HEIGHT / draw_height
        draw_height = MAX_FIGURE_HEIGHT

    parts = [Spacer(1, 4), PdfImage(str(path), draw_width, draw_height,
                                    hAlign="LEFT")]
    if caption:
        parts.append(Spacer(1, 3))
        parts.append(Paragraph(caption, st["caption"]))
    parts.append(Spacer(1, 9))
    return parts if bare else [KeepTogether(parts)]


def convert(markdown: str, st: dict, width: float) -> list:
    story: list = []
    lines = markdown.splitlines()
    i = 0
    seen_title = False

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        if stripped.startswith("# "):
            story.append(Paragraph(inline(stripped[2:]), st["title"]))
            seen_title = True
            i += 1
            continue

        for marker, style in (("## ", "h2"), ("### ", "h3")):
            if stripped.startswith(marker):
                heading = Paragraph(inline(stripped[len(marker):]), st[style])
                following = _next_content(lines, i + 1)
                image = IMAGE.match(following) if following else None
                if image:
                    story.append(KeepTogether(
                        [heading] + _figure(image.group(2), image.group(1),
                                            st, width, bare=True)))
                    i = lines.index(following, i + 1) + 1
                else:
                    story.append(heading)
                    i += 1
                break
        else:
            pass
        if stripped.startswith("## ") or stripped.startswith("### "):
            continue

        if set(stripped) <= {"-"} and len(stripped) >= 3:
            story.append(Spacer(1, 5))
            story.append(HRFlowable(width="100%", thickness=0.7, color=RULE,
                                    spaceBefore=0, spaceAfter=9))
            i += 1
            continue

        image = IMAGE.match(stripped)
        if image:
            story.extend(_figure(image.group(2), image.group(1), st, width))
            i += 1
            continue

        if stripped.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = split_row(lines[i])
                if not all(set(c) <= {"-", ":", " "} and c for c in cells):
                    rows.append(cells)
                i += 1
            if rows:
                story.append(Spacer(1, 3))
                story.append(build_table(rows, st, width))
                story.append(Spacer(1, 10))
            continue

        if stripped.startswith(">"):
            quoted = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quoted.append(lines[i].strip().lstrip(">").strip())
                i += 1
            story.append(Spacer(1, 3))
            story.append(quote_panel(quoted, st, width))
            story.append(Spacer(1, 10))
            continue

        if re.match(r"^[-*] ", stripped):
            while i < len(lines) and re.match(r"^[-*] ", lines[i].strip()):
                story.append(Paragraph(inline(lines[i].strip()[2:]), st["bullet"],
                                       bulletText="•"))
                i += 1
            story.append(Spacer(1, 4))
            continue

        # A paragraph runs until a blank line or the start of another block.
        chunk = []
        while i < len(lines) and lines[i].strip() and not re.match(
                r"^(#{1,6} |[-*] |\||>|-{3,}$)", lines[i].strip()):
            chunk.append(lines[i].strip())
            i += 1
        text = " ".join(chunk)
        story.append(Paragraph(inline(text), st["lede"] if seen_title and
                               len(story) == 1 else st["body"]))
    return story


def footer(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 7.6)
    canvas.setFillColor(MUTED)
    canvas.drawString(doc.leftMargin, 0.55 * inch, "SRE Book Builder — Operator Guide")
    canvas.drawRightString(LETTER[0] - doc.rightMargin, 0.55 * inch,
                           f"page {canvas.getPageNumber()}")
    canvas.setStrokeColor(RULE)
    canvas.setLineWidth(0.5)
    canvas.line(doc.leftMargin, 0.72 * inch,
                LETTER[0] - doc.rightMargin, 0.72 * inch)
    canvas.restoreState()


def main() -> int:
    if not SOURCE.exists():
        raise SystemExit(f"Not found: {SOURCE}")

    doc = SimpleDocTemplate(
        str(TARGET), pagesize=LETTER,
        leftMargin=0.9 * inch, rightMargin=0.9 * inch,
        topMargin=0.85 * inch, bottomMargin=0.9 * inch,
        title="SRE Book Builder — Operator Guide",
        author="Upper Snake River Valley Historical Society",
        subject="How to turn scanned pages into a searchable, bookmarked PDF",
    )
    st = styles()
    width = LETTER[0] - doc.leftMargin - doc.rightMargin
    doc.build(convert(SOURCE.read_text(encoding="utf-8"), st, width),
              onFirstPage=footer, onLaterPages=footer)

    print(f"Wrote {TARGET}  ({TARGET.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
