"""Turn survey.json into the missing-pages report."""
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DATA = json.loads((REPO / "docs" / "scan-survey-data.json").read_text(encoding="utf-8"))
OUT = REPO / "docs" / "scan-completeness-report.md"

CONFIDENT = 0.25          # folios read, as a share of body sheets


def rng(r):
    def num(v):
        return int(v) if v and v.isdigit() else None
    return num(r.get("first_label")), num(r.get("last_label"))


def share(r):
    return r["folios_read"] / r["body_sheets"] if r.get("body_sheets") else 0.0


rows = [r for r in DATA if "error" not in r]
for r in rows:
    lo, hi = rng(r)
    r["_lo"], r["_hi"] = lo, hi
    r["_share"] = share(r)
    r["_readable"] = r["_share"] >= CONFIDENT and r["anchor"] is not None
    out_of_range = bool(r["cited_but_absent"]) and (
        lo is None or hi is None
        or not all(lo <= p <= hi for p in r["cited_but_absent"]))
    r["_out_of_range"] = out_of_range

# One bucket each, most actionable first, so the counts add up to the total.
gaps, plausible, suspect, unreadable, clean = [], [], [], [], []
for r in rows:
    if r["gaps_from_folios"]:
        gaps.append(r)
    elif r["cited_but_absent"] and not r["_out_of_range"]:
        plausible.append(r)
    elif r["_out_of_range"]:
        suspect.append(r)
    elif not r["_readable"]:
        unreadable.append(r)
    else:
        clean.append(r)
assert len(gaps) + len(plausible) + len(suspect) + len(unreadable) + len(clean) == len(rows)


def pages(values):
    return ", ".join(str(v) for v in values)


def label(r):
    return r["folder"].replace("\\", " / ")


def issue_range(r):
    return f"{r['first_label']}–{r['last_label']}" if r["first_label"] else "unknown"


lines = []
w = lines.append

w("# Snake River Echoes — scan completeness report")
w("")
w(f"Every page scan in `Image Files/` read and checked: "
  f"**{len(rows)} issue folders, {sum(r['sheets'] for r in rows)} pages.**")
w("")
w("Two independent signals are used. The **printed page numbers** on the pages")
w("themselves reveal a gap in the middle of an issue: if one scan prints 27 and")
w("the next prints 30, then 28 and 29 are not in the folder. The **contents")
w("page's own citations** reveal pages missing off the end, where no later")
w("number exists to show the jump.")
w("")
w("**A blank entry does not mean an issue is complete.** It can also mean the")
w("program could not read that issue's page numbers at all. Those are listed")
w("separately, under *Could not be checked*, and need a person.")
w("")
w("## What to act on")
w("")
w(f"| | Issues |")
w(f"|---|---|")
w(f"| Pages missing, strong evidence | **{len(gaps)}** |")
w(f"| Pages missing, weaker evidence | {len(plausible)} |")
w(f"| Probably a false alarm | {len(suspect)} |")
w(f"| Could not be checked | {len(unreadable)} |")
w(f"| No problem found | {len(clean)} |")
w("")

w("## 1. Pages missing — strong evidence")
w("")
w("The pages either side of the gap print their own numbers, and those numbers")
w("skip. This is the most reliable finding in the report: **rescan these.**")
w("")
w("| Issue | Missing printed pages | Page numbers read | Issue runs |")
w("|---|---|---|---|")
for r in sorted(gaps, key=lambda r: r["folder"]):
    w(f"| {label(r)} | **{pages(r['gaps_from_folios'])}** | "
      f"{r['folios_read']} of {r['body_sheets']} | {issue_range(r)} |")
w("")

w("## 2. Pages missing — weaker evidence")
w("")
w("Where the contents page cites a page no scan carries, **and** that citation")
w("falls inside the issue's own numbering, so it is credible without the page")
w("numbers themselves confirming it.")
w("")
if plausible:
    w("Check against the paper copy before rescanning.")
    w("")
    w("| Issue | Cited but not found | Issue runs |")
    w("|---|---|---|")
    for r in sorted(plausible, key=lambda r: r["folder"]):
        w(f"| {label(r)} | {pages(r['cited_but_absent'])} | {issue_range(r)} |")
