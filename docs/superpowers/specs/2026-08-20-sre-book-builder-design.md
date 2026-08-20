# SRE Book Builder — Design

**Date:** 2026-08-20
**Status:** Approved, pending Phase 0 spike

## Problem

The Upper Snake River Valley Historical Society's journal *Snake River Echoes* exists as
folders of TIFF page scans. Each issue needs to become a single PDF that is searchable,
navigable by article, and small enough to share.

Source material on hand: `Image Files/SRE Vol 1 Number 1/` — 22 files,
`SRE_1971_Vol1_No1_01.tif` … `_22.tif`, 300 DPI grayscale LZW, ~8.5×11", 103 MB total.
This is high-quality OCR input.

This will be repeated for many issues, each producing its own book.

## Goals

- Turn a folder of TIFFs into one searchable, bookmarked, page-labeled PDF
- Run fully offline: no internet, no API keys, no Python install, no Claude
- Ship as a Windows installer that non-technical archive staff can run
- Keep a human reviewing every issue's bookmarks before publication

## Non-Goals (v1)

- Batch queueing of multiple issues
- PDF/A archival masters (the TIFFs are the preservation copy)
- Combined multi-volume books
- macOS builds
- Any AI or network dependency

## Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Scale | Many issues, one book each | Repeatable pipeline pointed at any folder |
| Outline | Article-level bookmarks from the printed TOC | Library/archive standard; per-page bookmarks are clutter |
| Page numbering | PDF page labels matching printed page numbers | Citations resolve correctly; the piece most home-grown scans skip |
| TOC source | Heuristic parse + operator review in a grid | Offline, no AI, human stays the accuracy backstop |
| OCR engine | Tesseract 5, bundled | Free, offline, Apache 2.0, redistributable |
| Outputs | Access copy only | TIFFs are the preservation master |
| OCR input DPI | 300 (full original) | Tesseract is tuned for 300; downsampling costs accuracy for no benefit |
| Embedded image DPI | 200 grayscale JPEG | ~7 MB per 22-page issue; revisit to 300 if photos look soft |
| Batch | One issue at a time | Every issue needs human TOC review anyway |
| GUI | Tkinter/ttk | PSF license, ~0 MB installer cost, native theming |
| Packaging | Inno Setup, self-contained Windows installer | No prerequisites for the operator |

### Why not OCRmyPDF

OCRmyPDF is the standard tool for scan-to-searchable-PDF and would be the right answer for
a personal script. It hard-depends on **Ghostscript, which is AGPL** — redistributing it
inside an installer handed to archives drags AGPL obligations onto the app or requires a
paid Artifex license. Using Tesseract directly plus pikepdf avoids this entirely.

### Why the hOCR path

OCR input DPI (300) and embedded image DPI (200) are deliberately decoupled: full OCR
accuracy, small output file. Tesseract's built-in PDF renderer embeds whatever image it
read, so it cannot separate the two. Instead Tesseract emits **hOCR** (text plus word
coordinates) and we place the invisible text layer over our own 200 DPI JPEG.

Consequence: embed DPI becomes a runtime dial. Changing it never requires re-OCRing,
because the text layer is resolution-independent.

## Stack

| Layer | Component | License |
|---|---|---|
| OCR | Tesseract 5 (bundled binary) | Apache 2.0 |
| Image prep | Pillow | MIT-CMU |
| PDF assembly, bookmarks, page labels | pikepdf (QPDF) | MPL 2.0 |
| GUI | Tkinter/ttk | PSF |
| Installer | Inno Setup | free |

All permissively licensed. One external binary.

## Pipeline

```
1. ingest     TIFFs -> ordered page list + parsed metadata guess
                 (natural sort, so _2 precedes _10)
2. prepare    deskew angle measured once per page, then applied to BOTH:
                 (a) 300 DPI grayscale image -> OCR input
                 (b) 200 DPI grayscale JPEG  -> embedded image
3. ocr        deskewed 300 DPI image -> hOCR (cached per page)
4. outline    OCR text of front matter -> [(title, sheet)] guesses
5. assemble   JPEGs + hOCR text layer + outline + labels + metadata -> PDF
```

Deskew is measured once and applied to both derivatives. Applying it to only one would
rotate the image out from under its own text layer — a silent misalignment that still
looks correct on screen.

Stages 1–3 are slow and deterministic; results are cached per page. Stage 5 is fast
(~1 second), so editing a bookmark and rebuilding does not re-OCR. That caching boundary
is the main reason for splitting 3 and 5.

## Data model

