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
from .grid import OutlineGrid

PREVIEW_WIDTH = 300
QUALITY_CHOICES = {"Small (150 DPI)": 150, "Balanced (200 DPI)": 200,
                   "High (300 DPI)": 300}


class App(ttk.Frame):
    def __init__(self, master: tk.Misc):
        super().__init__(master, padding=10)
        self.folder: Path | None = None
        self.sheets: list[Path] = []
        self.grid_model: OutlineGrid | None = None
        self.preview_cache: dict[int, ImageTk.PhotoImage] = {}
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
        self.body_sheet_var = tk.StringVar(value="1")
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
        ttk.Label(labels, text="Printed page 1 is sheet").pack(side="left")
        ttk.Entry(labels, textvariable=self.body_sheet_var, width=5).pack(
            side="left", padx=(4, 16))
        ttk.Label(labels, text="Image quality").pack(side="left")
        ttk.Combobox(labels, textvariable=self.quality_var, width=18, state="readonly",
                     values=list(QUALITY_CHOICES)).pack(side="left", padx=4)

        # --- bookmarks + preview ---
        middle = ttk.LabelFrame(self, text="Bookmarks", padding=8)
        middle.grid(row=2, column=0, sticky="nsew")
        middle.columnconfigure(0, weight=1)
        middle.rowconfigure(0, weight=1)

        self.tree = ttk.Treeview(middle, columns=("sheet",), show="tree headings",
                                 selectmode="browse")
        self.tree.heading("#0", text="Title")
        self.tree.heading("sheet", text="Sheet")
        self.tree.column("#0", width=380)
        self.tree.column("sheet", width=60, anchor="center")
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.tree.tag_configure("attention", foreground="#a33")
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Double-1>", self._on_edit_cell)

        scroll = ttk.Scrollbar(middle, orient="vertical", command=self.tree.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scroll.set)

        self.preview = ttk.Label(middle, relief="sunken", anchor="center",
                                 text="Select a bookmark\nto see its sheet",
                                 foreground="#777", width=34)
        self.preview.grid(row=0, column=2, sticky="nsew", padx=(8, 0))

        buttons = ttk.Frame(middle)
        buttons.grid(row=1, column=0, columnspan=3, sticky="w", pady=(8, 0))
        for text, command in (("Add", self.add_row), ("Remove", self.remove_row),
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
        self._start(self._draft_worker, f"Reading {len(self.sheets)} sheets…")

    def _start(self, worker, message: str) -> None:
        self.busy = True
        self.build_button.config(state="disabled")
        self.status.config(text=message)
        self.progress.config(value=0, maximum=len(self.sheets) or 1)
        threading.Thread(target=worker, daemon=True).start()

    def _progress(self, done: int, total: int, label: str) -> None:
        self.events.put(("progress", done, total, label))

    def _draft_worker(self) -> None:
        try:
            issue = pipeline.draft(self.folder, embed_dpi=self._embed_dpi(),
                                   progress=self._progress)
            self.events.put(("drafted", issue))
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

    def _on_drafted(self, issue: Issue) -> None:
        self.busy = False
        self.title_var.set(issue.title or "")
        self.volume_var.set("" if issue.volume is None else str(issue.volume))
        self.issue_var.set("" if issue.issue is None else str(issue.issue))
        self.year_var.set("" if issue.year is None else str(issue.year))
        self.publisher_var.set(issue.publisher or "")
        self.body_sheet_var.set(str(issue.body_starts_at_sheet))

        self.grid_model = OutlineGrid(issue, sheet_count=len(self.sheets))
        self._refresh_tree()
        self.build_button.config(state="normal")

        parked = sum(1 for r in self.grid_model.rows if r.needs_review)
        self.status.config(
            text=f"{len(self.grid_model.rows)} bookmarks proposed."
                 + (f" {parked} need a sheet number." if parked else " Review and build."))

    def _on_built(self, out: Path) -> None:
        self.busy = False
        self.build_button.config(state="normal")
        size = out.stat().st_size / 1e6
        self.status.config(text=f"Built {out.name} ({size:.1f} MB)")
        messagebox.showinfo("SRE Book Builder", f"Built {out.name}\n\n{out}\n\n{size:.1f} MB")

    def _on_error(self, message: str) -> None:
        self.busy = False
        self.build_button.config(state="normal" if self.grid_model else "disabled")
        self.status.config(text="")
        messagebox.showerror("SRE Book Builder", message)

    # ----------------------------------------------------------- grid ----

    def _refresh_tree(self, select: int | None = None) -> None:
        self.tree.delete(*self.tree.get_children())
        parents: dict[int, str] = {}
        for i, row in enumerate(self.grid_model.rows):
            parent = parents.get(0, "") if row.level else ""
            node = self.tree.insert(
                parent, "end", iid=str(i), text=row.title, values=(row.sheet,),
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
            value = self._ask("Sheet number", f'Which sheet does "{row.title}" start on?',
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
        if sheet not in self.preview_cache:
            image = Image.open(self.sheets[sheet - 1]).convert("L")
            ratio = PREVIEW_WIDTH / image.width
            image = image.resize((PREVIEW_WIDTH, round(image.height * ratio)),
                                 Image.LANCZOS)
            self.preview_cache[sheet] = ImageTk.PhotoImage(image)
        self.preview.config(image=self.preview_cache[sheet], text="")

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
        sheet = self.body_sheet_var.get().strip()
        if sheet.isdigit():
            issue.body_starts_at_sheet = int(sheet)
            issue.body_starts_at_printed = 1

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
