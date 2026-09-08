# Missing Pages and Page Labels Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to
> implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Make `Issue.missing_pages` authoritative and operator-editable, so an
issue with a gap in its scan carries the page numbers actually printed on its
pages.

**Architecture:** One function knows how sheets map to printed pages
(`page_labels`), and it skips any number listed in `missing_pages`. Every other
mapping helper reads that walk instead of computing `printed = sheet + offset`.
Detection gains the ability to see foot-of-page folios, which is what reveals a
gap in the first place. A bookmark whose page was never scanned stays in the
sidecar and is omitted from the PDF.

**Tech Stack:** Python 3.13, pytest, pikepdf, tkinter. No new dependencies.

**Spec:** [2026-09-08-missing-pages-and-page-labels-design.md](../specs/2026-09-08-missing-pages-and-page-labels-design.md)

**Invariant to preserve:** with `missing_pages` empty, every label is exactly
`sheet + offset`. Vol 1 Nos 1, 3 and 4 must not move.

---

### Task 1: `page_labels` skips missing pages

**Files:** Modify `srebook/core/model.py`; Test `tests/test_model.py`

- [ ] **Step 1: Write failing tests**

```python
def test_page_labels_skip_a_gap_in_the_scan():
    """Vol 1 No 2: cover 25, sheet 3 prints 27, then the scan jumps to 30."""
    issue = Issue(body_starts_at_sheet=1, body_starts_at_printed=25,
                  missing_pages=[28, 29])
    assert page_labels(issue, 20)[:5] == ["25", "26", "27", "30", "31"]
    assert page_labels(issue, 20)[-1] == "46"


def test_page_labels_are_linear_when_nothing_is_missing():
    issue = Issue(body_starts_at_sheet=1, body_starts_at_printed=49)
    assert page_labels(issue, 24) == [str(n) for n in range(49, 73)]


def test_a_missing_page_before_the_body_does_not_shift_the_roman_front_matter():
    issue = Issue(body_starts_at_sheet=3, body_starts_at_printed=1,
                  missing_pages=[2])
    assert page_labels(issue, 5) == ["i", "ii", "1", "3", "4"]
```

- [ ] **Step 2: Run and confirm failure**

Run: `py -m pytest tests/test_model.py -k page_labels -v`
Expected: FAIL on the gap tests, PASS on the linear one.

- [ ] **Step 3: Implement**

```python
def page_labels(issue: Issue, sheet_count: int) -> list[str]:
    missing = set(issue.missing_pages)
    labels: list[str] = []
    printed = issue.body_starts_at_printed
    for sheet in range(1, sheet_count + 1):
        if sheet < issue.body_starts_at_sheet:
            labels.append(_roman(sheet))
            continue
        while printed in missing:
            printed += 1
        labels.append(str(printed))
        printed += 1
    return labels
```

- [ ] **Step 4: Run the full suite** — `py -m pytest -q`. Expected: all pass.
- [ ] **Step 5: Commit** — `git commit -m "Skip pages the scan does not contain when numbering sheets"`

---

### Task 2: the other mapping helpers read the same walk

`printed_for_sheet`, `sheet_for_printed` and `sheet_for_label` compute
`printed = sheet + offset`. That is the assumption the gap breaks.

**Files:** Modify `srebook/core/model.py`; Test `tests/test_model.py`

- [ ] **Step 1: Write failing tests**

```python
def test_sheet_for_printed_crosses_a_gap():
    issue = Issue(body_starts_at_sheet=1, body_starts_at_printed=25,
                  missing_pages=[28, 29])
    assert sheet_for_printed(issue, 27) == 3
    assert sheet_for_printed(issue, 30) == 4
    assert sheet_for_printed(issue, 46) == 20


def test_a_page_that_is_missing_has_no_sheet():
    issue = Issue(body_starts_at_sheet=1, body_starts_at_printed=25,
                  missing_pages=[28, 29])
    assert sheet_for_printed(issue, 28) is None


def test_printed_for_sheet_crosses_a_gap():
    issue = Issue(body_starts_at_sheet=1, body_starts_at_printed=25,
                  missing_pages=[28, 29])
    assert printed_for_sheet(issue, 3) == 27
    assert printed_for_sheet(issue, 4) == 30
```

