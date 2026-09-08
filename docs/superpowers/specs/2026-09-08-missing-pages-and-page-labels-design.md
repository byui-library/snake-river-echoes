# Missing pages and page labels — design

**Date:** 2026-09-08
**Status:** approved, not yet implemented
**Supersedes:** the missing-page reporting added in v0.1.3

## The problem

*Snake River Echoes* Vol 1 No 2 is labelled wrongly, and the program cannot
currently express the truth about it.

What the scan actually contains:

| Sheet | Printed page | |
|---|---|---|
| 1 | 25 | front cover |
| 2 | 26 | contents |
| 3 | 27 | *Eastern Idaho Revisited!* |
| — | **28, 29** | **never scanned** — *The Battle of Pierre's Hole* |
| 4–20 | 30–46 | |

Three independent facts establish this:

1. Sheet 3 prints `27` on the page itself, at OCR line 47.
2. The contents page cites 27 for *Eastern Idaho Revisited!*, whose heading is
   physically on sheet 3.
3. The contents page cites 28 for *The Battle of Pierre's Hole*, which appears
   nowhere in the scan.

Vol 1 No 3 prints its folios in the same mid-page position (sheets 3, 5 and 7
print 51, 53 and 55), so a bare number there is a real folio. An earlier note in
`CLAUDE.md` called Vol 1 No 2's `27` "mirrored show-through". That was wrong.

### Why the program gets it wrong

`detect_body_start` inspects only the first two OCR lines of each sheet
(`lines[:2]`). This journal prints roughly half its folios at the foot of the
page, so every folio it can see on Vol 1 No 2 (sheets 4, 6, 7, 8, 16) sits
*after* the gap. It measured a single offset from those, extrapolated straight
back through the hole, and put the cover on 27.

The result is right for 17 sheets of 20 and wrong for the first three — quiet
enough that nothing looked broken until the numbers were checked against paper.

The missing-page warning inherits the same error and names 27, 28 instead of
28, 29, which would send someone to rescan the wrong pages.

### Why one mapping cannot fix it

`Issue` describes pagination as a single pair: `body_starts_at_sheet` and
`body_starts_at_printed`. A book with a gap needs two runs. Neither available
setting is correct:

- `sheet 1 is printed page 27` — right for sheets 4–20, wrong for 1–3 (today)
- `sheet 1 is printed page 25` — right for sheets 1–3, wrong for 4–20

## Decisions taken

| Question | Decision |
|---|---|
| Bookmark for an unscanned page | Kept in the app and the saved review, **omitted from the PDF** |
| Which pages are missing | Detected from the printed folios, **operator can correct the list** |
| Does a gap block the build | Yes, until acknowledged once; corrected by editing the numbers or by rescanning |

Omitting the bookmark from the PDF follows the project's existing rule: a
bookmark that jumps to the wrong page is worse than no bookmark, because a
reader has no way to tell.

## Design

The organising idea: **`Issue.missing_pages` already exists. Make it
authoritative and operator-editable, and derive everything else from it.** No
new pagination model, and the operator still sets exactly one starting number.

### Model — `core/model.py`

`page_labels(issue, sheet_count)` walks the sheets from the anchor, skipping any
printed number listed in `missing_pages`:

```
start 25, missing {28, 29}
  sheet 1 -> 25   sheet 2 -> 26   sheet 3 -> 27
  28 skipped, 29 skipped
  sheet 4 -> 30   ...   sheet 20 -> 46
```

Sheets before `body_starts_at_sheet` remain lowercase roman, unchanged.

`printed_for_sheet`, `sheet_for_printed` and `sheet_for_label` stop computing
`printed = sheet + offset` and read the same walk. **This is the main
correctness risk in the change**: three functions currently assume a linear
mapping, and that assumption is precisely what is wrong. After this there is one
function that knows how sheets map to printed pages, and everything else asks
it.

New field `gap_acknowledged: bool`, default `False`, persisted in the sidecar.
Set to `False` whenever `missing_pages` changes, so a corrected list must be
looked at again.

### Detection — `core/outline.py`

- `printed_folios` accepts a bare-number line **anywhere** on a sheet, not only
  in the first two lines. Where a sheet offers more than one bare number, take
  the one whose implied offset agrees with the majority of other sheets; if none
  does, take none and let that sheet contribute nothing.
