# CLAUDE.md

Guidance for Claude Code when working in this repository.

## What this is

**SRE Book Builder** — a Windows desktop application that turns a folder of TIFF page
scans into a single searchable, bookmarked, page-labeled PDF.

Built for digitizing *Snake River Echoes*, the journal of the Upper Snake River Valley
Historical Society, but intended to be handed to other archives as an installer.

**Current state: released through v0.1.9 and in daily use.** The installer is verified
on a pristine Windows with no Python and no Tesseract, and a special collections
employee is processing real issues with it.

**The repository is public**, MIT licensed, at
<https://github.com/byui-library/snake-river-echoes> -- which is the point: the program
is meant to be handed to other archives, and a repository nobody can read is not much of
a handover. Two consequences for anything committed here. The scans are the Historical
Society's, not the library's, so **no page of the journal goes into the repository** --
not as a test fixture beyond the tiny downsampled ones, and not inside a screenshot. And
no local paths: the guide's screenshots use a representative `D:\Scans\...`.

The authoritative design is
[docs/superpowers/specs/2026-08-20-sre-book-builder-design.md](docs/superpowers/specs/2026-08-20-sre-book-builder-design.md).
Read it before making architectural decisions. If code and spec disagree, that is a bug in
one of them — resolve it explicitly rather than silently following the code.

## Next session — start here

Released through v0.1.9 and in use by a special collections employee. `py -m pytest`
(432 tests) and `py packaging/build.py` both work from a clean checkout plus the
sample scans.

**Everything of consequence since v0.1.0 was found by someone using the program,
not by inspecting it.** Prefer putting a build in front of a real operator over
another round of tuning here.

**The whole collection has now been read**: 73 issue folders, 2,327 pages, 1971 to
2015 -- see [the scan completeness report](docs/scan-completeness-report.md) and
`packaging/survey_scans.py`. Re-surveying from cached OCR takes about 13 seconds, so a
change to how page numbers are read can be re-checked across every issue.

Issues from later decades broke the parser in ways the 1971 ones never could, and both
faults were invisible rather than loud: **Vol 27 prints its folios as `-5-`**, and
**Volume 18 is thick with dates and read 1959 as a page number**. Expect more of this
shape -- a reading that produces a confident wrong answer, not an error.

**Where the parser is still blind:** ten issues read too few page numbers to be judged
at all, mostly faint scans where OCR turns `—27—` into `xeP=`. The report lists them
under *Could not be checked*, and a blank there means nobody looked.

What has never needed changing across any of them: OCR, the text layer, deskew, page
labels, metadata and PDF assembly. The fragile part is narrow -- outline detection,
and reading the folder.

**Eight issues need pages rescanned.** Four on the strongest evidence, where the pages
either side of the gap print numbers that skip -- Vol 1 No 2 (28-29), Vol 6 No 1 (13-17),
Volume 18 (71-73), Volume 36 No 1 (5-9) -- and four more on the contents page alone.
The report has the detail; the scans still need redoing.

### Verified, with evidence

| Claim | Evidence |
|---|---|
| Text layer lands on the words | 100% of 34,494 words recoverable at their own location across three issues, colour and grey: `py packaging/verify_text_layer.py <folder>`. A 12 pt shift scores 1.4%, so the check is known to bite |
| Outline, page labels, metadata, search | checked on the real issue; Ctrl-F confirmed by the operator |
| Deskew applied to both derivatives | test; the OCR image is now derived from the rotated embed image, so they cannot drift apart |
| Packaged build refuses a system Tesseract | frozen exe exits 1 on this machine, which has one installed |
| Installer works with no dev tools | [clean-machine test](docs/superpowers/specs/2026-08-21-clean-machine-test-pass.txt), Windows Sandbox, networking off |
| Missing pages reported by the packaged build | clean-machine test on v0.1.8 names pages 28, 29 of Vol 1 No 2, and numbers its cover 25 |
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
- **The PDF embeds 200 DPI JPEG, in the colour the scanner captured.** This is what
  determines file size (~7 MB per 22-page issue). A greyscale scan stays greyscale; an
  RGB or RGBA one is embedded as RGB, with alpha flattened onto white because JPEG holds
  no transparency.

  Everything used to be converted to grey, decided when the whole corpus was 1971
  typescript. **64 of the 73 folders are colour**, so that published forty years of the
  journal in black and white, for about 7% in file size. Only the nine Vol 1 and Vol 2
  folders are genuinely grey.

  **The image dictionary must declare what the JPEG actually holds.** `DCTDecode` passes
  the JPEG through untouched, so `assemble._colour_space` reads its mode; hardcoding
  `DeviceGray` beside an RGB JPEG makes a viewer read three colour bytes as three grey
  pixels, and every page comes out smeared.

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

