# CLAUDE.md

Guidance for Claude Code when working in this repository.

## What this is

**SRE Book Builder** — a Windows desktop application that turns a folder of TIFF page
scans into a single searchable, bookmarked, page-labeled PDF.

Built for digitizing *Snake River Echoes*, the journal of the Upper Snake River Valley
Historical Society, but intended to be handed to other archives as an installer.

**Current state: released through v0.1.6 and in daily use.** The installer is verified
on a pristine Windows with no Python and no Tesseract, and a special collections
employee is processing real issues with it.

The authoritative design is
[docs/superpowers/specs/2026-08-20-sre-book-builder-design.md](docs/superpowers/specs/2026-08-20-sre-book-builder-design.md).
Read it before making architectural decisions. If code and spec disagree, that is a bug in
one of them — resolve it explicitly rather than silently following the code.

## Next session — start here

Released through v0.1.6 and in use by a special collections employee. `py -m pytest`
(306 tests) and `py packaging/build.py` both work from a clean checkout plus the
sample scans.

**Everything of consequence since v0.1.0 was found by someone using the program,
not by inspecting it.** Prefer putting a build in front of a real operator over
another round of tuning here.

**Six issues have been processed** (Vol 1 Nos 1-4, Vol 2 No 1, Vol 4 No 1), and each
one taught `core/outline.py` something new -- see the commit history. Each is pinned by
tests built from its own real OCR, so tuning for one cannot silently cost another.

The curve has not flattened. **An issue from a different decade is still the real
test**, and the parser should be expected to need work.

Also untested: **an issue containing photographs.** The issues seen so far are
typewritten text, so the 200 DPI embed decision has never been judged against a
halftone.

What has never needed changing across any of them: OCR, the text layer, deskew, page
labels, metadata and PDF assembly. The fragile part is narrow -- outline detection,
and reading the folder.

**Three of five scanned issues are missing pages** (Vol 1 No 2: 27-28, Vol 1 No 4:
95-96, Vol 2 No 1: 29). The program reports this now; the scans still need redoing.

### Verified, with evidence

| Claim | Evidence |
|---|---|
| Text layer lands on the words | 99.42% of 11,216 words recoverable at their own location, PDFium |
| Outline, page labels, metadata, search | checked on the real issue; Ctrl-F confirmed by the operator |
| Deskew applied to both derivatives | test, and the constraint is documented below |
| Packaged build refuses a system Tesseract | frozen exe exits 1 on this machine, which has one installed |
| Installer works with no dev tools | [clean-machine test](docs/superpowers/specs/2026-08-21-clean-machine-test-pass.txt), Windows Sandbox, networking off |
| Missing pages reported by the packaged build | clean-machine test on v0.1.6 names pages 27, 28 of Vol 1 No 2 |
| AppleDouble files ignored | packaged build reads 22 sheets from a folder of 22 scans + 22 ghosts |

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
  gui/
    grid.py      outline rules; imports no tkinter, so it is tested headless
    app.py       widgets, threading, layout only
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

## Running it

```
py -m srebook.cli draft "Image Files/SRE Vol 1 Number 1"    # OCR + propose outline
py -m srebook.cli build "Image Files/SRE Vol 1 Number 1"    # after reviewing the sidecar
py -m srebook.gui                                            # the window
py -m pytest                                                 # 301 tests, ~25s
```

Drafting an issue takes about 80 seconds; building from cached OCR is near-instant.

## Packaging

```
py packaging/build.py       # vendor Tesseract, freeze, compile installer, write .wsb
```

Then double-click `dist/clean-test.wsb` to run the whole thing in Windows Sandbox.

- **Tesseract is never handed to PyInstaller.** PyInstaller reclassifies loose DLLs as
  binaries and copies them to `_internal/` *as well as* the data destination — 130 MB
  duplicated, a 409 MB app instead of 90 MB. The installer lays `vendor/tesseract` down
  beside the exe, and `ocr.bundle_candidates` checks there first.
- **`tessdata/configs/` is not optional.** `hocr` on the Tesseract command line names
  `configs/hocr`, not a built-in flag. Without it Tesseract exits 0, silently writes plain
  text, and the pipeline finds no `.hocr` file. `vendor_tesseract.py` asserts it is there.
- **A packaged build never falls back to PATH.** Otherwise a build that bundled no
  Tesseract works perfectly on any developer machine and fails on the first archive
  workstation. `srebook doctor` reports which binary was resolved so a test can assert it.

## Environment notes

