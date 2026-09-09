# Snake River Echoes — scan completeness report

Every page scan in `Image Files/` read and checked: **73 issue folders, 2327 pages.**

Two independent signals are used. The **printed page numbers** on the pages
themselves reveal a gap in the middle of an issue: if one scan prints 27 and
the next prints 30, then 28 and 29 are not in the folder. The **contents
page's own citations** reveal pages missing off the end, where no later
number exists to show the jump.

**A blank entry does not mean an issue is complete.** It can also mean the
program could not read that issue's page numbers at all. Those are listed
separately, under *Could not be checked*, and need a person.

## What to act on

| | Issues |
|---|---|
| Pages missing, strong evidence | **4** |
| Pages missing, weaker evidence | 0 |
| Probably a false alarm | 16 |
| Could not be checked | 10 |
| No problem found | 43 |

## 1. Pages missing — strong evidence

The pages either side of the gap print their own numbers, and those numbers
skip. This is the most reliable finding in the report: **rescan these.**

| Issue | Missing printed pages | Page numbers read | Issue runs |
|---|---|---|---|
| SRE Vol 1 Number 2 | **28, 29** | 10 of 18 | 25–46 |
| SRE Vol 6 Number 1 | **13, 14, 15, 16, 17** | 12 of 27 | i–31 |
| SRE Volume 18 | **71, 72, 73** | 34 of 85 | i–89 |
| SRE Volume 36 / SRE Volume 36 Number 1 | **5, 6, 7, 8, 9** | 15 of 26 | i–26 |

## 2. Pages missing — weaker evidence

Where the contents page cites a page no scan carries, **and** that citation
falls inside the issue's own numbering, so it is credible without the page
numbers themselves confirming it.

**None.** Every citation-only finding fell outside its issue's numbering,
which points at the program's reading rather than at the scan. They are in
section 3.

## 3. Probably a false alarm — do not rescan on this alone

In each of these the contents page cites pages that fall **outside** the
numbering the program worked out for the issue. When every citation lands
outside, the likely fault is the program's idea of where the numbering
starts, not the scan.

This was confirmed by eye. **Vol 9 Number 2** is listed below as missing
eleven pages. Its sheet 5 prints `—27—` and its sheet 10 prints `—32—`, so
the issue runs 23 to 50 and its contents citing 31–48 is correct: **nothing
is missing from it.** The program read its page numbers as 1–28 because the
scans are faint and OCR could not make them out — sheet 5's `—27—` came
through as `xeP=`.

They divide into two, and the difference decides what to do about them.

**a. The issue's numbering is not known.** Too few page numbers were readable
to trust the range, so a citation outside it means nothing. Vol 9 No 2 above
is one of these. To settle any of them, look at one page and read the number
printed on it.

| Issue | Cited but not found | Range the program guessed | Page numbers read |
|---|---|---|---|
| SRE Volume 8 / SRE Vol 8 Number 4 | 75, 78, 83, 85, 92, 96 | 1–28 | **1 of 25** |
| SRE Volume 9 / SRE Vol 9 Number 2 | 31, 32, 37, 38, 39, 43, 44, 45, 46, 47, 48 | 1–28 | **1 of 25** |
| SRE Volume 9 / SRE Vol 9 Number 4 | 74, 75, 76, 80, 82, 84, 87, 91, 94 | 1–28 | **1 of 25** |

**b. The numbering is well established, so the citation is the error.** Here
the range is confirmed by many printed page numbers, and the cited page could
not exist in the issue — page 100 of an issue that ends at 50. The contents
page has been misread, most often a price or a dot leader taken for a page
number. Nothing to rescan.