Each issue gets a sidecar `<name>.srebook.json` next to the output PDF, holding metadata,
bookmarks, and build settings. It makes rebuilds reproducible and doubles as the app's
save-file, so a half-reviewed issue survives a crash or a shift change.

```json
{
  "title": "Snake River Echoes",
  "volume": 1,
  "issue": 1,
  "year": 1971,
  "publisher": "Upper Snake River Valley Historical Society",
  "embed_dpi": 200,
  "page_labels": { "body_starts_at_sheet": 3, "body_starts_at_printed": 1 },
  "bookmarks": [
    { "title": "Front Cover", "sheet": 1 },
    { "title": "Table of Contents", "sheet": 2 },
    { "title": "Andrew Henry", "sheet": 11 },
    { "title": "Idaho Poetry", "sheet": 19, "children": [
      { "title": "My Home in Idaho", "sheet": 19 },
      { "title": "The Grand Old Snake", "sheet": 21 }
    ]}
  ]
}
```

`sheet` is 1-based and refers to physical scan order, never printed page number.

`children` is optional and nests one level only. A parent always carries its own `sheet`.

### Page labels

The operator supplies one number: which sheet carries printed page 1
(`body_starts_at_sheet`). Phase 0 found that body sheets print their page number as the
first line, so this field is **pre-filled by detection** and the operator only overrides it
when detection is wrong. Front-matter extent is derived from it, never stored separately. Sheets before it are
labeled lowercase roman (`i`, `ii`, …); the body is labeled decimal starting at its printed
number. Written as a PDF `/PageLabels` number tree. Result: Acrobat's page box reads
`7 (9 of 22)`.

### Metadata

Written to both the PDF Info dictionary and XMP: Title (`Snake River Echoes, Vol. 1,
No. 1 (1971)`), Author (the society), Subject, Keywords, creation date. Volume, issue,
and year are pre-filled by parsing filenames (`SRE_1971_Vol1_No1_01.tif`), but every
field stays editable — other archives will not use this naming convention.

### Outline structure

Bookmarks nest at most two levels: article, and optionally the separately-titled pieces
inside a printed department.

1. **Two levels, never three.**
2. **Nest only when a printed section holds 2 or more separately-titled pieces.** A
   one-item section is just an article.
3. **Ship expanded** (positive `/Count` on the outline node) while the issue's total entry
   count is under 40; collapse beyond that.
4. **Every node navigates.** No grouping label that fails to jump anywhere.

Rationale: navigation research favours broad-shallow over narrow-deep, and nesting is only
safe when the parent label predicts its children. "IDAHO POETRY" does not predict "The
Grand Old Snake", so that child must be visible on load rather than hidden behind a
collapsed node — hence rule 3. Rule 4 exists because a dead parent node is the most common
defect in hand-made PDF outlines.

For Vol 1 No 1 this yields 8 top-level entries, one of which expands to two poems.

### TOC parser

> **Revised after the Phase 0 spike.** The original leader-dot approach was tested against
> the real contents page and does not work. See
> [Phase 0 findings](2026-08-20-phase0-findings.md).

Two stages, neither of which reads a page number off the contents page:

1. **Extract candidate titles.** On the sheets before the body, cut each line at its dot
   leader and keep the lines that are overwhelmingly uppercase. Capitalization must be
   tested on the *raw* line — stripping lowercase first turns author credits like
   `by Harold S. Forbush` into plausible-looking initials.
2. **Locate each title in the body.** Article titles appear verbatim where the article
   begins, so the sheet number comes from finding the title, not from reading a printed
   page number.

Tesseract reads rows of periods as random letters and swallows the trailing page number
with them, so leader-dot parsing recovers titles but not numbers. Title location recovered
6 of 8 articles exactly on the test issue; the two misses were section labels never printed
in the body.

It remains a head start, not a dependency: the operator corrects the grid, and finding
nothing simply yields an empty grid.

## GUI

Single window, three zones, one linear path.

```
+- SRE Book Builder ---------------------------------------------+
|  Issue folder:  [ Image Files\SRE Vol 1 Number 1     ] [Browse] |
|                 22 pages found - 300 DPI grayscale              |
+----------------------------------------------------------------+
|  Title      [Snake River Echoes                    ]            |
|  Volume [1]  Issue [1]  Year [1971]                             |
|  Publisher  [Upper Snake River Valley Historical Society ]      |
|  Printed page 1 is sheet [ 3 ]     Embed quality [200 DPI v]    |
+----------------------------------------------------------------+
|  Bookmarks                            [Auto-detect from TOC]    |
|  +------------------------------+---------+   +--------------+  |
|  | Title                        |  Sheet  |   |              |  |
|  +------------------------------+---------+   |  page 9      |  |
|  | Front Cover                  |    1    |   |  preview     |  |
|  | Table of Contents            |    2    |   |              |  |
|  | Fort Hall Reminiscences      |    9    |<- |              |  |
|  | Pioneer Families             |   21    |   |              |  |
|  +------------------------------+---------+   +--------------+  |
|      [+ Add]  [Remove]  [up]  [down]                            |
+----------------------------------------------------------------+
|  [##############........]  OCR 14/22        [Cancel]  [Build]   |
+----------------------------------------------------------------+
```

