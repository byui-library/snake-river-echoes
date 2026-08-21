# SRE Book Builder — Operator Guide

Turns a folder of scanned pages into one PDF that can be searched, and that has
a clickable list of articles down the side.

Print this and keep it by the workstation.

---

## Before you start

You need one folder containing the scans for **one issue**, and nothing else.
The files must be TIFFs, one page per file, named so they sort in reading order
— `..._01.tif`, `..._02.tif`, and so on. The first file must be the front cover.

The program never changes your scans. It only reads them.

---

## The window

![The whole window, part way through reviewing an issue.](images/window.png)

Everything happens here, top to bottom: choose the folder, check the issue
details, review the bookmarks, build.

---

## Doing an issue

**1. Open the program** — *SRE Book Builder* in the Start menu.

**2. Click Browse** and pick the issue's folder.

Reading the text starts straight away and takes about a minute for a 20-page
issue. You can fill in the issue details while it works.

**3. Check the issue details.**

![Most of this is filled in from the file names.](images/issue-panel.png)

Correct anything wrong. One setting is worth a second look:

> **Sheet ⟨1⟩ is printed page ⟨49⟩**
>
> This tells the finished PDF what page numbers to show. The program works it
> out from the numbers printed in the corners of the pages. **Check it against
> the issue in your hand.** See *Sheets and printed pages* below.

**4. Review the bookmarks.** This is the part only a person can do.

Click any bookmark to see that page on the right. Drag the divider between the
list and the page to make the page bigger, or maximise the window.

**5. Click Build PDF.**

It takes a second or two, because the text was already read in step 2. The PDF
appears in an `output` folder inside the issue's folder.

If you change a bookmark afterwards, just press Build again — it is quick.

---

## Bookmarks in red

![Black bookmarks are settled. Red ones want a decision from you.](images/bookmark-list.png)

Black entries are settled: the program found the article's heading on that page
and is confident. **Red entries want a decision.** There are two kinds, and they
need opposite things.

### "This is printed here, but the contents page never listed it"

The program found a heading printed on a page — a poem, a book list, the board
of directors — that the issue's own contents page does not mention. The page
number is right. The only question is whether it belongs in the outline.

**Keep it** with **Confirm**, or drop it with **Remove**.

### "The contents page named this, but I could not find where it starts"

The contents page lists an article, but the program could not find its heading
in the body — usually because the heading is worded differently, or the page is
a photograph it cannot read. These show a **—** instead of a page number,
because the number it has is only a placeholder.

**Give it a page number**, then confirm it.

### The buttons

![The buttons under the bookmark list.](images/buttons.png)

| Button | What it does |
|---|---|
| **Confirm** | Accepts the selected bookmark as it stands |
| **Add** | A new bookmark, for something the program missed entirely |
| **Remove** | Deletes the selected bookmark |
| **↑ ↓** | Moves a bookmark up or down the list |
| **→ Indent** | Tucks a bookmark under the one above, for poems inside a poetry section |
| **← Outdent** | Brings it back out to the top level |

**The program will not build until every red bookmark is dealt with.** That is
deliberate: a bookmark that jumps to the wrong page is worse than no bookmark,
because a reader has no way to tell.

### Finding the right page

Use the issue's own contents page. It gives a **printed page number** — the
number printed on the paper. Type that straight into the **Printed page**
column and the program works out which scan it is.

> Contents page says the article is on page **56**.
> Double-click the **Printed page** cell and type **56**.
> The Sheet column fills itself in.

You never need to do that arithmetic yourself. If you type a page the issue does
not have, it will say so rather than accept it.

Then click the bookmark and check the picture on the right really does show that
article starting. That check takes two seconds and is the whole point of the
preview.

---

## Sheets and printed pages

These are different, and the difference matters.

- **Sheet** — which scan it is. Sheet 1 is the first file, always.
- **Printed page** — the number printed on the paper in 1971.

They are often not the same. *Snake River Echoes* was paginated continuously
through each volume, so an issue can start at printed page 27, or 49, or 73. The
cover and contents pages usually carry no printed number, but they are still
counted.

If sheet 1 is printed page 49, the finished PDF shows `49 (1 of 24)` — so a
citation to page 56 takes a reader to page 56.

> **If every bookmark suddenly points past the end of the issue**, you have
> almost certainly typed printed page numbers into the **Sheet** column. Use the
> **Printed page** column instead. The program will usually spot this and say so.

---

## The other settings

**Image quality** — leave on *Balanced (200 DPI)* unless you have a reason.
*High* makes a much larger file; *Small* is for emailing. Changing it does not
mean re-reading the text, so it is cheap to try.

**Re-analyse** — reads the scans again and throws away the bookmarks currently
listed, including any you edited. Use it if you open an issue that was done some
time ago and the list looks wrong or empty. It asks before discarding anything.

---

## What you end up with

Inside the issue folder, an `output` folder containing:

| File | What it is |
|---|---|
| `..._Vol1_No3.pdf` | **The finished book.** This is the one to keep and share |
| `..._Vol1_No3.srebook.json` | Your review, saved. Keeps the PDF rebuildable later |
| `.cache` | Working files. Large, and safe to delete |

The PDF opens showing the bookmark list. Readers can search it with Ctrl-F.

---

## If something goes wrong

**"There are no page scans (.tif) in ..."**
The folder has no TIFFs, or you picked the folder above the right one.

**"... holds 24 pages in one file."**
The scans are one big TIFF rather than one file per page. Split it and try
again — the program needs a file per page so it can bookmark and number them.

**The bookmark list is nearly empty.**
Some issues set their contents page in a way the program reads poorly. Add the
bookmarks by hand with **Add**, using the contents page. The PDF is still fully
searchable either way.

**The list looks like an old, worse result.**
Opening an issue shows the review you saved last time. Click **Re-analyse** to
read the scans afresh.

**A page looks crooked or blank in the preview.**
Check the original scan. The program straightens pages automatically but cannot
fix a bad scan. A page it cannot read is still included — it just has no
searchable text on it.

**It refuses to build and lists problems.**
Each line names one bookmark and what it needs. Deal with them and press Build
again.

---

## What this program will not do

It does not check whether the bookmark titles are *correct* — only that each one
points at a real page. If the contents page has a typo, so will the bookmark,
unless you fix it.

**You are the accuracy check.** The program is a head start, not an authority.
