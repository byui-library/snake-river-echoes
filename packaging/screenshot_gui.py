"""Photograph the window for the operator guide.

    py packaging/screenshot_gui.py "path\\to\\an issue folder"

Captures ONLY this program's own window, using the Windows PrintWindow API,
which asks the window to draw itself into an off-screen bitmap. It never reads
the screen, so nothing else the operator has open can end up in a picture that
goes into a document. An earlier version of this script grabbed the desktop and
captured a browser; do not reintroduce that. There is no code path here that
touches anything but our own HWND.

Writes docs/images/*.png, then regenerate the PDF with guide_to_pdf.py.
"""
from __future__ import annotations

import ctypes
import sys
import tkinter as tk
from ctypes import wintypes
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from srebook.core import ingest                       # noqa: E402
from srebook.gui.app import App                       # noqa: E402

IMAGES = ROOT / "docs" / "images"
PW_RENDERFULLCONTENT = 0x00000002
SETTLE_MS = 400


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG),
                ("biHeight", wintypes.LONG), ("biPlanes", wintypes.WORD),
                ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD),
                ("biXPelsPerMeter", wintypes.LONG),
                ("biYPelsPerMeter", wintypes.LONG),
                ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 3)]


def capture_window(hwnd: int) -> Image.Image:
    """Render one window into a bitmap. Reads no pixels from the screen."""
    user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    width, height = rect.right - rect.left, rect.bottom - rect.top

    window_dc = user32.GetWindowDC(hwnd)
    memory_dc = gdi32.CreateCompatibleDC(window_dc)
    bitmap = gdi32.CreateCompatibleBitmap(window_dc, width, height)
    gdi32.SelectObject(memory_dc, bitmap)
    try:
        if not user32.PrintWindow(hwnd, memory_dc, PW_RENDERFULLCONTENT):
            raise RuntimeError("PrintWindow refused to draw the window")

        info = BITMAPINFO()
        info.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        info.bmiHeader.biWidth = width
        info.bmiHeader.biHeight = -height          # top-down
        info.bmiHeader.biPlanes = 1
        info.bmiHeader.biBitCount = 32
        info.bmiHeader.biCompression = 0           # BI_RGB

        buffer = ctypes.create_string_buffer(width * height * 4)
        gdi32.GetDIBits(memory_dc, bitmap, 0, height, buffer,
                        ctypes.byref(info), 0)
        return Image.frombuffer("RGBA", (width, height), buffer,
                                "raw", "BGRA", 0, 1).convert("RGB")
    finally:
        gdi32.DeleteObject(bitmap)
        gdi32.DeleteDC(memory_dc)
        user32.ReleaseDC(hwnd, window_dc)


def crop_to(shot: Image.Image, hwnd: int, widget: tk.Misc,
            pad: int = 8) -> Image.Image:
    """Cut one widget out of the window's own picture."""
    rect = wintypes.RECT()
    ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
    left = widget.winfo_rootx() - rect.left - pad
    top = widget.winfo_rooty() - rect.top - pad
    return shot.crop((
        max(left, 0), max(top, 0),
        min(left + widget.winfo_width() + pad * 2, shot.width),
        min(top + widget.winfo_height() + pad * 2, shot.height),
    ))


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    folder = Path(sys.argv[1])

    root = tk.Tk()
    root.title("SRE Book Builder")
    root.geometry("980x760")
    app = App(root)

    app.sheets = ingest.find_sheets(folder)
    app.folder = folder
    app.folder_var.set(str(folder))
    app.folder_note.config(text=f"{len(app.sheets)} sheets found.")
    app.reanalyse_button.config(state="normal")
    app._start(app._draft_worker, f"Reading {len(app.sheets)} sheets…")

    IMAGES.mkdir(parents=True, exist_ok=True)

    def shoot() -> None:
        if app.busy:                       # still reading the scans
            root.after(SETTLE_MS, shoot)
            return
        if app.grid_model and app.grid_model.rows:
            app.tree.selection_set("2")    # an article, so the preview shows one
        root.update_idletasks()
        root.after(SETTLE_MS, take)

    def take() -> None:
        hwnd = int(root.wm_frame(), 16)
        shot = capture_window(hwnd)
        shot.save(IMAGES / "window.png")
        for name, widget in (("issue-panel", app.meta_frame),
                             ("bookmark-list", app.tree),
                             ("buttons", app.button_bar)):
            crop_to(shot, hwnd, widget).save(IMAGES / f"{name}.png")
            print(f"  wrote {name}.png")
        print(f"  wrote window.png  ({shot.width}x{shot.height})")
        root.destroy()

    root.after(SETTLE_MS, shoot)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