- [ ] **Step 2: Run and confirm failure.**
- [ ] **Step 3: Implement.** Both read `page_labels(issue, sheet_count)` and
  search it. `sheet_for_printed` returns `int | None` — **its signature
  changes**, so update every caller:
  - `gui/grid.py: set_printed` — treat `None` as refusal, it already returns bool
  - `core/model.py: _all_look_like_printed_pages` — a `None` means the value is
    not a printed page in this issue, so it does not support the heuristic
- [ ] **Step 4: Run the full suite.** Expected: all pass.
- [ ] **Step 5: Commit** — `git commit -m "Read the sheet-to-page mapping from one place"`

---

### Task 3: `gap_acknowledged` on the issue

**Files:** Modify `srebook/core/model.py`; Test `tests/test_model.py`

- [ ] **Step 1: Failing test**

```python
def test_the_acknowledgement_survives_a_save(tmp_path):
    issue = Issue(missing_pages=[28, 29], gap_acknowledged=True)
    path = tmp_path / "i.json"
    save_sidecar(issue, path)
    assert load_sidecar(path).gap_acknowledged is True


def test_an_older_sidecar_has_not_acknowledged_anything(tmp_path):
    path = tmp_path / "i.json"
    path.write_text('{"title": "SRE", "missing_pages": [28]}', encoding="utf-8")
    assert load_sidecar(path).gap_acknowledged is False
```

- [ ] **Step 2: Run and confirm failure.**
- [ ] **Step 3: Implement** — field defaulting to `False`, written only when
  true (matching how `missing_pages` is written), read with `.get(..., False)`.
- [ ] **Step 4: Run the suite. Step 5: Commit.**

---

### Task 4: read folios anywhere on the sheet

This is the defect that hid Vol 1 No 2's gap.

**Files:** Modify `srebook/core/outline.py`; Test `tests/test_outline.py`

- [ ] **Step 1: Failing test**

```python
def test_a_folio_at_the_foot_of_the_page_counts():
    """Vol 1 No 2 sheet 3 prints 27 at OCR line 47; Vol 1 No 3 prints its
    folios in the same mid-page position. lines[:2] never saw them."""
    body = {3: ["EASTERN IDAHO REVISITED"] + ["text"] * 40 + ["27"],
            4: ["30", "text"],
            5: ["text"] * 30 + ["31"]}
    assert printed_folios(body) == {3: 27, 4: 30, 5: 31}
```

- [ ] **Step 2: Run and confirm failure** (returns `{4: 30}` today).
- [ ] **Step 3: Implement.** Collect every bare-number line on the sheet. Where
  a sheet offers more than one, keep the candidate whose implied offset agrees
  with the offset most sheets support; if none agrees, contribute nothing for
  that sheet. Two passes: gather candidates, tally offsets, then choose.
- [ ] **Step 4: Run the suite**, especially `tests/test_outline.py`, which pins
  four real issues. Expected: all pass.
- [ ] **Step 5: Commit** — `git commit -m "See the folios this journal prints at the foot of the page"`

---

### Task 5: `detect_gaps`

**Files:** Modify `srebook/core/outline.py`; Test `tests/test_outline.py`

- [ ] **Step 1: Failing test**

```python
def test_a_jump_between_folios_names_the_pages_that_are_not_there():
    assert detect_gaps({3: 27, 4: 30, 5: 31}) == [28, 29]


def test_consecutive_folios_leave_no_gap():
    assert detect_gaps({4: 52, 5: 53, 6: 54}) == []


def test_folios_from_non_adjacent_sheets_do_not_invent_a_gap():
    """Sheet 4 prints 30 and sheet 8 prints 34; 31-33 simply print no folio."""
    assert detect_gaps({4: 30, 8: 34}) == []
```

