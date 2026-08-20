# Snake River Echoes — SRE Book Builder

Turns a folder of TIFF page scans into a single PDF that is **searchable**, **navigable by
article**, and **small enough to share**.

Built to digitize *Snake River Echoes*, the journal of the Upper Snake River Valley
Historical Society, and intended to be installed on archive workstations by staff who
should not have to think about OCR.

> **Status: the pipeline works.** `draft` then `build` produces a finished PDF.
> The GUI and installer are not written yet. See
> [the design spec](docs/superpowers/specs/2026-08-20-sre-book-builder-design.md).

## Using it

```
py -m srebook.cli draft "Image Files/SRE Vol 1 Number 1"
```

OCRs the issue, works out where the body starts, and proposes an outline by locating
each contents-page title in the body. Titles it cannot place are parked and reported.
Review the sidecar it writes, then:

```
py -m srebook.cli build "Image Files/SRE Vol 1 Number 1"
```

Vol 1 No 1: 22 sheets, 107 MB of TIFFs in, 9.97 MB PDF out, ~80 seconds.

## What you get per issue

A single PDF with:

- **A searchable text layer** over every page, produced by Tesseract OCR
- **Article-level bookmarks** in the sidebar, matching the issue's printed table of contents
- **Correct page labels** — the viewer's page box reads `7 (9 of 22)`, so a citation to
  printed page 7 lands on printed page 7
- **Embedded metadata** — title, volume, issue, year, publisher

About 7 MB for a 22-page issue.

## Design in one paragraph

Scans are read at full 300 DPI for OCR accuracy but embedded at 200 DPI for file size —
two separate numbers, deliberately decoupled. Tesseract emits **hOCR** (text plus word
coordinates) rather than a finished PDF, and the app composes the invisible text layer over
its own compressed images. Bookmarks come from a heuristic parse of the printed contents
page, presented to the operator in an editable grid alongside a page preview; a human
confirms every issue before it is published. Everything runs offline.

## Runs fully offline

No internet, no API keys, no accounts, no AI service. The finished app is a self-contained
Windows installer bundling Tesseract — no Python installation required on the target
machine. It is intended to work on an air-gapped archive workstation.

## Stack

| Layer | Component | License |
|---|---|---|
| OCR | Tesseract 5 (bundled) | Apache 2.0 |
| Image prep | Pillow | MIT-CMU |
| PDF assembly | pikepdf (QPDF) | MPL 2.0 |
| GUI | Tkinter/ttk | PSF |
| Installer | Inno Setup | free |

All permissively licensed. Notably **not** OCRmyPDF, whose Ghostscript dependency is AGPL
and would attach redistribution obligations to an installer handed to other institutions.

## Scanned material is not in this repository

Page scans are excluded by `.gitignore`. The TIFFs are the preservation master and live in
archival storage; a clone will not have them. Sample material used during development is
`Image Files/SRE Vol 1 Number 1/` — 22 TIFFs, 300 DPI grayscale, ~103 MB.

## Repository layout

```
srebook/core/     the pipeline: ingest, prepare, ocr, outline, assemble
srebook/cli.py    command line front end
srebook/gui/      Tkinter interface                     [not yet written]
tests/            128 tests, no image fixtures required
packaging/        PyInstaller spec, Inno Setup script   [not yet written]
docs/
  superpowers/specs/    design documents
CLAUDE.md         working guidance and hard constraints
```

## Development

See [CLAUDE.md](CLAUDE.md) for constraints, vocabulary, and environment notes.
