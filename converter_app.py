#!/usr/bin/env python3
"""SKP Converter — GUI app to convert images to SketchUp SKM materials."""

import json
import subprocess
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

# Unit label → multiplier to convert FROM that unit TO inches
UNITS_TO_INCHES = {
    "in":  1.0,
    "cm":  1 / 2.54,
    "ft":  12.0,
    "m":   39.3701,
}

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


PREFS_PATH = Path.home() / ".skp_converter_prefs.json"


def _load_prefs() -> dict:
    try:
        return json.loads(PREFS_PATH.read_text())
    except Exception:
        return {}


def _save_prefs(prefs: dict) -> None:
    try:
        PREFS_PATH.write_text(json.dumps(prefs, indent=2))
    except Exception:
        pass


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Image to SKM Converter for SketchUp")
        self.resizable(False, False)
        self._preview_photo = None  # keep reference to prevent GC
        self._last_output_dir = None  # track for Reveal in Finder
        self._build_ui()
        self._load_saved_prefs()
        self._center()
        self.after(100, self._activate)
        self.protocol("WM_DELETE_WINDOW", self._on_quit)

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
        PREVIEW_SIZE = 200

        # Configure ttk style — stay native/light, just tune spacing
        style = ttk.Style(self)
        style.theme_use("aqua")  # native macOS look

        outer = ttk.Frame(self, padding=P)
        outer.pack(fill="both", expand=True)

        # ── App heading + supported formats ────────────────────────
        ttk.Label(outer, text="Image to SKM Converter for SketchUp",
                  font=("SF Pro Text", 15, "bold")).pack(anchor="w")
        formats = ", ".join(sorted(ext.lstrip(".").upper() for ext in IMAGE_EXTENSIONS))
        ttk.Label(outer, text=f"Supported formats: {formats}",
                  font=("SF Pro Text", 11), foreground="gray").pack(anchor="w", pady=(2, 10))

        # ── Top area: left controls + right preview ────────────────
        top = ttk.Frame(outer)
        top.pack(fill="x")

        left = ttk.Frame(top)
        left.pack(side="left", fill="both", expand=True)

        # ── Preview panel (right side) ─────────────────────────────
        preview_frame = ttk.LabelFrame(top, text="Preview", padding=4)
        preview_frame.pack(side="right", padx=(16, 0), anchor="n")

        self.preview_canvas = tk.Canvas(
            preview_frame, width=PREVIEW_SIZE, height=PREVIEW_SIZE,
            bg="#f0f0f0", highlightthickness=1, highlightbackground="#c0c0c0"
        )
        self.preview_canvas.pack()
        self.preview_canvas.create_text(
            PREVIEW_SIZE // 2, PREVIEW_SIZE // 2,
            text="Select an image\nto preview",
            fill="#999", font=("SF Pro Text", 11), justify="center",
            tags="placeholder"
        )

        preview_info = ttk.Frame(preview_frame)
        preview_info.pack(fill="x", pady=(4, 0))
        self.preview_dims_var = tk.StringVar(value="")
        ttk.Label(preview_info, textvariable=self.preview_dims_var,
                  font=("SF Mono", 10), foreground="gray").pack()

        # ── Source files (in left column) ──────────────────────────
        ttk.Label(left, text="Source Images", font=("SF Pro Text", 12, "bold")).pack(anchor="w")

        list_frame = ttk.Frame(left)
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
        self.file_list.bind("<<ListboxSelect>>", self._on_file_select)

        btn_row = ttk.Frame(left)
        btn_row.pack(fill="x", pady=(6, 0))
        ttk.Button(btn_row, text="Add Files…",       command=self._add_files).pack(side="left")
        ttk.Button(btn_row, text="Remove Selected",  command=self._remove_selected).pack(side="left", padx=(6, 0))
        ttk.Button(btn_row, text="Clear All",        command=self._clear_files).pack(side="left", padx=(6, 0))

        # ── Output Name ────────────────────────────────────────────
        ttk.Separator(left, orient="horizontal").pack(fill="x", pady=12)
        ttk.Label(left, text="Material Name", font=("SF Pro Text", 12, "bold")).pack(anchor="w")

        name_row = ttk.Frame(left)
        name_row.pack(fill="x", pady=(4, 0))
        self.material_name_var = tk.StringVar()
        self.material_name_entry = ttk.Entry(name_row, textvariable=self.material_name_var, width=30)
        self.material_name_entry.pack(side="left", fill="x", expand=True)
        ttk.Label(name_row, text=".skm", foreground="gray").pack(side="left", padx=(2, 0))
        ttk.Label(left, text="Leave blank to use each image's filename. With multiple\nimages, a custom name produces Name-1.skm, Name-2.skm, etc.",
                  foreground="gray", font=("SF Pro Text", 10), justify="left").pack(anchor="w", pady=(2, 0))

        ttk.Separator(outer, orient="horizontal").pack(fill="x", pady=12)

        # ── Output Folder ──────────────────────────────────────────
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
        self.width_var = tk.StringVar(value="100")
        ttk.Entry(dim_row, textvariable=self.width_var, width=8).pack(side="left", padx=(4, 2))

        ttk.Label(dim_row, text="   Height:").pack(side="left")
        self.height_var = tk.StringVar(value="100")
        ttk.Entry(dim_row, textvariable=self.height_var, width=8).pack(side="left", padx=(4, 2))

        ttk.Label(dim_row, text="   Units:").pack(side="left")
        self.unit_var = tk.StringVar(value="cm")
        unit_cb = ttk.Combobox(dim_row, textvariable=self.unit_var,
                               values=list(UNITS_TO_INCHES.keys()),
                               state="readonly", width=4)
        unit_cb.pack(side="left", padx=(4, 0))
        unit_cb.bind("<<ComboboxSelected>>", self._on_unit_change)
        self._prev_unit = "cm"

        # Update preview when dimensions change
        self.width_var.trace_add("write", self._on_dim_change)
        self.height_var.trace_add("write", self._on_dim_change)

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

        status_row = ttk.Frame(outer)
        status_row.pack(fill="x", pady=(8, 0))
        self.status_var = tk.StringVar(value="Add images to get started.")
        ttk.Label(status_row, textvariable=self.status_var,
                  foreground="gray").pack(side="left")
        self.reveal_btn = ttk.Button(status_row, text="Reveal in Finder",
                                     command=self._reveal_in_finder)
        # Hidden until first successful conversion
        self.reveal_btn.pack_forget()

    # ------------------------------------------------------------------
    # Preferences (persist between launches)
    # ------------------------------------------------------------------

    def _load_saved_prefs(self):
        """Restore saved settings from previous session."""
        prefs = _load_prefs()
        if "unit" in prefs:
            old_unit = self.unit_var.get()
            new_unit = prefs["unit"]
            if new_unit in UNITS_TO_INCHES and new_unit != old_unit:
                self.unit_var.set(new_unit)
                self._prev_unit = new_unit
        if "width" in prefs:
            self.width_var.set(str(prefs["width"]))
        if "height" in prefs:
            self.height_var.set(str(prefs["height"]))
        if "output_mode" in prefs:
            self.output_mode.set(prefs["output_mode"])
            self._on_output_mode()
        if "output_path" in prefs:
            self.output_path_var.set(prefs["output_path"])

    def _save_current_prefs(self):
        """Save current settings for next launch."""
        _save_prefs({
            "unit": self.unit_var.get(),
            "width": self.width_var.get(),
            "height": self.height_var.get(),
            "output_mode": self.output_mode.get(),
            "output_path": self.output_path_var.get(),
        })

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
        # Auto-select and preview the first added image
        if paths and self.file_list.size() > 0:
            self.file_list.selection_clear(0, "end")
            self.file_list.selection_set(0)
            self._on_file_select()

    def _remove_selected(self):
        for i in reversed(self.file_list.curselection()):
            self.file_list.delete(i)
        self._update_status()
        self._clear_preview()

    def _clear_files(self):
        self.file_list.delete(0, "end")
        self._update_status()
        self._clear_preview()

    def _on_file_select(self, _=None):
        sel = self.file_list.curselection()
        if not sel:
            return
        path = self.file_list.get(sel[0])
        self._current_preview_path = path
        self._refresh_preview()
        # Auto-fill material name from selected file stem
        stem = Path(path).stem
        if not self.material_name_var.get().strip():
            self.material_name_var.set(stem)

    def _on_dim_change(self, *_):
        """Called when width or height values change — refresh preview."""
        if hasattr(self, "_current_preview_path") and self._current_preview_path:
            self._refresh_preview()

    def _refresh_preview(self):
        path = getattr(self, "_current_preview_path", None)
        if not path:
            return
        try:
            w_in = float(self.width_var.get())
            h_in = float(self.height_var.get())
            if w_in <= 0 or h_in <= 0:
                return
        except (ValueError, tk.TclError):
            w_in = h_in = 1.0  # fallback to square
        self._show_preview(path, w_in, h_in)

    def _show_preview(self, path, w_in=1.0, h_in=1.0):
        try:
            from PIL import ImageTk
            img = Image.open(path)
            orig_w, orig_h = img.size

            # Scale the preview to reflect the chosen tile dimensions.
            # The 200x200 canvas represents the tile; the image is stretched
            # to match the width:height ratio chosen by the user.
            canvas_size = 200
            aspect = w_in / h_in
            if aspect >= 1:
                disp_w = canvas_size
                disp_h = int(canvas_size / aspect)
            else:
                disp_h = canvas_size
                disp_w = int(canvas_size * aspect)

            resized = img.resize((max(disp_w, 1), max(disp_h, 1)), Image.LANCZOS)
            self._preview_photo = ImageTk.PhotoImage(resized)
            self.preview_canvas.delete("all")
            # Draw a light border around the tile area
            x0 = (canvas_size - disp_w) // 2
            y0 = (canvas_size - disp_h) // 2
            self.preview_canvas.create_rectangle(
                x0, y0, x0 + disp_w, y0 + disp_h,
                outline="#aaa", dash=(2, 2)
            )
            self.preview_canvas.create_image(
                canvas_size // 2, canvas_size // 2,
                image=self._preview_photo, anchor="center"
            )
            # Show both pixel dims and tile size in the user's chosen unit
            unit = getattr(self, "unit_var", None)
            unit_label = unit.get() if unit else "in"
            self.preview_dims_var.set(
                f"{orig_w}x{orig_h} px  |  {w_in:.4g} x {h_in:.4g} {unit_label}"
            )
        except Exception:
            self._clear_preview()

    def _clear_preview(self):
        self._current_preview_path = None
        self._preview_photo = None
        self.preview_canvas.delete("all")
        self.preview_canvas.create_text(
            100, 100,
            text="Select an image\nto preview",
            fill="#999", font=("SF Pro Text", 11), justify="center"
        )
        self.preview_dims_var.set("")

    def _on_output_mode(self):
        custom = self.output_mode.get() == "custom"
        self.output_entry.config(state="normal" if custom else "disabled")
        self.browse_btn.config(state="normal" if custom else "disabled")

    def _browse_output(self):
        d = filedialog.askdirectory(title="Select Output Folder")
        if d:
            self.output_path_var.set(d)

    def _on_unit_change(self, _=None):
        """Convert displayed values from old unit to new unit."""
        old_unit = self._prev_unit
        new_unit = self.unit_var.get()
        if old_unit == new_unit:
            return
        try:
            w = float(self.width_var.get())
            h = float(self.height_var.get())
            # old unit → inches → new unit
            old_to_in = UNITS_TO_INCHES[old_unit]
            new_to_in = UNITS_TO_INCHES[new_unit]
            w_new = (w * old_to_in) / new_to_in
            h_new = (h * old_to_in) / new_to_in
            self.width_var.set(f"{w_new:.4g}")
            self.height_var.set(f"{h_new:.4g}")
        except (ValueError, KeyError):
            pass
        self._prev_unit = new_unit

    def _on_preset(self, _=None):
        """Set dimensions from preset. Presets store inches; convert to current unit."""
        label = self.preset_var.get()
        for name, w, h in PRESETS:
            if name == label and w is not None:
                to_in = UNITS_TO_INCHES.get(self.unit_var.get(), 1.0)
                self.width_var.set(f"{w / to_in:.4g}")
                self.height_var.set(f"{h / to_in:.4g}")
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
            w_val = float(self.width_var.get())
            h_val = float(self.height_var.get())
            if w_val <= 0 or h_val <= 0:
                raise ValueError
            # Convert from display unit to inches (SKM always stores inches)
            to_in = UNITS_TO_INCHES.get(self.unit_var.get(), 1.0)
            w_in = w_val * to_in
            h_in = h_val * to_in
        except ValueError:
            messagebox.showerror("Invalid size", "Width and Height must be positive numbers.")
            return

        mat_name = self.material_name_var.get().strip() or None

        self.convert_btn.config(state="disabled")
        self.reveal_btn.pack_forget()
        self._log_clear()
        self.status_var.set("Converting…")

        # Save prefs on each conversion
        self._save_current_prefs()

        def run():
            ok = err = 0
            last_dir = None
            multi = len(files) > 1
            for idx, path_str in enumerate(files, start=1):
                src = Path(path_str)
                # Single file: use custom name as-is.
                # Multiple files + custom name: Name-1, Name-2, …
                # No custom name: use each image's filename.
                if mat_name and multi:
                    file_name = f"{mat_name}-{idx}"
                elif mat_name:
                    file_name = mat_name
                else:
                    file_name = None
                try:
                    out_dir = self._resolve_output(src)
                    last_dir = str(out_dir)
                    skm = img_to_skm.convert(
                        str(src), x_scale=w_in, y_scale=h_in,
                        output_dir=str(out_dir),
                        material_name=file_name
                    )
                    self._log(f"✓  {src.name}  →  {Path(skm).name}\n", "ok")
                    ok += 1
                except Exception as e:
                    self._log(f"✗  {src.name}: {e}\n", "err")
                    err += 1

            self._last_output_dir = last_dir
            summary = f"Done — {ok} converted"
            if err:
                summary += f", {err} failed"
            self.after(0, lambda: self._finish(summary))

        threading.Thread(target=run, daemon=True).start()

    def _finish(self, summary):
        self.convert_btn.config(state="normal")
        self.status_var.set(summary)
        # Show Reveal in Finder if we have an output directory
        if self._last_output_dir and Path(self._last_output_dir).exists():
            self.reveal_btn.pack(side="right")

    def _reveal_in_finder(self):
        """Open the output folder in Finder."""
        if self._last_output_dir and Path(self._last_output_dir).exists():
            subprocess.Popen(["open", str(self._last_output_dir)])

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


    def _on_quit(self):
        """Save preferences and ensure the process fully terminates."""
        self._save_current_prefs()
        self.destroy()
        import os
        os._exit(0)


if __name__ == "__main__":
    app = App()
    app.mainloop()
