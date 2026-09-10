# Snake River Echoes — SRE Book Builder

Turns a folder of TIFF page scans into a single PDF that is **searchable**, **navigable by
article**, and **small enough to share**.

Built to digitize *Snake River Echoes*, the journal of the Upper Snake River Valley
Historical Society, and intended to be installed on archive workstations by staff who
should not have to think about OCR.

> **Status: in daily use.** The installer is tested on a pristine Windows with no
> Python and no Tesseract and networking disabled — it installs, uses its own bundled
> OCR engine, and builds a searchable PDF. See
> [the design spec](docs/superpowers/specs/2026-08-20-sre-book-builder-design.md).

## Download

**[Latest release](https://github.com/byui-library/snake-river-echoes/releases/latest)** —
`SREBookBuilder-<version>-setup.exe`. Installs per-user, needs no administrator, and
bundles everything it uses. The printable
[operator guide](docs/operator-guide.pdf) is attached to the same page.

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
that sheet, so you can confirm an article really starts there.

The list holds *articles*, so **Previous / Next** step through every sheet including the
blank leaves and full-page photographs nothing points at — which is how you confirm a
scan is whole. **Merge up** joins a title to the byline underneath it when the parser
split one article in two, and **Undo** (or Ctrl-Z) steps back any change to the list.

## What you get per issue

A single PDF with:

- **A searchable text layer** over every page, produced by Tesseract OCR
- **Article-level bookmarks** in the sidebar, matching the issue's printed table of contents
- **Correct page labels** — the viewer's page box reads `7 (9 of 22)`, so a citation to
  printed page 7 lands on printed page 7
- **Embedded metadata** — title, volume, issue, year, publisher
- **The colour the scanner captured** — a colour scan stays in colour, a greyscale one
  stays greyscale

About 7 MB for a 22-page issue in greyscale, 16 MB for a 28-page issue in colour.

## Design in one paragraph

Scans are read at full 300 DPI in greyscale for OCR accuracy, but embedded at 200 DPI in
the scanner's own colour for file size — two separate derivatives, deliberately
decoupled, from one deskew measured once and applied to both. Tesseract emits **hOCR** (text plus word
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

Page scans are excluded by `.gitignore`, and none has ever been committed. The TIFFs are
the preservation master and live in archival storage; a clone will not have them. The
journal is the Historical Society's copyright, so no page of it appears here — not as a
fixture, and not inside a screenshot.

Development ran against 73 issue folders, 2,327 pages, 1971 to 2015. What that survey
found is in
[the scan completeness report](docs/scan-completeness-report.md): four issues with pages
demonstrably missing, four more to check against paper, and thirteen whose page numbers
could not be read well enough to judge.

## Repository layout

```
srebook/core/     the pipeline: ingest, prepare, ocr, outline, assemble
srebook/cli.py    command line front end
srebook/gui/      Tkinter interface (grid.py holds the rules, app.py the widgets)
tests/            432 tests, no display required
packaging/        vendoring, PyInstaller spec, Inno Setup script, sandbox test
docs/
  superpowers/specs/    design documents
CLAUDE.md         working guidance and hard constraints
```

## Building the installer

```
py packaging/build.py
```

Produces `dist/SREBookBuilder-<version>-setup.exe` (67 MB), which installs per-user and
needs no administrator — usually the obstacle to getting a tool onto a library
workstation. It bundles its own Tesseract and never uses one it finds on the machine.

`py packaging/make_sandbox.py` writes `dist/clean-test.wsb`. Double-clicking it opens
Windows Sandbox — a pristine, disposable Windows with no Python and no Tesseract, and
with networking switched off — installs the app, and builds a real issue. That is the
only environment in which "the installer works" means anything.

## For operators

[docs/operator-guide.pdf](docs/operator-guide.pdf) (print this) or
[the Markdown source](docs/operator-guide.md) — a page for the staff who
will run this: the flow, what a red bookmark means, and the difference between a sheet
and a printed page.

## Development

See [CLAUDE.md](CLAUDE.md) for constraints, vocabulary, and environment notes.

## License

MIT — see [LICENSE](LICENSE). Bundled dependencies keep their own permissive
terms (Tesseract is Apache 2.0). Ghostscript is deliberately not used: it is
AGPL, and its obligations would follow this program to every archive that
installs it.
