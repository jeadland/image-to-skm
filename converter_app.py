#!/usr/bin/env python3
"""SKP Converter — GUI app to convert images to SketchUp SKM materials."""

import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path

HERE = Path(__file__).parent.resolve()
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

try:
    import img_to_skm
except ImportError:
    messagebox.showerror("Missing file", "img_to_skm.py not found next to this script.")
    sys.exit(1)

try:
    from PIL import Image  # noqa: F401
except ImportError:
    messagebox.showerror(
        "Missing dependency",
        "Pillow is not installed.\n\nRun in Terminal:\n  pip3 install Pillow"
    )
    sys.exit(1)

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp", ".gif"}

# Preset: (label, width_in, height_in)
PRESETS = [
    ("Custom",        None,   None),
    ("1 m × 1 m",    39.37,  39.37),
    ("2 m × 2 m",    78.74,  78.74),
    ("0.5 m × 0.5 m",19.69,  19.69),
    ("1 ft × 1 ft",  12.0,   12.0),
    ("2 ft × 3 ft",  24.0,   36.0),
    ("4 ft × 6 ft",  48.0,   72.0),
    ("5 ft × 8 ft",  60.0,   96.0),
    ("6 ft × 9 ft",  72.0,   108.0),
    ("8 ft × 10 ft", 96.0,   120.0),
]


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("SKP Converter")
        self.resizable(False, False)
        self._build_ui()
        self._center()
        self.after(100, self._activate)

    def _center(self):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

    def _activate(self):
        """Bring the window to the front on macOS."""
        # PyObjC: register as foreground app so macOS shows the dock icon
        # and allows window focus
        try:
            from AppKit import NSApplication, NSApp  # type: ignore[import]
            NSApplication.sharedApplication()
            NSApp.activateIgnoringOtherApps_(True)
        except ImportError:
            pass
        # Tk: force the window to the top, then relax
        self.attributes("-topmost", True)
        self.lift()
        self.focus_force()
        self.after(300, lambda: self.attributes("-topmost", False))

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        P = 16  # padding

        # Configure ttk style — stay native/light, just tune spacing
        style = ttk.Style(self)
        style.theme_use("aqua")  # native macOS look

        outer = ttk.Frame(self, padding=P)
        outer.pack(fill="both", expand=True)

        # ── Source files ─────────────────────────────────────────────
        ttk.Label(outer, text="Source Images", font=("SF Pro Text", 12, "bold")).pack(anchor="w")

        list_frame = ttk.Frame(outer)
        list_frame.pack(fill="x", pady=(4, 0))

        sb = ttk.Scrollbar(list_frame, orient="vertical")
        self.file_list = tk.Listbox(
            list_frame, height=5, selectmode="extended",
            font=("SF Mono", 11),
            yscrollcommand=sb.set,
            relief="solid", borderwidth=1
        )
        sb.config(command=self.file_list.yview)
        self.file_list.pack(side="left", fill="x", expand=True)
        sb.pack(side="right", fill="y")

        btn_row = ttk.Frame(outer)
        btn_row.pack(fill="x", pady=(6, 0))
        ttk.Button(btn_row, text="Add Files…",       command=self._add_files).pack(side="left")
        ttk.Button(btn_row, text="Remove Selected",  command=self._remove_selected).pack(side="left", padx=(6, 0))
        ttk.Button(btn_row, text="Clear All",        command=self._clear_files).pack(side="left", padx=(6, 0))

        ttk.Separator(outer, orient="horizontal").pack(fill="x", pady=12)

        # ── Output ───────────────────────────────────────────────────
        ttk.Label(outer, text="Output Folder", font=("SF Pro Text", 12, "bold")).pack(anchor="w")

        self.output_mode = tk.StringVar(value="same")

        ttk.Radiobutton(outer, text="Same folder as source image",
                        variable=self.output_mode, value="same",
                        command=self._on_output_mode).pack(anchor="w", pady=(4, 0))

        custom_row = ttk.Frame(outer)
        custom_row.pack(fill="x", pady=(4, 0))
        ttk.Radiobutton(custom_row, text="Custom folder:",
                        variable=self.output_mode, value="custom",
                        command=self._on_output_mode).pack(side="left")

        self.output_path_var = tk.StringVar()
        self.output_entry = ttk.Entry(custom_row, textvariable=self.output_path_var,
                                      width=30, state="disabled")
        self.output_entry.pack(side="left", padx=(6, 6))
        self.browse_btn = ttk.Button(custom_row, text="Browse…",
                                     command=self._browse_output, state="disabled")
        self.browse_btn.pack(side="left")

        ttk.Separator(outer, orient="horizontal").pack(fill="x", pady=12)

        # ── Options ──────────────────────────────────────────────────
        ttk.Label(outer, text="Texture Tile Size", font=("SF Pro Text", 12, "bold")).pack(anchor="w")

        preset_row = ttk.Frame(outer)
        preset_row.pack(fill="x", pady=(6, 0))
        ttk.Label(preset_row, text="Preset:").pack(side="left")
        self.preset_var = tk.StringVar(value=PRESETS[1][0])
        preset_cb = ttk.Combobox(preset_row, textvariable=self.preset_var,
                                  values=[p[0] for p in PRESETS],
                                  state="readonly", width=18)
        preset_cb.pack(side="left", padx=(6, 0))
        preset_cb.bind("<<ComboboxSelected>>", self._on_preset)

        dim_row = ttk.Frame(outer)
        dim_row.pack(fill="x", pady=(8, 0))

        ttk.Label(dim_row, text="Width:").pack(side="left")
        self.width_var = tk.StringVar(value="39.37")
        ttk.Entry(dim_row, textvariable=self.width_var, width=8).pack(side="left", padx=(4, 2))
        ttk.Label(dim_row, text='in').pack(side="left")

        ttk.Label(dim_row, text="   Height:").pack(side="left")
        self.height_var = tk.StringVar(value="39.37")
        ttk.Entry(dim_row, textvariable=self.height_var, width=8).pack(side="left", padx=(4, 2))
        ttk.Label(dim_row, text='in').pack(side="left")

        ttk.Separator(outer, orient="horizontal").pack(fill="x", pady=12)

        # ── Convert ──────────────────────────────────────────────────
        self.convert_btn = ttk.Button(outer, text="Convert", command=self._convert)
        self.convert_btn.pack()

        ttk.Separator(outer, orient="horizontal").pack(fill="x", pady=12)

        # ── Results ──────────────────────────────────────────────────
        ttk.Label(outer, text="Results", font=("SF Pro Text", 12, "bold")).pack(anchor="w")

        log_frame = ttk.Frame(outer)
        log_frame.pack(fill="x", pady=(4, 0))
        log_sb = ttk.Scrollbar(log_frame, orient="vertical")
        self.log = tk.Text(log_frame, height=5, state="disabled",
                           font=("SF Mono", 11), wrap="none",
                           relief="solid", borderwidth=1,
                           yscrollcommand=log_sb.set)
        log_sb.config(command=self.log.yview)
        self.log.pack(side="left", fill="x", expand=True)
        log_sb.pack(side="right", fill="y")

        self.log.tag_config("ok",  foreground="#1a7f37")
        self.log.tag_config("err", foreground="#cf222e")

        self.status_var = tk.StringVar(value="Add images to get started.")
        ttk.Label(outer, textvariable=self.status_var,
                  foreground="gray").pack(anchor="w", pady=(8, 0))

    # ------------------------------------------------------------------
    # Interactions
    # ------------------------------------------------------------------

    def _add_files(self):
        paths = filedialog.askopenfilenames(
            title="Select Images",
            filetypes=[("Images", " ".join(f"*{e}" for e in IMAGE_EXTENSIONS)),
                       ("All files", "*.*")]
        )
        existing = set(self.file_list.get(0, "end"))
        for p in paths:
            if p not in existing:
                self.file_list.insert("end", p)
        self._update_status()

    def _remove_selected(self):
        for i in reversed(self.file_list.curselection()):
            self.file_list.delete(i)
        self._update_status()

    def _clear_files(self):
        self.file_list.delete(0, "end")
        self._update_status()

    def _on_output_mode(self):
        custom = self.output_mode.get() == "custom"
        self.output_entry.config(state="normal" if custom else "disabled")
        self.browse_btn.config(state="normal" if custom else "disabled")

    def _browse_output(self):
        d = filedialog.askdirectory(title="Select Output Folder")
        if d:
            self.output_path_var.set(d)

    def _on_preset(self, _=None):
        label = self.preset_var.get()
        for name, w, h in PRESETS:
            if name == label and w is not None:
                self.width_var.set(f"{w:.4g}")
                self.height_var.set(f"{h:.4g}")
                return

    def _update_status(self):
        n = self.file_list.size()
        self.status_var.set(
            f"{n} image{'s' if n != 1 else ''} queued." if n else "Add images to get started."
        )

    # ------------------------------------------------------------------
    # Conversion
    # ------------------------------------------------------------------

    def _resolve_output(self, src: Path) -> Path:
        if self.output_mode.get() == "same":
            return src.parent
        custom = self.output_path_var.get().strip()
        if not custom:
            raise ValueError("Please select an output folder.")
        out = Path(custom)
        out.mkdir(parents=True, exist_ok=True)
        return out

    def _convert(self):
        files = list(self.file_list.get(0, "end"))
        if not files:
            messagebox.showwarning("No files", "Add at least one image first.")
            return

        try:
            w_in = float(self.width_var.get())
            h_in = float(self.height_var.get())
            if w_in <= 0 or h_in <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid size", "Width and Height must be positive numbers.")
            return

        self.convert_btn.config(state="disabled")
        self._log_clear()
        self.status_var.set("Converting…")

        def run():
            ok = err = 0
            for path_str in files:
                src = Path(path_str)
                try:
                    out_dir = self._resolve_output(src)
                    skm = img_to_skm.convert(
                        str(src), x_scale=w_in, y_scale=h_in,
                        output_dir=str(out_dir)
                    )
                    self._log(f"✓  {src.name}  →  {Path(skm).name}\n", "ok")
                    ok += 1
                except Exception as e:
                    self._log(f"✗  {src.name}: {e}\n", "err")
                    err += 1

            summary = f"Done — {ok} converted"
            if err:
                summary += f", {err} failed"
            self.after(0, lambda: self._finish(summary))

        threading.Thread(target=run, daemon=True).start()

    def _finish(self, summary):
        self.convert_btn.config(state="normal")
        self.status_var.set(summary)

    def _log(self, msg, tag=""):
        self.after(0, lambda: self._log_write(msg, tag))

    def _log_write(self, msg, tag):
        self.log.config(state="normal")
        self.log.insert("end", msg, tag)
        self.log.see("end")
        self.log.config(state="disabled")

    def _log_clear(self):
        self.log.config(state="normal")
        self.log.delete("1.0", "end")
        self.log.config(state="disabled")


if __name__ == "__main__":
    app = App()
    app.mainloop()