Stages are cached per sheet. Editing a bookmark and rebuilding must never re-OCR, and
does not.

**It is no longer near-instant, though.** `build` still re-runs `prepare_sheet` for every
sheet because it needs the embedded JPEG, and keeping colour made that about 1.7x more
expensive -- rotate and resample now run on three channels. Measured: ~580 ms per colour
sheet, so ~26 s to rebuild a 45-sheet issue. Caching `embed_jpeg` beside the `.hocr`,
keyed on `(sheet, embed_dpi)`, would make a bookmark edit cost no image work at all. Not
done.

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
py -m pytest                                                 # 432 tests, ~30s
```

Drafting an issue takes about 80 seconds. Rebuilding reuses the cached OCR but still
re-prepares every image, so it is ~26 s for a 45-sheet colour issue -- see Architecture.

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
  the real interpreter under `AppData/Local/Programs/Python/Python313/`, or just `py`.
- Tesseract, PyInstaller and Inno Setup are installed. Ghostscript and ImageMagick are
  not, and must stay that way. Note that `convert` on PATH is Windows' filesystem tool,
  not ImageMagick. ISCC lives at `~/AppData/Local/Programs/Inno Setup 6/ISCC.exe`.
- **Sample data lives in `Image Files/`, and it is four whole issues, not one.** This is
  the reproduction corpus — check a reported bug against it before asking for scans.
  Untracked (see `.gitignore`), 300 DPI, mostly colour (64 of 73 folders); do not assume a clone has it.

  | Folder | Sheets | Printed pages | Notes |
  |---|---|---|---|
  | `SRE Vol 1 Number 1` | 22 | 1–22 | sheet 1 is printed page 1, so it cannot show a page-label bug |
  | `SRE Vol 1 Number 2` | 20 | 25–46 | **missing pages 28, 29** — sheet 3 prints 27, sheet 4 prints 30. The gap-check fixture |
  | `SRE Vol 1 Number 3` | 24 | 49–72 | |
  | `SRE Vol 1 Number 4` | 22 | 73–94 | **missing pages 95, 96** |

  Each has cached OCR under `output/.cache`, so detection can be re-run in seconds
  without re-OCRing. **Never run `draft --force` across these** — it overwrites the
  operator's saved reviews, which are not in git. To inspect detection, call
  `outline.detect_body_start` on `pipeline._sheet_text` output; that writes nothing.
  Current code detects (1,1), (1,25), (1,49), (1,73) on the four — correct for all.

## Delivery phases

| Phase | Deliverable | Status |
|---|---|---|
| 0 | hOCR-to-PDF spike proven on the real 22 pages | **done** — [findings](docs/superpowers/specs/2026-08-20-phase0-findings.md) |
| 1 | Core + CLI; a finished Vol 1 No 1 PDF | **done** — 128 tests, real PDF built |
| 2 | Tkinter GUI | **done** — 165 tests |
| 3 | Inno Setup installer | **done** — [clean-machine test passed](docs/superpowers/specs/2026-09-10-clean-machine-test-v0.1.9.txt) |
| 4 | The whole collection surveyed for missing pages | **done** — [report](docs/scan-completeness-report.md), 73 folders, 2,327 pages |
| 5 | Colour preserved end to end | **done** — 0.1.9; 64 of 73 folders are colour |

Keep this table current.

**Not done, and worth doing.** `build` re-prepares every image even when the OCR is
cached, so a rebuild after a bookmark edit costs ~26 s on a 45-sheet colour issue.
Caching `embed_jpeg` beside the `.hocr`, keyed on `(sheet, embed_dpi)`, would make it
free. Separately, the OCR cache key does not include a stamp for the prepare pipeline, so
changing how the OCR image is derived does not invalidate what it invalidates -- adding
one would force a ~90 minute re-read of the collection, which is why it has not been.

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
- **A field the operator edits must redraw what it controls.** The two page-label entries
  were written once when an issue loaded and read again only when saving, with no
  `trace_add` between. Typing a corrected starting page changed nothing on screen, so the
  program looked as though it had stopped adjusting page numbers at all. `grid.OutlineGrid.
  set_page_labels` now holds the rule and the window redraws on every keystroke.

- **`detect_body_start` reads only `lines[:2]`, and this journal prints half its folios at
  the foot of the page.** Vol 1 No 2's sheet 3 prints 27 at OCR line 47; sheet 5 prints 31
  at line 40. Compare Vol 1 No 3, whose sheets 3, 5 and 7 print 51, 53 and 55 in the same
  mid-page position — so a bare number there is a real folio, not noise. An earlier note in
  this project called Vol 1 No 2's 27 "mirrored show-through"; **that was wrong.**

- **An issue with a gap cannot be described by one (sheet, printed) pair.** Vol 1 No 2 is
  cover 25, contents 26, sheet 3 = printed 27, **pages 28 and 29 never scanned**, then
  sheets 4-20 = 30-46. Three independent facts agree: sheet 3's own folio, the contents
  citing 27 for the article whose heading is on sheet 3, and the article it cites at 28
  being absent from the scan. Seeing only the post-gap folios, the detector measured one
  offset and extrapolated back through the hole, landing the cover on 27. It is right for
  17 sheets of 20 and wrong for the first three. PDF `/PageLabels` is a number tree and
  can express both runs; the model cannot yet. **Rescanning 28-29 removes the problem
  entirely** — prefer that over modelling the gap.

- **A rule that decides what the program does must live where the program can see it.**
  The coverage threshold that tells a readable page range from a guessed one lived in a
  report generator, so the report said Vol 9 No 2 was complete while the program refused
  to build it over four pages that do not exist. `outline.numbering_is_readable` now holds
  it, and both callers ask.

- **A guess made where there is no evidence is worse than no answer.** Vol 9 No 2 yields
  one folio across 25 sheets, so its labels fall back to 1..28. Every conclusion drawn
  against that fallback was fiction, and each one looked as confident as a real finding.

- **A setting whose effect the operator cannot see will be worked around.** The front
  matter's page labels were right, and the Printed page column showed a dash for them, so
  an operator with no confirmation that "sheet 3 is printed page 1" had taken effect typed
  `0` into the column instead. The fix was to display `i`, `ii`: the feature was never
  missing, only invisible. Reserve the dash for genuinely unknown.
- **Half a fix is worse than none.** Keeping the scanner's colour made the embedded JPEG
  RGB while the image dictionary still said `DeviceGray`, and every page of every colour
  issue came out smeared. The old all-grey behaviour was at least coherent. When a change
  crosses a boundary, test the seam, not each side: 384 tests passed because not one of
  them built a colour page.

- **The same wrong assumption is usually written down twice.** Grey conversion lived in
  `prepare.py` *and* in the preview in `app.py`. Fixing only the pipeline would have left
  the operator looking at grey and believing the output was grey; fixing only the preview
  would have hidden a real defect. Grep for the assumption, not for the symptom.

- **A parser that cannot read is more dangerous than one that errors.** Vol 27 prints
  `-5-` and read as unnumbered; Volume 18 is full of dates and read 1959 as a folio,
  concluding the issue ran to page 2004. Both produced a confident answer, and one of them
  would have sent an archivist to rescan pages that never existed. Detection now reports
  how many folios it actually read, and the report refuses to call an issue complete when
  the answer is "almost none".

- **Say what could not be checked, not just what failed.** An issue where detection found
  nothing and an issue with nothing wrong both produce an empty result. Presented as one
  list they are indistinguishable, and the blank reads as a clean bill of health.

- **An action that destroys information needs a way back, not an inverse.** Merge folds
  two titles and a sheet into one; there is nothing left to reconstruct them from. One
  snapshot before each action covers Merge, Remove and every other edit alike -- and is
  less code than a single bespoke un-merge.

- **Never write source files through a shell heredoc containing escapes.** Two did not
  survive, and one silently compiled a regex as `CONTENTS`.
