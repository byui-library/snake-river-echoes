# CLAUDE.md

Guidance for Claude Code when working in this repository.

## What this is

**SRE Book Builder** — a Windows desktop application that turns a folder of TIFF page
scans into a single searchable, bookmarked, page-labeled PDF.

Built for digitizing *Snake River Echoes*, the journal of the Upper Snake River Valley
Historical Society, but intended to be handed to other archives as an installer.

**Current state: design complete, no code yet.** The next step is the Phase 0 spike.

The authoritative design is
[docs/superpowers/specs/2026-08-20-sre-book-builder-design.md](docs/superpowers/specs/2026-08-20-sre-book-builder-design.md).
Read it before making architectural decisions. If code and spec disagree, that is a bug in
one of them — resolve it explicitly rather than silently following the code.

## Hard constraints

These are not preferences. Violating one breaks a promise the project has made.

| Constraint | Why |
|---|---|
| **Never modify the source TIFFs.** Open read-only. | They are the preservation master. There is no other copy in this repo. |
| **No AGPL dependencies.** Specifically no Ghostscript, and therefore no OCRmyPDF. | The app is redistributed to archives as an installer. AGPL obligations would follow it. |
| **No network or AI at runtime.** No API keys, no cloud OCR, no telemetry. | Must run on an air-gapped archive machine, operated by staff with no accounts. |
| **`srebook/core/` must never import `tkinter`.** | Core is the testable surface. GUI imports there make the whole pipeline untestable headless. |
| **Never commit scanned page images.** | See `.gitignore`. Only small downsampled test fixtures. |

## The two DPI numbers are different on purpose

This is the single easiest thing to get wrong in this codebase.

- **OCR reads 300 DPI** (the full original). Tesseract is tuned for 300; downsampling
  first measurably worsens accuracy on small print.
- **The PDF embeds 200 DPI** grayscale JPEG. This is what determines file size
  (~7 MB per 22-page issue).

They are decoupled deliberately. This is why the pipeline uses Tesseract's **hOCR** output
and composes the text layer itself, rather than using Tesseract's built-in PDF renderer
(which embeds whatever image it read, forcing the two to be equal).

Consequence: changing embed DPI never requires re-OCRing.

**Corollary — deskew must be applied to BOTH derivatives.** The angle is measured once per
page and applied to the 300 DPI OCR input and the 200 DPI embedded image alike. Applying it
to only one rotates the image out from under its own invisible text layer. That produces a
PDF that looks perfect and searches wrong, which is the worst failure mode this project has.

## Vocabulary

Used precisely throughout the code and spec:

- **sheet** — 1-based physical position in scan order. Sheet 1 is the first TIFF.
- **printed page** — the number printed on the paper by the 1971 typesetter.
- **page label** — the PDF feature that maps sheets to printed page numbers, so a viewer's
  page box reads `7 (9 of 22)`.

Never use "page" unqualified in code, comments, or UI text. It is ambiguous and the
distinction is the whole point of the page-label feature.

## Architecture

```
srebook/
  core/     no GUI imports; fully testable headless
    model.py     Issue / Bookmark dataclasses, sidecar read+write
    ingest.py    folder -> ordered sheets, metadata guess
    prepare.py   TIFF -> deskewed 300 DPI (OCR) + 200 DPI JPEG (embed)
    ocr.py       300 DPI image -> hOCR, cached per sheet
    outline.py   OCR text -> [(title, sheet)] guesses
    assemble.py  JPEGs + text layer + outline + labels + metadata -> PDF
  gui/      Tkinter/ttk
  cli.py    thin wrapper over core; also the manual test harness
```

Stages are cached per sheet. OCR is slow; assembly is ~1 second. Preserve that boundary —
editing a bookmark and rebuilding must never re-OCR.

## Conventions

- **TDD.** Tests before implementation. `core/` has no GUI dependency precisely so this
  is possible.
- **Errors are sentences, not tracebacks.** A single bad sheet must never abort an issue;
  include it image-only with a warning and continue.
- **The operator is the accuracy backstop.** The TOC parser is a head start, not a source
  of truth. Never build a flow that publishes unreviewed bookmarks.

## Environment notes

- Windows. The Bash tool is Git Bash; PowerShell is also available.
- **`python` on PATH is the Microsoft Store shim and does not work.** Use the real one:
  `/c/Users/milesm/AppData/Local/Programs/Python/Python313/python.exe` (3.13.15), or `py`.
- Tesseract, Ghostscript, and ImageMagick are **not** installed. `winget` and `choco` are
  available. Note that `convert` on PATH is Windows' filesystem tool, not ImageMagick.
- Sample data lives in `Image Files/SRE Vol 1 Number 1/` — 22 TIFFs, 300 DPI grayscale
  LZW, ~103 MB. Untracked. Do not assume a clone has it.

## Delivery phases

| Phase | Deliverable | Status |
|---|---|---|
| 0 | hOCR-to-PDF spike proven on the real 22 pages | not started |
| 1 | Core + CLI; a finished Vol 1 No 1 PDF | not started |
| 2 | Tkinter GUI | not started |
| 3 | Inno Setup installer | not started |

Keep this table current.