| Issue | Cited but not found | Issue runs | Page numbers read |
|---|---|---|---|
| SRE Vol 1 Number 4 | 95, 96 | 73–94 | 13 of 20 |
| SRE Vol 2 Number 1 | 29 | 1–24 | 13 of 22 |
| SRE Vol 3 Number 2 | 81, 88 | 20–43 | 18 of 21 |
| SRE Vol 4 Number 1 | 100 | i–25 | 10 of 25 |
| SRE Vol 4 Number 2 & 3 | 100 | 21–56 | 16 of 33 |
| SRE Vol 4 Number 4 | 4 | 52–91 | 29 of 39 |
| SRE Vol 5 Number 2 | 100 | 23–50 | 20 of 25 |
| SRE Vol 6 Number 4 | 5, 15 | 71–98 | 22 of 25 |
| SRE Volume 24 / SRE Vol24 Number 2 | 20 | 23–50 | 20 of 26 |
| SRE Volume 25 / SRE Vol 25 Number 2 | 20 | 23–50 | 22 of 26 |
| SRE Volume 31 / SRE Vol 31 Number  2 | 2 | 23–58 | 17 of 34 |
| SRE Volume 33 / SRE Vol 33 Number 1 | 69, 70, 88, 89, 90 | i–26 | 11 of 26 |
| SRE Volume 37 / SRE Volume 37 Number 2 | 1 | 23–58 | 25 of 34 |

## 4. Could not be checked

Too few printed page numbers were readable to say anything. **These are not
clean bills of health — nobody has checked them.** Verify against the paper
copies, or rescan at a setting that renders the page numbers legibly.

| Issue | Page numbers read | Sheets |
|---|---|---|
| SRE Volume 20 | 12 of 49 | 52 |
| SRE Volume 23 / SRE Vol 23 Number 1 | 3 of 28 | 30 |
| SRE Volume 26 / SRE Vol 26 Number 1 | 6 of 26 | 28 |
| SRE Volume 27 / SRE Vol 27 Number 1 | 2 of 26 | 28 |
| SRE Volume 30 / SRE Vol 30 Number  1 | 4 of 26 | 28 |
| SRE Volume 31 / SRE Vol 31 Number  1 | 2 of 26 | 28 |
| SRE Volume 35 / SRE Volume 35 Number 1 | 3 of 26 | 28 |
| SRE Volume 8 / SRE Vol 8 Number 1 | 1 of 25 | 28 |
| SRE Volume 9 / SRE Vol 9 Number 1 | 1 of 25 | 28 |
| SRE Volume 9 / SRE Vol 9 Number 3 | 3 of 25 | 28 |

## 5. No problem found

43 issues where enough page numbers were read to trust the result,
and they run consecutively with every cited page present.

<details><summary>Show the list</summary>