- Windows. The Bash tool is Git Bash; PowerShell is also available.
- **`python` on PATH is the Microsoft Store shim and does not work.** Use the real one:
  `/c/Users/milesm/AppData/Local/Programs/Python/Python313/python.exe` (3.13.15), or `py`.
- Tesseract, PyInstaller and Inno Setup are installed. Ghostscript and ImageMagick are
  not, and must stay that way. Note that `convert` on PATH is Windows' filesystem tool,
  not ImageMagick. ISCC lives at `~/AppData/Local/Programs/Inno Setup 6/ISCC.exe`.
- Sample data lives in `Image Files/SRE Vol 1 Number 1/` — 22 TIFFs, 300 DPI grayscale
  LZW, ~103 MB. Untracked. Do not assume a clone has it.

## Delivery phases

| Phase | Deliverable | Status |
|---|---|---|
| 0 | hOCR-to-PDF spike proven on the real 22 pages | **done** — [findings](docs/superpowers/specs/2026-08-20-phase0-findings.md) |
| 1 | Core + CLI; a finished Vol 1 No 1 PDF | **done** — 128 tests, real PDF built |
| 2 | Tkinter GUI | **done** — 165 tests |
| 3 | Inno Setup installer | **done** — [clean-machine test passed](docs/superpowers/specs/2026-08-21-clean-machine-test-pass.txt) |

Keep this table current.

## Phase 0 results carried into Phase 1

Proven: 9.96 MB output from 107 MB of TIFFs, OCR confidence 94.1 on body sheets, and
**99.42% of words exactly recoverable at their own location** in the finished PDF.

Non-obvious things the spike established — read the findings doc before writing
`core/ocr.py`, `core/outline.py`, or `core/assemble.py`:

- **Set text on the baseline, not the box bottom.** hOCR word boxes span ascender to
  descender. Using the bottom put every word 1.73 pt low. Read the `baseline` coefficients
  from the enclosing `ocr_line` and derive font size from the measured ascent.
- **Encode content streams as cp1252, not latin-1.** The font declares WinAnsiEncoding;
  latin-1 has no curly quotes, so apostrophes silently became `?`.
- **`U+FFFE` from PDFium is not a defect.** It is PDFium's marker for a hyphen at a line
  break. The alignment test must treat it as a hyphen or it will report ~38 false failures.
- **Drop words below confidence 30.** Non-text pages generate noise words that pollute
  search results.
- **The TOC leader-dot heuristic in the original spec does not work** and has been replaced
  by title-location. Tesseract reads dot leaders as random letters and swallows the page
  number with them.

## Phase 1-2 lessons

- **`Bookmark.needs_review` is recorded, never inferred.** An early version decided "the
  drafter could not place this" from `sheet == 1`, which flags a legitimate Front Cover
  bookmark as unreviewed. The drafter knows; it writes the flag down.
- **`detect_body_start` extrapolates back to printed page 1** rather than reporting the
  first sheet that prints a folio. Not every body page prints its number, and reporting
  the first numbered one labels real printed pages as roman front matter.
- **Candidate titles stop at the contents sheet.** Reading further picks up article
  headings, so an article whose heading is punctuated differently from its contents entry
  earns a second, duplicate bookmark.

## Lessons from six real issues and an operator

- **A contents page may be Title Case, not caps.** Capitalisation alone cannot then
  separate a title from the description under it, so those candidates are kept only
  where the body confirms them, and take their wording from the body heading.
- **The CONTENTS marker may be buried in a header line** ("Spring Issue, 1972 CONTENTS
  Volume 1, Number 4"). Requiring a line of its own made the cover's masthead the outline.
- **Page labels are not 1..N.** The journal is paginated continuously across each volume:
  No 2 is 27-46, No 3 49-72, No 4 73-94. The GUI briefly hardcoded the printed number to
  1, which silently destroyed a correct detection -- express the mapping, never assume it.
- **The front matter is known, not guessed.** Sheet 1 is the cover and the contents sheet
  was already found; both are bookmarked automatically.
- **A setting whose effect the operator cannot see will be worked around.** The front
  matter's page labels were right, and the Printed page column showed a dash for them, so
  an operator with no confirmation that "sheet 3 is printed page 1" had taken effect typed
  `0` into the column instead. The fix was to display `i`, `ii`: the feature was never
  missing, only invisible. Reserve the dash for genuinely unknown.
- **Never write source files through a shell heredoc containing escapes.** Two did not
  survive, and one silently compiled a regex as `CONTENTS`.