- [ ] **Step 2: Run and confirm failure.**
- [ ] **Step 3: Implement** — for each pair of *adjacent* sheets present in the
  mapping, any numbers strictly between their folios are missing.
- [ ] **Step 4: Run the suite. Step 5: Commit.**

---

### Task 6: `detect_body_start` stops extrapolating through a gap

**Files:** Modify `srebook/core/outline.py`; Test `tests/test_outline.py`

- [ ] **Step 1: Failing test**

```python
def test_the_anchor_counts_back_from_the_earliest_folio_not_through_a_gap():
    """Vol 1 No 2: sheet 3 prints 27, so the cover is 25 -- not 27, which is
    what extrapolating the post-gap offset produced."""
    body = {3: ["A"] * 40 + ["27"], 4: ["30"], 5: ["31"], 6: ["32"]}
    assert detect_body_start(body) == (1, 25)
```

- [ ] **Step 2: Run and confirm failure** (returns `(1, 27)` today).
- [ ] **Step 3: Implement** — take the earliest sheet with a trusted folio and
  count back one printed page per sheet to sheet 1. Keep the existing rule that
  a single folio is coincidence: require at least two.
- [ ] **Step 4: Run the suite.** The Vol 1 Nos 1/3/4 pins must stay green:
  `(1, 1)`, `(1, 49)`, `(1, 73)`.
- [ ] **Step 5: Commit.**

---

### Task 7: the drafter merges both sources and flags the bookmark

**Files:** Modify `srebook/core/pipeline.py`; Test `tests/test_pipeline.py`

- [ ] **Step 1: Failing test** — drafting Vol 1 No 2's cached OCR yields
  `body_starts_at_printed == 25`, `missing_pages == [28, 29]`, and a bookmark
  titled *The Baltle of Pierre's Hole* with `review_reason == "missing"`.
- [ ] **Step 2: Run and confirm failure.**
- [ ] **Step 3: Implement** — union of `detect_gaps(folios)` and the existing
  contents-citation check, sorted. A contents entry whose cited page is in
  `missing_pages` gets `needs_review=True, review_reason="missing"`.
- [ ] **Step 4: Run the suite. Step 5: Commit.**

---

### Task 8: validation states the gap, and the build waits for acknowledgement

**Files:** Modify `srebook/core/model.py` (`validate`); Test `tests/test_model.py`

- [ ] **Step 1: Failing tests**

```python
def test_a_missing_bookmark_is_a_statement_not_a_fault():
    issue = Issue(missing_pages=[28], gap_acknowledged=True, bookmarks=[
        Bookmark("The Battle of Pierre's Hole", 4,
                 needs_review=True, review_reason="missing")])
    problems = validate(issue, sheet_count=20)
    assert problems == []


def test_an_unacknowledged_gap_stops_the_build():
    issue = Issue(missing_pages=[28, 29])
    problems = validate(issue, sheet_count=20)
    assert any("28, 29" in p for p in problems)
```

- [ ] **Step 2: Run and confirm failure.**
- [ ] **Step 3: Implement** — skip the `needs_review` complaint when the reason
  is `"missing"`; add one problem naming the pages while
  `missing_pages and not gap_acknowledged`.
- [ ] **Step 4: Run the suite. Step 5: Commit.**

---

### Task 9: assembly emits real label runs and drops missing bookmarks

**Files:** Modify `srebook/core/assemble.py`; Test `tests/test_assemble.py`

- [ ] **Step 1: Failing tests** — build a PDF for an issue with
  `missing_pages=[28, 29]` and assert `/PageLabels/Nums` contains a decimal run
  starting at 25 at index 0 and a second starting at 30 at index 3; and that a
  bookmark with `review_reason="missing"` does not appear in the outline.
