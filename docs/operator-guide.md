# SRE Book Builder — Operator Guide

Turns a folder of scanned pages into one PDF that can be searched, and that has
a clickable list of articles down the side.

Print this and keep it by the workstation.

---

## Before you start

You need one folder containing the scans for **one issue**, and nothing else.
The files must be TIFFs, named so they sort in reading order — `..._01.tif`,
`..._02.tif`, and so on. The first file must be the front cover.

The program never changes your scans. It only reads them.

---

## Doing an issue

**1. Open the program** — *SRE Book Builder* in the Start menu.

**2. Click Browse** and pick the issue's folder.

Reading the text starts straight away and takes about a minute for a 20-page
issue. You can fill in the issue details while it works.

**3. Check the issue details.**

Most of these are filled in for you from the file names. Correct anything wrong.

> **Sheet ⟨1⟩ is printed page ⟨27⟩**
>
> This is the one worth a second look. It tells the PDF what page numbers to
> show. See *Sheets and printed pages* below.

**4. Review the bookmarks.** This is the part only a person can do.

Click any bookmark to see that page on the right. Drag the divider to make the
page bigger, or maximise the window.

**5. Click Build PDF.**

It takes a second or two, because the text was already read in step 2. The PDF
appears in an `output` folder inside the issue's folder.

If you change a bookmark afterwards, just press Build again — it is quick.

---

## Bookmarks in red, and the dash

A bookmark shown **in red** with a **—** in the Sheet column means:

> *The program found this title on the contents page, but could not find where
> the article actually starts.*

This is normal. It happens when the article's heading is worded differently from
the contents page, or when the page is a photograph the program cannot read.

You have three choices. Select the bookmark, then:

| If | Do this |
|---|---|
| The page shown is right | Click **Confirm** |
| It should point somewhere else | Double-click **Printed page** and type the number from the contents page |
| It should not be a bookmark at all | Click **Remove** |

If every bookmark suddenly points past the end of the issue, you have almost
certainly typed printed page numbers into the **Sheet** column. Use the
**Printed page** column instead — the program will tell you if it spots this.

**The program will not build until every red bookmark is dealt with.** That is
deliberate: a bookmark that jumps to the wrong page is worse than no bookmark,
because a reader has no way to tell.

### Finding the right page

Use the issue's own contents page. It gives a **printed page number** — the
number printed on the paper. Type that straight into the **Printed page**
column and the program works out the sheet for you.

> Contents page says the article is on **page 33**.
> Double-click the **Printed page** column, type **33**.
> The Sheet column fills itself in.

You never need to do that arithmetic yourself. If you type a page the issue
does not have, it will say so rather than accept it.

Then click the bookmark and check the picture on the right actually shows that
article starting. That check takes two seconds and is the whole point of the
preview.

---

## Sheets and printed pages

These are different, and the difference matters.

- **Sheet** — which scan it is. Sheet 1 is the first file, always.
- **Printed page** — the number printed on the paper in 1971.

They are often not the same. *Snake River Echoes* was paginated continuously
through each volume, so an issue can start at printed page 27 or 49 or 73. The
cover and contents pages usually carry no printed number at all, but they are
still counted.

The program works this out from the page numbers printed in the corners and
fills the setting in. **Check it against the issue in your hand.** If sheet 1 is
printed page 27, the finished PDF will show `27 (1 of 20)` — so a citation to
page 33 takes a reader to page 33.

---

## The other settings

**Image quality** — leave on *Balanced (200 DPI)* unless you have a reason.
*High* makes a much larger file; *Small* is for emailing. Changing it does not
mean re-reading the text, so it is cheap to try.

**Re-analyse** — reads the scans again and throws away the bookmarks currently
listed, including any you edited. Use it if you opened an issue that was done
some time ago and the list looks wrong or empty. It will ask before discarding
anything.

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

**The bookmark list is nearly empty.**
Some issues set their contents page in a way the program reads poorly. Add the
bookmarks by hand with **Add**, using the contents page and the conversion
above. The PDF is still fully searchable either way.

**A page looks crooked or blank in the preview.**
Check the original scan. The program straightens pages automatically but cannot
fix a bad scan. A page it cannot read is still included — it just has no
searchable text.

**It refuses to build and lists problems.**
Each line names one bookmark and what it needs. Deal with them and press Build
again.

---

## What this program will not do

It does not check whether the bookmark titles are *correct* — only that each one
points at a real sheet. If the contents page has a typo, so will the bookmark,
unless you fix it.

**You are the accuracy check.** The program is a head start, not an authority.