else:
    w("**None.** Every citation-only finding fell outside its issue's numbering,")
    w("which points at the program's reading rather than at the scan. They are in")
    w("section 3.")
w("")

w("## 3. Probably a false alarm — do not rescan on this alone")
w("")
w("In each of these the contents page cites pages that fall **outside** the")
w("numbering the program worked out for the issue. When every citation lands")
w("outside, the likely fault is the program's idea of where the numbering")
w("starts, not the scan.")
w("")
w("This was confirmed by eye. **Vol 9 Number 2** is listed below as missing")
w("eleven pages. Its sheet 5 prints `—27—` and its sheet 10 prints `—32—`, so")
w("the issue runs 23 to 50 and its contents citing 31–48 is correct: **nothing")
w("is missing from it.** The program read its page numbers as 1–28 because the")
w("scans are faint and OCR could not make them out — sheet 5's `—27—` came")
w("through as `xeP=`.")
w("")
w("| Issue | Cited but not found | Program thinks the issue runs | Page numbers read |")
w("|---|---|---|---|")
for r in sorted(suspect, key=lambda r: r["folder"]):
    w(f"| {label(r)} | {pages(r['cited_but_absent'])} | {issue_range(r)} | "
      f"{r['folios_read']} of {r['body_sheets']} |")
w("")

w("## 4. Could not be checked")
w("")
w("Too few printed page numbers were readable to say anything. **These are not")
w("clean bills of health — nobody has checked them.** Verify against the paper")
w("copies, or rescan at a setting that renders the page numbers legibly.")
w("")
w("| Issue | Page numbers read | Sheets |")
w("|---|---|---|")
for r in sorted(unreadable, key=lambda r: r["folder"]):
    w(f"| {label(r)} | {r['folios_read']} of {r['body_sheets']} | {r['sheets']} |")
w("")

w("## 5. No problem found")
w("")
w(f"{len(clean)} issues where enough page numbers were read to trust the result,")
w("and they run consecutively with every cited page present.")
w("")
w("<details><summary>Show the list</summary>")
w("")
for r in sorted(clean, key=lambda r: r["folder"]):
    w(f"- {label(r)} — {r['sheets']} sheets, pages {issue_range(r)}, "
      f"{r['folios_read']} of {r['body_sheets']} page numbers read")
w("")
w("</details>")
w("")

w("## 6. Gaps in the collection itself")
w("")
w("Not about pages within an issue, but about what is not here at all.")
w("")

volumes = set()
for d in (REPO / "Image Files").iterdir():
    if d.is_dir():
        m = re.search(r"vol(?:ume)?[ _]*(\d+)", d.name, re.I)
        if m:
            volumes.add(int(m.group(1)))
present = sorted(volumes)
absent = [v for v in range(1, max(present) + 1) if v not in volumes]

w(f"**Volumes present:** {', '.join(str(v) for v in present)}")
w("")
w(f"**Volumes with no folder at all:** **{', '.join(str(v) for v in absent)}**")
w("")
w("Nothing in this report says anything about those years — there is nothing")
w("to check. They are the largest gap in the collection.")
w("")
w("**Folders that are not a single issue of scans:**")
w("")
w("| Folder | What it is |")
w("|---|---|")
w("| `SRE_1988March` | 28 single-page **PDFs**, no TIFF scans, so nothing here could check it. 1988 is Volume 17, so this is probably one of that volume's issues delivered in the wrong format. |")
w("| `SRE_index_vol1-37` | The cumulative index for volumes 1–37, not an issue. 76 scans, surveyed like an issue, so ignore its row above. |")
w("| `SRE_Vol_38` | The same 43 pages as `SRE Volume 38`, exported differently (`001.tif` rather than `SRE_2015_Vol38_No1_01.tif`). **Volume 38 was therefore checked twice**; one copy can go. |")
w("| `SRE Volume 17`–`20` | A whole year of scans in one folder, with no issue number in the file names. The numbering runs continuously, so the check still works, but these are not one issue each. |")
w("")

OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"wrote {OUT}  ({len(lines)} lines)")
print(f"gaps={len(gaps)} plausible={len(plausible)} suspect={len(suspect)} "
      f"unreadable={len(unreadable)} clean={len(clean)}")