- The existing contents-page check is **kept, not replaced**. Folios reveal a
  gap in the middle of an issue; citations reveal pages missing from the end,
  where no following folio exists to show a jump. The two results are merged
  into `missing_pages`.
- New `detect_gaps(folios) -> list[int]`: where consecutive sheets carry folios
  that jump by more than one, the skipped numbers are missing. Sheet 3 printing
  27 followed by sheet 4 printing 30 yields `[28, 29]`.
- `detect_body_start` anchors on the **earliest trusted folio** and counts back
  across the front matter, rather than extrapolating an offset through a gap.
- OCR misreads a folio occasionally (sheet 14 of Vol 1 No 2 reads 40 as 49). A
  folio is trusted only when it agrees with the offset that the majority of
  sheets support, which is the rule `missing_pages` already uses.

### Bookmarks — `core/pipeline.py`, `core/assemble.py`

- New `review_reason = "missing"`, set when a contents entry's cited page is in
  `missing_pages`.
- `validate()` reports it as a statement of fact, not a fault the operator must
  repair. It does not demand a sheet number, because there is no sheet to give.
- The build is refused while `missing_pages` is non-empty and
  `gap_acknowledged` is `False`. Once acknowledged it does not ask again for
  that issue unless the list changes.
- Assembly omits bookmarks whose reason is `missing`. They stay in the sidecar,
  so rescanning the pages and rebuilding restores them in place.

### Assembly — `core/assemble.py`

`_add_page_labels` currently emits at most two runs: an optional roman range and
one decimal range. It must derive its runs from the label list — start a new
`/Nums` entry wherever a label is not the previous label plus one. PDF
`/PageLabels` is a number tree and expresses this natively.

For Vol 1 No 2 that is three runs: roman none, decimal from 25 at sheet 1,
decimal from 30 at sheet 4.

### Window — `gui/grid.py`, `gui/app.py`

- The issue panel gains an editable **"Pages missing from this scan"** field,
  comma separated. Editing it re-derives the printed page column live, using the
  `trace_add` mechanism added in the previous change, and clears the
  acknowledgement.
- Parsing lives in `grid.OutlineGrid`, which imports no tkinter, so the rules
  are tested without a display. A half-typed field leaves the list alone.
- An **Acknowledge** action clears the build gate and is persisted.
- Missing bookmarks display the printed page they belong on and are marked
  distinctly from the two existing red kinds. The status line counts them
  separately, as it already does for "to keep or remove" and "needs a page
  number".

## Sidecar format

Two additions. Both are optional on read, so an older sidecar loads unchanged.

```json
{
  "page_labels": { "body_starts_at_sheet": 1, "body_starts_at_printed": 25 },
  "missing_pages": [28, 29],
  "gap_acknowledged": true
}
```

## Testing

Pinned to real OCR, in the manner of the existing per-issue tests:

- **Vol 1 No 2** — detects start 25 and missing `[28, 29]`; labels are
  `25, 26, 27, 30 … 46`; *The Battle of Pierre's Hole* is flagged `missing` and
  absent from the built PDF.
- **Vol 1 Nos 1, 3, 4** — unchanged: `(1, 1)`, `(1, 49)`, `(1, 73)`, no gaps.
  These guard against fixing one issue at the cost of three.
- `page_labels` with a gap, with a gap inside front matter, and with a missing
  page beyond the last sheet.
- `sheet_for_printed` round-trips across a gap.
- Grid: parsing the missing-pages field, half-typed input, clearing the
  acknowledgement on edit.
- Assembly: a three-run `/PageLabels` tree reads back correctly.

## Migration

Saved reviews already on disk carry missing-page numbers produced by the old
logic — Vol 1 No 2's says 27, 28. They are corrected by re-analysing the issue
or by editing the field. The program does not rewrite a saved review on load.

The clean-machine test asserts the packaged build names "27, 28" for Vol 1
No 2. That assertion pins the bug and must be updated to 28, 29.

`CLAUDE.md` records the corrected facts as of this change.

## Out of scope

- Generating placeholder pages for unscanned leaves.
- Marking the gap anywhere in the PDF itself. The omission is silent by
  decision; the record of it lives in the sidecar and the window.
- Detecting pages missing from the **end** of an issue, where there is no
  following folio to reveal a jump. Vol 1 No 4's missing 95–96 are known only
  from the contents page, and that check stays as it is.