Behavior:

- OCR starts automatically when a folder is picked, on a background thread, while the
  operator fills in metadata. It is usually finished by the time they reach the grid.
- Selecting a bookmark row shows that sheet's image in the preview pane. This is the
  highest-value accuracy feature: it confirms an article really starts on that sheet
  without opening a separate viewer.
- Build takes ~1 second because pages are already OCR'd. Fix, rebuild, look again.
- Autosave to the sidecar on every edit.

### Output location

The PDF and its sidecar are written to an `output/` folder created inside the issue folder,
named from the metadata: `output/SRE_1971_Vol1_No1.pdf` and `.srebook.json`. Source TIFFs
are opened read-only and never modified. The operator can redirect output elsewhere; the
app remembers the last choice.

## Error handling

Errors are stated in plain English and leave the app usable — never raw tracebacks.

| Condition | Behavior |
|---|---|
| Unreadable or corrupt TIFF | Named in a warning; page included image-only; build continues |
| Page fails OCR | Included image-only with a warning; build continues |
| Tesseract binary missing | Plain-language error at startup naming the expected path |
| No write permission on output | Error names the folder; operator can pick another |
| Folder has no TIFFs | Stated on selection, before any work starts |
| Bookmark points at a nonexistent sheet | Flagged in the grid; blocks Build until corrected |

A single bad page must never abort an issue.

## Code structure

```
srebook/
  core/           # no GUI imports anywhere; fully testable headless
    model.py        Issue / Bookmark dataclasses, sidecar read+write
    ingest.py       folder -> ordered pages, metadata guess
    prepare.py      TIFF -> 200 DPI grayscale JPEG
    ocr.py          TIFF -> hOCR + per-page cache
    outline.py      OCR text -> [(title, sheet)] guesses
    assemble.py     pages + outline + labels + metadata -> PDF
  gui/
    app.py, grid.py, preview.py
  cli.py          # thin wrapper over core; also the test harness
tests/
  fixtures/       # 4 real pages from Vol 1 No 1: cover, TOC, text, photo
packaging/
  srebook.spec    # PyInstaller
  installer.iss   # Inno Setup
```

`core/` never imports Tkinter. Every rule in the system is testable without a window.

## Testing

Tests are written before the code they cover.

- Natural sort: `_2` precedes `_10` (the classic scan-ordering bug)
- Filename to metadata parsing, including names not matching the SRE convention
- TOC leader-dot parsing against real OCR output from the Vol 1 No 1 contents page
- Page labels produce the correct `/PageLabels` structure, verified by reopening the PDF
- Bookmark tree round-trips through pikepdf intact
- **Text-layer alignment**: build from a fixture, extract text, assert a known phrase is
  present *and* its coordinates fall in the correct page region. This catches a silently
  misaligned OCR layer — the worst failure mode here, because the PDF still looks perfect.
- Output file size stays within expected bounds

## Delivery phases

| Phase | Deliverable | Gate |
|---|---|---|
| 0 — Spike | hOCR-to-PDF path proven on all 22 real pages; actual size, accuracy, timing | Report numbers; confirm 200 DPI embed looks right before building on it |
| 1 — Core + CLI | Working headless pipeline; **finished Vol 1 No 1 PDF** | Open it, search it, check the bookmarks |
| 2 — GUI | The window above | Run it on a second issue |
| 3 — Installer | Self-contained `.exe` installer, tested on a clean machine | Hand to an archive |

Phase 0 is small and answers the riskiest question first. Phase 1 delivers the actual
requested artifact before any GUI code exists.

## Risks

| Risk | Mitigation |
|---|---|
| hOCR coordinate scaling misaligns the text layer | Phase 0 spike; automated alignment test |
| Tesseract accuracy on 1971 print | 300 DPI grayscale input is near-ideal; measured in Phase 0 |
| 200 DPI embed too soft for photographs | Runtime dial; changing it never requires re-OCR |
| TOC heuristic weak on unusual layouts | Operator grid with page preview is the real mechanism |
| Installer size ~150–200 MB (mostly language data) | Ship English `tessdata` only |