- [ ] **Step 2: Run and confirm failure.**
- [ ] **Step 3: Implement** — derive runs by walking `page_labels()` and opening
  a new `/Nums` entry wherever a label is not the previous plus one; filter the
  outline before writing it.
- [ ] **Step 4: Run the suite. Step 5: Commit.**

---

### Task 10: the grid parses and edits the missing list

**Files:** Modify `srebook/gui/grid.py`; Test `tests/test_gui_grid.py`

- [ ] **Step 1: Failing tests**

```python
def test_the_missing_pages_field_accepts_a_typed_list():
    g = a_paginated_grid()
    assert g.set_missing_pages("28, 29")
    assert g.issue.missing_pages == [28, 29]


def test_editing_the_missing_list_withdraws_the_acknowledgement():
    g = a_paginated_grid()
    g.issue.gap_acknowledged = True
    g.set_missing_pages("28")
    assert g.issue.gap_acknowledged is False


def test_a_half_typed_missing_list_is_ignored():
    g = a_paginated_grid()
    assert not g.set_missing_pages("28,")
    assert not g.set_missing_pages("twenty")


def test_clearing_the_field_removes_every_gap():
    g = a_paginated_grid()
    g.set_missing_pages("28, 29")
    assert g.set_missing_pages("")
    assert g.issue.missing_pages == []


def test_missing_pages_display_as_a_typed_list():
    g = a_paginated_grid()
    g.set_missing_pages("29, 28")
    assert g.missing_pages_text() == "28, 29"
```

- [ ] **Step 2: Run and confirm failure. Step 3: Implement. Step 4: Run suite.
      Step 5: Commit.**

---

### Task 11: the window shows the field, the flag and the acknowledgement

**Files:** Modify `srebook/gui/app.py`; Test `tests/test_gui_app.py`

- [ ] **Step 1: Failing tests** — typing `28, 29` into the new field redraws the
  printed column so row for sheet 4 reads `30`; the Acknowledge button enables
  the build; a `missing` bookmark is counted separately in the status line.
- [ ] **Step 2: Run and confirm failure.**
- [ ] **Step 3: Implement** — entry bound with `trace_add` to
  `_on_missing_pages_edited`, guarded by `_loading_labels` exactly as the
  page-label fields are; an Acknowledge control; a third status-line count and a
  distinct tag for `missing` rows.
- [ ] **Step 4: Run the suite. Step 5: Commit.**

---

### Task 12: correct the fixtures, docs and clean-machine test

**Files:** Modify `packaging/sandbox_test.cmd`, `docs/operator-guide.md`,
`CLAUDE.md`, `pyproject.toml`, `packaging/installer.iss`

- [ ] **Step 1:** Change the clean-machine assertion from `27, 28` to `28, 29`.
      **Use the Write or Edit tool, never a shell heredoc** — that file has been
      corrupted twice by escape mangling.
- [ ] **Step 2:** Operator guide: a section on a scan with a gap — what the
      warning means, that the bookmark waits in the app, and that rescanning
      restores it. Regenerate `docs/operator-guide.pdf`.
- [ ] **Step 3:** `CLAUDE.md`: update the sample-data table and test count.
- [ ] **Step 4:** Bump version to 0.1.7 in both files.
- [ ] **Step 5:** `py packaging/build.py`, then run `dist/clean-test.wsb`.
- [ ] **Step 6:** Commit and tag.

---

### Task 13: retest Vol 1 No 2 end to end

- [ ] **Step 1:** Re-analyse Vol 1 No 2 in the installed build.
- [ ] **Step 2:** Confirm the field reads **sheet 1 is printed page 25**, the
      missing list reads **28, 29**, the cover shows **25**, sheet 3 shows
      **27** and sheet 4 shows **30**.
- [ ] **Step 3:** Confirm *The Battle of Pierre's Hole* is flagged missing and
      absent from the built PDF, while remaining in the sidecar.
- [ ] **Step 4:** Confirm Vol 1 Nos 1, 3 and 4 are unchanged.