- SRE Vol 1 Number 1 — 22 sheets, pages 1–22, 14 of 20 page numbers read
- SRE Vol 1 Number 3 — 24 sheets, pages 49–72, 15 of 22 page numbers read
- SRE Vol 2 Number 2 — 24 sheets, pages 25–48, 17 of 22 page numbers read
- SRE Vol 2 Number 3 — 24 sheets, pages 49–72, 16 of 22 page numbers read
- SRE Vol 2 Number 4 — 22 sheets, pages 73–94, 18 of 20 page numbers read
- SRE Vol 3 Number 1 — 22 sheets, pages 1–22, 8 of 21 page numbers read
- SRE Vol 3 Number 3 — 20 sheets, pages 40–59, 10 of 17 page numbers read
- SRE Vol 3 Number 4 — 20 sheets, pages 56–75, 14 of 17 page numbers read
- SRE Vol 5 Number 1 — 28 sheets, pages i–26, 7 of 27 page numbers read
- SRE Vol 5 Number 3 — 28 sheets, pages 47–74, 12 of 25 page numbers read
- SRE Vol 5 Number 4 — 28 sheets, pages 71–98, 16 of 25 page numbers read
- SRE Vol 6 Number 2 — 28 sheets, pages 23–50, 13 of 25 page numbers read
- SRE Vol 6 Number 3 — 28 sheets, pages 47–74, 16 of 25 page numbers read
- SRE Volume 16 — 58 sheets, pages i–56, 42 of 55 page numbers read
- SRE Volume 17 — 52 sheets, pages i–50, 19 of 49 page numbers read
- SRE Volume 19 — 54 sheets, pages i–52, 17 of 51 page numbers read
- SRE Volume 21 / SRE Vol 21 Number 1 — 28 sheets, pages i–26, 9 of 26 page numbers read
- SRE Volume 21 / SRE Vol 21 Number 2 — 28 sheets, pages 23–50, 21 of 26 page numbers read
- SRE Volume 22 / SRE Vol 22 Number 1 — 28 sheets, pages i–26, 12 of 26 page numbers read
- SRE Volume 22 / SRE Vol 22 Number 2 — 30 sheets, pages 23–52, 24 of 28 page numbers read
- SRE Volume 23 / SRE Vol 23 Number 2 — 29 sheets, pages 23–51, 18 of 27 page numbers read
- SRE Volume 24 / SRE Vol 24 Number 1 — 28 sheets, pages i–26, 13 of 26 page numbers read
- SRE Volume 25 / SRE Vol 25 Number 1 — 28 sheets, pages i–26, 14 of 26 page numbers read
- SRE Volume 26 / SRE Vol 26 Number 2 — 28 sheets, pages 23–50, 22 of 26 page numbers read
- SRE Volume 27 / SRE Vol 27 1998 Commemorative — 28 sheets, pages i–26, 13 of 26 page numbers read
- SRE Volume 27 / SRE Vol 27 Number 2 — 28 sheets, pages 23–50, 7 of 26 page numbers read
- SRE Volume 28 / SRE Vol 28 Number  1 — 28 sheets, pages i–26, 10 of 26 page numbers read
- SRE Volume 28 / SRE Vol 28 Number  2 — 28 sheets, pages 23–50, 8 of 26 page numbers read
- SRE Volume 29 / SRE Vol 29 Number  1 — 28 sheets, pages i–26, 11 of 26 page numbers read
- SRE Volume 29 / SRE Vol 29 Number  2 — 28 sheets, pages 23–50, 8 of 26 page numbers read
- SRE Volume 30 / SRE Vol 30 Number  2 — 40 sheets, pages 23–62, 17 of 38 page numbers read
- SRE Volume 32 / SRE Vol 32 Number 1 — 48 sheets, pages i–46, 32 of 46 page numbers read
- SRE Volume 32 / SRE Vol 32 Number 2 — 28 sheets, pages 43–70, 21 of 26 page numbers read
- SRE Volume 32 / SRE Vol 32 Number 3 — 28 sheets, pages 67–94, 14 of 26 page numbers read
- SRE Volume 33 / SRE Vol 33 Number 2 — 28 sheets, pages 23–50, 16 of 26 page numbers read
- SRE Volume 35 / SRE Volume 35 Number 2 — 68 sheets, pages 23–90, 53 of 66 page numbers read
- SRE Volume 35 / SRE Volume 35 Number 3 — 24 sheets, pages 87–110, 18 of 22 page numbers read
- SRE Volume 37 / SRE Volume 37 Number 1 — 28 sheets, pages i–26, 10 of 26 page numbers read
- SRE Volume 38 — 43 sheets, pages i–41, 28 of 42 page numbers read
- SRE Volume 8 / SRE Vol 8 Number 2 — 28 sheets, pages 23–50, 22 of 25 page numbers read
- SRE Volume 8 / SRE Vol 8 Number 3 — 28 sheets, pages 47–74, 21 of 25 page numbers read
- SRE_Vol_38 / SRE_Vol38 / PDF / SRE_Vol38 / TIFF / SRE_Vol38 — 43 sheets, pages i–41, 28 of 42 page numbers read
- SRE_index_vol1-37 / PDF / SRE_index_vol1-37 / TIFF / SRE_index_vol1-37 — 76 sheets, pages i–74, 42 of 75 page numbers read

</details>

## 6. Gaps in the collection itself

Not about pages within an issue, but about what is not here at all.

**Volumes present:** 1, 2, 3, 4, 5, 6, 8, 9, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 35, 36, 37, 38

**Volumes with no folder at all:** **7, 10, 11, 12, 13, 14, 15, 34**

Nothing in this report says anything about those years — there is nothing
to check. They are the largest gap in the collection.

**Folders that are not a single issue of scans:**

| Folder | What it is |
|---|---|
| `SRE_1988March` | 28 single-page **PDFs**, no TIFF scans, so nothing here could check it. 1988 is Volume 17, so this is probably one of that volume's issues delivered in the wrong format. |
| `SRE_index_vol1-37` | The cumulative index for volumes 1–37, not an issue. 76 scans, surveyed like an issue, so ignore its row above. |
| `SRE_Vol_38` | The same 43 pages as `SRE Volume 38`, exported differently (`001.tif` rather than `SRE_2015_Vol38_No1_01.tif`). **Volume 38 was therefore checked twice**; one copy can go. |
| `SRE Volume 17`–`20` | A whole year of scans in one folder, with no issue number in the file names. The numbering runs continuously, so the check still works, but these are not one issue each. |

