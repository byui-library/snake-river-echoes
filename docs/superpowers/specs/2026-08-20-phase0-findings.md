# Phase 0 Spike — Findings

**Date:** 2026-08-20
**Input:** `Image Files/SRE Vol 1 Number 1/` — 22 sheets, 300 DPI grayscale, 107 MB
**Verdict:** hOCR path proven. Proceed to Phase 1, with one design change.

## What the spike answered

The gate question was whether we can OCR at 300 DPI, embed at 200 DPI, and land the
invisible text layer accurately over the smaller image — the thing Tesseract's built-in
PDF renderer cannot do. Answer: yes.

## Measured results

| Metric | Result |
|---|---|
| Output PDF | **9.96 MB** from 107 MB of TIFFs (9.3%) |
| Per sheet | 453 KB |
| Mean OCR confidence | 93.3 overall, **94.1** on body sheets 3–22 |
| Words captured | 11,216 |
| OCR time | ~1.8 s/sheet (~40 s for the issue) |
| Rebuild after a bookmark edit | **0.15 s** (no re-OCR) |
| Deskew applied | 10 of 22 sheets, max 0.8° |
| Image storage | 98% of the PDF is raw JPEG passed through as `DCTDecode` |

### Text-layer alignment

Verified by rendering the finished PDF with PDFium and checking, for every word the OCR
found, whether the characters sitting at that location spell that word.

| Measure | Result |
|---|---|
| Words exactly recoverable at their own location | **99.42%** (11,151 of 11,216) |
| Horizontal centre error | mean 0.039 pt, max 0.28 pt |
| Vertical centre error | mean 0.55 pt, p99 1.28 pt, max 3.28 pt |

The residual 0.58% are all cases where the word is intact but a neighbouring character
also falls inside the test rectangle — a limitation of the check, not a defect in the PDF.
The 3.28 pt vertical maximum occurs on descender-heavy words; against a ~10 pt line that
still places the caret on the word.

## Bugs found and fixed

1. **Text set at the box bottom instead of the baseline.** hOCR word boxes span ascender
   to descender; text must be set on the baseline. Using the box bottom put every word a
   descender's depth low — a systematic 1.73 pt vertical error across every page. Fixed by
   reading the `baseline` coefficients from the enclosing `ocr_line` and deriving font size
   from the measured ascent. Vertical error dropped to 0.55 pt.

2. **Content stream encoded as latin-1 while the font declared WinAnsiEncoding.** latin-1
   has no curly quotes, so every typographic apostrophe became `?` in the searchable text
   (`Snake’` → `Snake?`). Fixed by encoding as cp1252. Recovered 25 words.

3. **Noise text from non-text pages.** The cover produced 61 "words" from a line-drawing
   map, 19 below confidence 40. A confidence floor of 30 removes them, which also stops
   phantom search hits.

## One thing that looked like a bug and was not

End-of-line hyphens appeared to render as an undefined glyph (`U+FFFE`). They do not.
`U+FFFE` is PDFium's own marker for a hyphen at a line break, emitted deliberately so
search can match across hyphenation. The hyphen is correct in the PDF. A dash-normalization
"fix" written in response to this was reverted, since WinAnsi carries en- and em-dashes
correctly and Tesseract already emits ASCII hyphens.

Recorded because the same false positive will recur in Phase 1's alignment test.

## DESIGN CHANGE: the TOC parser will not work as specified

The spec assumed the printed contents page could be parsed by matching the leader-dot
pattern `Title ....... 7`. **On this material it cannot.** Tesseract reads rows of periods
as random letters, and the page number at the end of the row is swallowed with them:

```
Eastern [dahiog 666037. FO ek ee ee ee mS
which drew interesite from ale over the states. 276. ee 7
country: hel pedi tovShapem mite. 6 ci. ce oes ee le eee eG
```

The **titles** survive perfectly; the **page numbers** do not.

### What works instead

Article titles appear verbatim in the body text at the point where the article begins, so
the sheet number can be found by locating the title rather than by reading a page number:

| TOC title | Located |
|---|---|
| A GOAL IS ACHIEVED | sheet 3 |
| ORAL HISTORY | sheet 4 |
| EASTERN IDAHO HISTORY FAIR - 1971 | sheet 7 |
| A BRIEF AUTOBIOGRAPHY | sheet 8 |
| ANDREW HENRY | sheet 11 (as "ANDREW HENRY - FUR TRAPPER") |
| WHO AND WHAT IN IDAHO | sheet 11 |
| IDAHO POETRY | not in body — section label only |
| BOOK LIST | not found (OCR'd as "BOOK WETS T" on the TOC page) |

Six of eight located automatically and exactly. The remaining two are section labels never
printed in the body, which is precisely what the operator grid exists to handle.

So `core/outline.py` becomes: extract ALL-CAPS candidate titles from the contents page
(cutting each line at its leader), then locate each in the body by normalized match, and
report sheet numbers. Page numbers are never parsed from the contents page.

Note the candidate filter must test capitalization on the **raw** line. Stripping lowercase
first turns author lines like `by Harold S. Forbush` into plausible-looking initials.

### Bonus: page labels can be derived, not typed

Even-numbered body sheets carry their printed page number as the first line (sheet 4 → "4",
sheet 6 → "6", … sheet 20 → "20"). For this issue the printed page number equals the sheet
number. This means the "which sheet is printed page 1" field can be **pre-filled by
detection** rather than left to the operator, with the field kept as an override.

## Material note

This issue contains **no photographs** — it is typewritten text throughout, with a line
drawing on the cover. Visual comparison of the 200 DPI embed against the 300 DPI original
shows slight softening and full legibility; typewriter strokes are heavy and survive the
downsample well. **200 DPI is confirmed for this issue**, but the halftone question is still
open, since later issues that contain photographs have not been tested.

## Carried into Phase 1

- Baseline-derived text placement, with the alignment test as a regression test
- cp1252 content-stream encoding
- Confidence floor of 30
- `U+FFFE` treated as a hyphen in the alignment test
- Title-location outline strategy, replacing leader-dot parsing
- Page-label detection from body headers, as a pre-fill

## Artifacts

Spike scripts are throwaway and live in the session scratchpad, not the repo. The generated
PDF, contact sheet and comparison crops are under `Image Files/SRE Vol 1 Number 1/output/`,
which is untracked.
