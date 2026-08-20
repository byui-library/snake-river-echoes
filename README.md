# Snake River Echoes — SRE Book Builder

Turns a folder of TIFF page scans into a single PDF that is **searchable**, **navigable by
article**, and **small enough to share**.

Built to digitize *Snake River Echoes*, the journal of the Upper Snake River Valley
Historical Society, and intended to be installed on archive workstations by staff who
should not have to think about OCR.

> **Status: everything is built, including a 64 MB Windows installer.** What remains
> is running it on a machine that has never had development tools. See
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

Or use the window, which does both steps with the review in between:

```
py -m srebook.gui
```

Pick a folder and it reads the text in the background while you fill in the issue
details. Bookmarks it could not place are flagged in red; selecting any bookmark shows
that sheet, so you can confirm an article really starts there. Build takes about a
second, because the text is already read.

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
srebook/gui/      Tkinter interface (grid.py holds the rules, app.py the widgets)
tests/            183 tests, no image fixtures or display required
packaging/        vendoring, PyInstaller spec, Inno Setup script, sandbox test
docs/
  superpowers/specs/    design documents
CLAUDE.md         working guidance and hard constraints
```

## Building the installer

```
py packaging/build.py
```

Produces `dist/SREBookBuilder-0.1.0-setup.exe` (64 MB), which installs per-user and
needs no administrator — usually the obstacle to getting a tool onto a library
workstation. It bundles its own Tesseract and never uses one it finds on the machine.

`py packaging/make_sandbox.py` writes `dist/clean-test.wsb`. Double-clicking it opens
Windows Sandbox — a pristine, disposable Windows with no Python and no Tesseract, and
with networking switched off — installs the app, and builds a real issue. That is the
only environment in which "the installer works" means anything.

## Development

See [CLAUDE.md](CLAUDE.md) for constraints, vocabulary, and environment notes.
