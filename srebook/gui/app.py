"""The window.

Deliberately thin: the rules live in grid.py and srebook.core, both of which are
tested without a display. What is here is wiring, threading and layout.

One linear path -- pick a folder, fill in the issue, review the bookmarks, build
-- because archive staff should not need training or a manual.
"""
from __future__ import annotations

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

from ..core import ingest, pipeline
from ..core.model import Issue
from . import preview
from .grid import OutlineGrid

PREVIEW_MARGIN = 8        # breathing room inside the sunken border
MIN_PREVIEW = 40          # below this the pane is not laid out yet
RESIZE_SETTLE_MS = 120    # re-render after dragging stops, not during
QUALITY_CHOICES = {"Small (150 DPI)": 150, "Balanced (200 DPI)": 200,
                   "High (300 DPI)": 300}


class App(ttk.Frame):
    def __init__(self, master: tk.Misc):
        super().__init__(master, padding=10)
        self.folder: Path | None = None
        self.sheets: list[Path] = []
        self.grid_model: OutlineGrid | None = None
        self.preview_cache: dict[tuple[int, tuple[int, int]], ImageTk.PhotoImage] = {}
        self.events: queue.Queue = queue.Queue()
        self.busy = False

        self.pack(fill="both", expand=True)
        self._build_widgets()
        self.after(100, self._drain_events)

    # --------------------------------------------------------- layout ----

    def _build_widgets(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        # --- folder ---
        top = ttk.Frame(self)
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(1, weight=1)
        ttk.Label(top, text="Issue folder").grid(row=0, column=0, sticky="w")
        self.folder_var = tk.StringVar()
        ttk.Entry(top, textvariable=self.folder_var, state="readonly").grid(
            row=0, column=1, sticky="ew", padx=6)
        ttk.Button(top, text="Browse…", command=self.choose_folder).grid(row=0, column=2)
        # draft() returns a saved review when one exists, so without this the
        # window would show a stale result forever with no way to re-run.
        self.reanalyse_button = ttk.Button(top, text="Re-analyse",
                                           command=self.reanalyse, state="disabled")
        self.reanalyse_button.grid(row=0, column=3, padx=(4, 0))
        self.folder_note = ttk.Label(top, text="Choose a folder of TIFF page scans.",
                                     foreground="#555")
        self.folder_note.grid(row=1, column=1, sticky="w", padx=6, pady=(2, 8))

        # --- metadata ---
        meta = ttk.LabelFrame(self, text="Issue", padding=8)
        meta.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        meta.columnconfigure(1, weight=1)

        self.title_var = tk.StringVar()
        self.volume_var = tk.StringVar()
        self.issue_var = tk.StringVar()
        self.year_var = tk.StringVar()
        self.publisher_var = tk.StringVar()
        self.label_sheet_var = tk.StringVar(value="1")
        self.label_printed_var = tk.StringVar(value="1")
        self.quality_var = tk.StringVar(value="Balanced (200 DPI)")

        ttk.Label(meta, text="Title").grid(row=0, column=0, sticky="w")
        ttk.Entry(meta, textvariable=self.title_var).grid(
            row=0, column=1, columnspan=3, sticky="ew", padx=6)

        numbers = ttk.Frame(meta)
        numbers.grid(row=1, column=0, columnspan=4, sticky="w", pady=(6, 0))
        for label, var, width in (("Volume", self.volume_var, 5),
                                  ("Issue", self.issue_var, 5),
                                  ("Year", self.year_var, 7)):
            ttk.Label(numbers, text=label).pack(side="left")
            ttk.Entry(numbers, textvariable=var, width=width).pack(side="left", padx=(4, 12))

        ttk.Label(meta, text="Publisher").grid(row=2, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(meta, textvariable=self.publisher_var).grid(
            row=2, column=1, columnspan=3, sticky="ew", padx=6, pady=(6, 0))

        labels = ttk.Frame(meta)
        labels.grid(row=3, column=0, columnspan=4, sticky="w", pady=(8, 0))
        # Two fields, because one cannot express a volume paginated
        # continuously: Vol 1 No 2 runs pages 27-46, and "printed page 1 is
        # sheet N" silently relabelled the whole issue 1, 2, 3...
        ttk.Label(labels, text="Sheet").pack(side="left")
        ttk.Entry(labels, textvariable=self.label_sheet_var, width=4).pack(
            side="left", padx=4)
        ttk.Label(labels, text="is printed page").pack(side="left")
        ttk.Entry(labels, textvariable=self.label_printed_var, width=5).pack(
            side="left", padx=(4, 16))
        ttk.Label(labels, text="Image quality").pack(side="left")
        ttk.Combobox(labels, textvariable=self.quality_var, width=18, state="readonly",
                     values=list(QUALITY_CHOICES)).pack(side="left", padx=4)

        # --- bookmarks + preview ---
        middle = ttk.LabelFrame(self, text="Bookmarks", padding=8)
        middle.grid(row=2, column=0, sticky="nsew")
        middle.columnconfigure(0, weight=1)
        middle.rowconfigure(0, weight=1)

        # A draggable split: the operator decides how much room the list and
        # the page image each get. A fixed-width preview was too small to read,
        # which defeats its purpose -- it is there to confirm that an article
        # really starts on the sheet a bookmark claims.
        self.split = ttk.PanedWindow(middle, orient="horizontal")
        self.split.grid(row=0, column=0, columnspan=3, sticky="nsew")

        list_pane = ttk.Frame(self.split)
        list_pane.columnconfigure(0, weight=1)
        list_pane.rowconfigure(0, weight=1)
        self.split.add(list_pane, weight=1)

        # Printed page first: it is the number the contents page gives, and
        # asking an operator to convert it to a sheet by hand once put an entire
        # issue's bookmarks past the end of the book.
        self.tree = ttk.Treeview(list_pane, columns=("printed", "sheet"),
                                 show="tree headings", selectmode="browse")
        self.tree.heading("#0", text="Title")
        self.tree.heading("printed", text="Printed page")
        self.tree.heading("sheet", text="Sheet")
        self.tree.column("#0", width=300, minwidth=120)
        self.tree.column("printed", width=88, minwidth=70, anchor="center")
        self.tree.column("sheet", width=58, minwidth=50, anchor="center")
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.tree.tag_configure("attention", foreground="#a33")
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Double-1>", self._on_edit_cell)

        scroll = ttk.Scrollbar(list_pane, orient="vertical", command=self.tree.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scroll.set)

        preview_pane = ttk.Frame(self.split)
        preview_pane.columnconfigure(0, weight=1)
        preview_pane.rowconfigure(0, weight=1)
        self.split.add(preview_pane, weight=2)

        self.preview = ttk.Label(preview_pane, relief="sunken", anchor="center",
                                 text="Select a bookmark\nto see its sheet",
                                 foreground="#777")
        self.preview.grid(row=0, column=0, sticky="nsew")
        # Re-render when the pane changes size, so dragging the split or
        # maximising the window actually enlarges the page.
        self.preview.bind("<Configure>", self._on_preview_resized)

        buttons = ttk.Frame(middle)
        buttons.grid(row=1, column=0, columnspan=3, sticky="w", pady=(8, 0))
        for text, command in (("Confirm", self.confirm_row),
                              ("Add", self.add_row), ("Remove", self.remove_row),
                              ("↑", self.move_up), ("↓", self.move_down),
                              ("→ Indent", self.indent), ("← Outdent", self.outdent)):
            ttk.Button(buttons, text=text, command=command, width=9).pack(
                side="left", padx=(0, 4))

        # --- status + build ---
        bottom = ttk.Frame(self)
        bottom.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        bottom.columnconfigure(1, weight=1)
        self.progress = ttk.Progressbar(bottom, mode="determinate", length=220)
        self.progress.grid(row=0, column=0, sticky="w")
        self.status = ttk.Label(bottom, text="")
        self.status.grid(row=0, column=1, sticky="w", padx=10)
        self.build_button = ttk.Button(bottom, text="Build PDF", command=self.build,
                                       state="disabled")
        self.build_button.grid(row=0, column=2, sticky="e")

    # ---------------------------------------------------- folder + OCR ----

    def choose_folder(self) -> None:
        chosen = filedialog.askdirectory(title="Choose the folder of page scans")
        if not chosen:
            return
        folder = Path(chosen)
        try:
            self.sheets = ingest.find_sheets(folder)
        except ingest.IngestError as exc:
            messagebox.showerror("SRE Book Builder", str(exc))
            return
        if not self.sheets:
            messagebox.showerror(
                "SRE Book Builder",
                f"There are no page scans (.tif) in {folder.name}.")
            return

        self.folder = folder
        self.folder_var.set(str(folder))
        self.folder_note.config(text=f"{len(self.sheets)} sheets found.")
        self.preview_cache.clear()
        self.reanalyse_button.config(state="normal")
        self._start(self._draft_worker, f"Reading {len(self.sheets)} sheets…")

    def _start(self, worker, message: str) -> None:
        self.busy = True
        self.build_button.config(state="disabled")
        self.reanalyse_button.config(state="disabled")
        self.status.config(text=message)
        self.progress.config(value=0, maximum=len(self.sheets) or 1)
        threading.Thread(target=worker, daemon=True).start()

    def _progress(self, done: int, total: int, label: str) -> None:
        self.events.put(("progress", done, total, label))

    def reanalyse(self) -> None:
        """Re-run the analysis, discarding the saved review.

        Offered explicitly because the saved review normally wins -- that is
        what stops a re-open from throwing away an operator's work.
        """
        if not self.folder or self.busy:
            return
        if self.grid_model and self.grid_model.rows:
            if not messagebox.askyesno(
                "SRE Book Builder",
                "Re-analyse this issue from the scans?\n\n"
                "The bookmarks currently listed, including any you have edited, "
                "will be replaced."):
                return
        self._overwrite = True
        self._start(self._draft_worker, "Re-analysing…")

    def _draft_worker(self) -> None:
        overwrite = getattr(self, "_overwrite", False)
        self._overwrite = False
        try:
            saved = pipeline.sidecar_path(self.folder).exists() and not overwrite
            issue = pipeline.draft(self.folder, embed_dpi=self._embed_dpi(),
                                   overwrite=overwrite, progress=self._progress)
            self.events.put(("drafted", issue, not saved))
        except Exception as exc:  # surfaced as a sentence, not a traceback
            self.events.put(("error", str(exc)))

    def _build_worker(self) -> None:
        try:
            out = pipeline.build(self.folder, progress=self._progress)
            self.events.put(("built", out))
        except Exception as exc:
            self.events.put(("error", str(exc)))

    def _drain_events(self) -> None:
        try:
            while True:
                event = self.events.get_nowait()
                getattr(self, f"_on_{event[0]}")(*event[1:])
        except queue.Empty:
            pass
        self.after(100, self._drain_events)

    def _on_progress(self, done: int, total: int, label: str) -> None:
        self.progress.config(value=done, maximum=total)
        self.status.config(text=f"Reading text {min(done + 1, total)} of {total}"
                                if done < total else "Text read.")

    def _on_drafted(self, issue: Issue, fresh: bool = True) -> None:
        self.busy = False
        self.title_var.set(issue.title or "")
        self.volume_var.set("" if issue.volume is None else str(issue.volume))
        self.issue_var.set("" if issue.issue is None else str(issue.issue))
        self.year_var.set("" if issue.year is None else str(issue.year))
        self.publisher_var.set(issue.publisher or "")
        self.label_sheet_var.set(str(issue.body_starts_at_sheet))
        self.label_printed_var.set(str(issue.body_starts_at_printed))

        self.grid_model = OutlineGrid(issue, sheet_count=len(self.sheets))
        self._refresh_tree()
        self.build_button.config(state="normal")

        self.reanalyse_button.config(state="normal")
        # Two different jobs. Saying "n need a sheet number" about a heading we
        # read off its own page is simply wrong, and sends the operator looking
        # for a number instead of making a decision.
        unplaced = sum(1 for r in self.grid_model.rows
                       if r.needs_review and r.review_reason != "suggested")
        suggested = sum(1 for r in self.grid_model.rows
                        if r.needs_review and r.review_reason == "suggested")
        count = len(self.grid_model.rows)
        if fresh:
            lead = f"{count} bookmarks proposed."
        else:
            # Say so, or an old one-bookmark result looks like a failed analysis.
            lead = (f"Loaded your saved review ({count} bookmarks). "
                    "Use Re-analyse to read the scans again.")
        notes = []
        if unplaced:
            notes.append(f"{unplaced} need a page number")
        if suggested:
            notes.append(f"{suggested} to keep or remove")
        self.status.config(text=lead + (" " + ", ".join(notes) + "." if notes else ""))

        # A scan missing pages is worth interrupting for: otherwise the operator
        # hunts for articles that were never scanned, and may publish an issue
        # believing it complete.
        if fresh and issue.missing_pages:
            pages = ", ".join(str(p) for p in issue.missing_pages)
            messagebox.showwarning(
                "SRE Book Builder",
                f"The contents page refers to printed page(s) {pages}, which no "
                "scan in this folder carries.\n\n"
                "Pages were probably missed at the scanner. Check the issue "
                "against the paper copy before publishing.")

    def _on_built(self, out: Path) -> None:
        self.busy = False
        self.build_button.config(state="normal")
        self.reanalyse_button.config(state="normal")
        size = out.stat().st_size / 1e6
        self.status.config(text=f"Built {out.name} ({size:.1f} MB)")
        messagebox.showinfo("SRE Book Builder", f"Built {out.name}\n\n{out}\n\n{size:.1f} MB")

    def _on_error(self, message: str) -> None:
        self.busy = False
        self.build_button.config(state="normal" if self.grid_model else "disabled")
        self.reanalyse_button.config(state="normal" if self.folder else "disabled")
        self.status.config(text="")
        messagebox.showerror("SRE Book Builder", message)

    # ----------------------------------------------------------- grid ----

    def _refresh_tree(self, select: int | None = None) -> None:
        self.tree.delete(*self.tree.get_children())
        parents: dict[int, str] = {}
        for i, row in enumerate(self.grid_model.rows):
            parent = parents.get(0, "") if row.level else ""
            node = self.tree.insert(
                parent, "end", iid=str(i), text=row.title,
                values=(self.grid_model.printed_display(i),
                        self.grid_model.sheet_display(i)),
                open=True,
                tags=("attention",) if self.grid_model.needs_attention(i) else (),
            )
            if row.level == 0:
                parents[0] = node
        if select is not None and self.grid_model.rows:
            iid = str(min(select, len(self.grid_model.rows) - 1))
            self.tree.selection_set(iid)
            self.tree.see(iid)

    def _selected(self) -> int | None:
        selection = self.tree.selection()
        return int(selection[0]) if selection else None

    def confirm_row(self) -> None:
        """Accept the selected bookmark's sheet as correct."""
        index = self._selected()
        if index is None or not self.grid_model:
            return
        self.grid_model.confirm(index)
        self._refresh_tree(index)
        self._autosave()
        remaining = sum(1 for r in self.grid_model.rows if r.needs_review)
        self.status.config(
            text=f"{remaining} bookmark(s) still to check."
            if remaining else "All bookmarks confirmed. Ready to build.")

    def add_row(self) -> None:
        if not self.grid_model:
            return
        self._refresh_tree(self.grid_model.add(title="New bookmark", sheet=1))
        self._autosave()

    def remove_row(self) -> None:
        index = self._selected()
        if index is None:
            return
        self.grid_model.remove(index)
        self._refresh_tree(index)
        self._autosave()

    def _apply(self, action) -> None:
        index = self._selected()
        if index is None:
            return
        result = action(index)
        self._refresh_tree(result if isinstance(result, int) else index)
        self._autosave()

    def move_up(self):
        self._apply(self.grid_model.move_up) if self.grid_model else None

    def move_down(self):
        self._apply(self.grid_model.move_down) if self.grid_model else None

    def indent(self):
        self._apply(self.grid_model.indent) if self.grid_model else None

    def outdent(self):
        self._apply(self.grid_model.outdent) if self.grid_model else None

    def _on_edit_cell(self, event) -> None:
        index = self._selected()
        if index is None:
            return
        column = self.tree.identify_column(event.x)
        row = self.grid_model.rows[index]
        if column == "#1":
            value = self._ask(
                "Printed page",
                f'What page number is printed on the page where "{row.title}"\n'
                "starts? This is the number the contents page gives.",
                self.grid_model.printed_display(index).replace("—", ""))
            if value and value.isdigit():
                if not self.grid_model.set_printed(index, int(value)):
                    messagebox.showerror(
                        "SRE Book Builder",
                        f"This issue does not have a printed page {value}.\n\n"
                        f"It has {len(self.sheets)} sheets. Check the "
                        "'Sheet is printed page' setting above the list.")
        elif column == "#2":
            value = self._ask("Sheet number", f'Which scan does "{row.title}" start on?',
                              str(row.sheet))
            if value and value.isdigit():
                self.grid_model.edit(index, sheet=int(value))
        else:
            value = self._ask("Bookmark title", "Title", row.title)
            if value is not None:
                self.grid_model.edit(index, title=value)
        self._refresh_tree(index)
        self._autosave()

    def _ask(self, title: str, prompt: str, initial: str) -> str | None:
        from tkinter import simpledialog
        return simpledialog.askstring(title, prompt, initialvalue=initial, parent=self)

    # -------------------------------------------------------- preview ----

    def _on_select(self, _event) -> None:
        index = self._selected()
        if index is None or not self.sheets:
            return
        sheet = self.grid_model.rows[index].sheet
        if not 1 <= sheet <= len(self.sheets):
            self.preview.config(image="", text=f"Sheet {sheet} does not exist")
            return
        self._show_sheet(sheet)

    def _show_sheet(self, sheet: int) -> None:
        box = (self.preview.winfo_width() - PREVIEW_MARGIN,
               self.preview.winfo_height() - PREVIEW_MARGIN)
        if box[0] < MIN_PREVIEW or box[1] < MIN_PREVIEW:
            # The pane has not been laid out yet; try again once it has.
            self.after(60, lambda: self._show_sheet(sheet))
            return

        source = Image.open(self.sheets[sheet - 1])
        size = preview.fit_within(source.size, box)
        key = (sheet, size)
        if key not in self.preview_cache:
            self.preview_cache.clear()   # one page at a time; these are large
            image = source.convert("L").resize(size, Image.LANCZOS)
            self.preview_cache[key] = ImageTk.PhotoImage(image)
        self._shown_sheet = sheet
        self.preview.config(image=self.preview_cache[key], text="")

    def _on_preview_resized(self, _event) -> None:
        """Re-render at the new size, once the operator stops dragging."""
        sheet = getattr(self, "_shown_sheet", None)
        if sheet is None:
            return
        if getattr(self, "_resize_job", None):
            self.after_cancel(self._resize_job)
        self._resize_job = self.after(RESIZE_SETTLE_MS,
                                      lambda: self._show_sheet(sheet))

    # ------------------------------------------------------ build/save ----

    def _embed_dpi(self) -> int:
        return QUALITY_CHOICES.get(self.quality_var.get(), 200)

    def _collect_metadata(self) -> None:
        issue = self.grid_model.issue
        issue.title = self.title_var.get().strip()
        issue.publisher = self.publisher_var.get().strip()
        issue.embed_dpi = self._embed_dpi()
        for attr, var in (("volume", self.volume_var), ("issue", self.issue_var),
                          ("year", self.year_var)):
            text = var.get().strip()
            setattr(issue, attr, int(text) if text.isdigit() else None)
        sheet = self.label_sheet_var.get().strip()
        printed = self.label_printed_var.get().strip()
        if sheet.isdigit():
            issue.body_starts_at_sheet = int(sheet)
        if printed.isdigit():
            issue.body_starts_at_printed = int(printed)

    def _autosave(self) -> None:
        if not (self.grid_model and self.folder):
            return
        self._collect_metadata()
        self.grid_model.save(pipeline.sidecar_path(self.folder))

    def build(self) -> None:
        if not (self.grid_model and self.folder) or self.busy:
            return
        self._autosave()
        problems = self.grid_model.problems()
        if problems:
            messagebox.showerror("SRE Book Builder", "\n\n".join(problems))
            return
        self._start(self._build_worker, "Building…")


def main() -> int:
    root = tk.Tk()
    root.title("SRE Book Builder")
    root.geometry("980x760")
    root.minsize(820, 620)
    try:
        ttk.Style().theme_use("vista")  # native Windows look
    except tk.TclError:
        pass
    App(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
