#!/usr/bin/env python3
"""SKP Converter — GUI app to convert images to SketchUp SKM materials."""

import json
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
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

try:
    import customtkinter as ctk
except ImportError:
    messagebox.showerror(
        "Missing dependency",
        "customtkinter is not installed.\n\nRun in Terminal:\n  pip3 install customtkinter"
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


# ── Colours ──────────────────────────────────────────────────────────
BG          = "#f9fafb"
CARD        = "#ffffff"
ACCENT      = "#2563eb"
ACCENT_HOVER = "#1d4ed8"
ACCENT_LIGHT = "#eff6ff"
SEC_BTN     = "#e5e7eb"    # secondary button bg
SEC_HOVER   = "#d1d5db"    # secondary button hover
TEXT        = "#111827"
TEXT_SEC    = "#374151"
TEXT_DIM    = "#6b7280"
GREEN       = "#059669"
RED         = "#dc2626"
BORDER      = "#e5e7eb"
ENTRY_BG    = "#ffffff"
ENTRY_BORDER = "#d1d5db"
PREVIEW_BG  = "#f3f4f6"


ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")


class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Image to SKM Converter for SketchUp")
        self.geometry("680x880")
        self.resizable(True, True)
        self.minsize(600, 700)
        self.configure(fg_color=BG)
        self._preview_photo = None
        self._last_output_dir = None
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
        try:
            from AppKit import NSApplication, NSApp
            NSApplication.sharedApplication()
            NSApp.activateIgnoringOtherApps_(True)
        except ImportError:
            pass
        self.attributes("-topmost", True)
        self.lift()
        self.focus_force()
        self.after(300, lambda: self.attributes("-topmost", False))

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        PREVIEW_SIZE = 180

        outer = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        outer.pack(fill="both", expand=True, padx=24, pady=(16, 20))

        # ── Heading ──────────────────────────────────────────────────
        ctk.CTkLabel(outer, text="Image to SKM Converter for SketchUp",
                     font=("SF Pro Display", 18, "bold"),
                     text_color=TEXT).pack(anchor="w")
        formats = ", ".join(sorted(ext.lstrip(".").upper() for ext in IMAGE_EXTENSIONS))
        ctk.CTkLabel(outer, text=f"Supported formats: {formats}",
                     font=("SF Pro Text", 11),
                     text_color=TEXT_DIM).pack(anchor="w", pady=(2, 12))

        # ── Top: source list + preview ───────────────────────────────
        top = ctk.CTkFrame(outer, fg_color="transparent")
        top.pack(fill="x")

        left = ctk.CTkFrame(top, fg_color="transparent")
        left.pack(side="left", fill="both", expand=True)

        # Preview (right)
        preview_card = ctk.CTkFrame(top, fg_color=CARD, corner_radius=10,
                                    border_width=1, border_color=BORDER)
        preview_card.pack(side="right", padx=(14, 0), anchor="n")

        ctk.CTkLabel(preview_card, text="Preview",
                     font=("SF Pro Text", 10), text_color=TEXT_DIM).pack(pady=(6, 3))

        self.preview_canvas = tk.Canvas(
            preview_card, width=PREVIEW_SIZE, height=PREVIEW_SIZE,
            bg=PREVIEW_BG, highlightthickness=0, borderwidth=0
        )
        self.preview_canvas.pack(padx=8)
        self.preview_canvas.create_text(
            PREVIEW_SIZE // 2, PREVIEW_SIZE // 2,
            text="Select an image\nto preview",
            fill=TEXT_DIM, font=("SF Pro Text", 10), justify="center",
            tags="placeholder"
        )

        self.preview_dims_var = tk.StringVar(value="")
        ctk.CTkLabel(preview_card, textvariable=self.preview_dims_var,
                     font=("SF Mono", 9), text_color=TEXT_DIM).pack(pady=(2, 8))

        # Source images
        ctk.CTkLabel(left, text="Source Images",
                     font=("SF Pro Text", 12, "bold"),
                     text_color=TEXT).pack(anchor="w")

        list_card = ctk.CTkFrame(left, fg_color=CARD, corner_radius=8,
                                 border_width=1, border_color=BORDER)
        list_card.pack(fill="x", pady=(4, 0))

        self.file_list = tk.Listbox(
            list_card, height=4, selectmode="extended",
            font=("SF Mono", 11),
            bg=CARD, fg=TEXT, selectbackground=ACCENT_LIGHT,
            selectforeground=TEXT,
            relief="flat", borderwidth=0, highlightthickness=0
        )
        sb = ctk.CTkScrollbar(list_card, command=self.file_list.yview, height=0)
        self.file_list.configure(yscrollcommand=sb.set)
        self.file_list.pack(side="left", fill="both", expand=True, padx=(6, 0), pady=4)
        sb.pack(side="right", fill="y", padx=(0, 2), pady=4)
        self.file_list.bind("<<ListboxSelect>>", self._on_file_select)

        btn_row = ctk.CTkFrame(left, fg_color="transparent")
        btn_row.pack(fill="x", pady=(6, 0))
        self._ghost_btn(btn_row, "+ Add Files…", self._add_files).pack(side="left")
        self._ghost_btn(btn_row, "Remove", self._remove_selected).pack(side="left", padx=(4, 0))
        self._ghost_btn(btn_row, "Clear All", self._clear_files).pack(side="left", padx=(4, 0))

        # ── Material Name ────────────────────────────────────────────
        self._sep(left)
        ctk.CTkLabel(left, text="Material Name",
                     font=("SF Pro Text", 12, "bold"),
                     text_color=TEXT).pack(anchor="w")

        name_row = ctk.CTkFrame(left, fg_color="transparent")
        name_row.pack(fill="x", pady=(4, 0))
        self.material_name_var = tk.StringVar()
        ctk.CTkEntry(name_row, textvariable=self.material_name_var,
                     width=240, height=30, corner_radius=6,
                     fg_color=CARD, border_color=ENTRY_BORDER,
                     text_color=TEXT, font=("SF Mono", 12)).pack(side="left")
        ctk.CTkLabel(name_row, text=".skm", font=("SF Mono", 12),
                     text_color=TEXT_DIM).pack(side="left", padx=(4, 0))

        ctk.CTkLabel(left,
                     text="Leave blank to use filename. Multiple images: Name-1, Name-2, etc.",
                     font=("SF Pro Text", 10), text_color=TEXT_DIM,
                     justify="left").pack(anchor="w", pady=(2, 0))

        # ── Output Folder ────────────────────────────────────────────
        self._sep(outer)
        ctk.CTkLabel(outer, text="Output Folder",
                     font=("SF Pro Text", 12, "bold"),
                     text_color=TEXT).pack(anchor="w")

        self.output_mode = tk.StringVar(value="same")

        ctk.CTkRadioButton(outer, text="Same folder as source image",
                           variable=self.output_mode, value="same",
                           command=self._on_output_mode,
                           font=("SF Pro Text", 12), text_color=TEXT_SEC,
                           fg_color=ACCENT, hover_color=ACCENT_HOVER,
                           border_color=ENTRY_BORDER).pack(anchor="w", pady=(4, 0))

        custom_row = ctk.CTkFrame(outer, fg_color="transparent")
        custom_row.pack(fill="x", pady=(3, 0))
        ctk.CTkRadioButton(custom_row, text="Custom:",
                           variable=self.output_mode, value="custom",
                           command=self._on_output_mode,
                           font=("SF Pro Text", 12), text_color=TEXT_SEC,
                           fg_color=ACCENT, hover_color=ACCENT_HOVER,
                           border_color=ENTRY_BORDER).pack(side="left")

        self.output_path_var = tk.StringVar()
        self.output_entry = ctk.CTkEntry(custom_row, textvariable=self.output_path_var,
                                         width=200, height=28, corner_radius=6,
                                         fg_color=CARD, border_color=ENTRY_BORDER,
                                         text_color=TEXT, state="disabled")
        self.output_entry.pack(side="left", padx=(6, 4))
        self.browse_btn = self._ghost_btn(custom_row, "Browse…", self._browse_output)
        self.browse_btn.pack(side="left")
        self.browse_btn.configure(state="disabled")

        # ── Texture Tile Size ────────────────────────────────────────
        self._sep(outer)
        ctk.CTkLabel(outer, text="Texture Tile Size",
                     font=("SF Pro Text", 12, "bold"),
                     text_color=TEXT).pack(anchor="w")

        preset_row = ctk.CTkFrame(outer, fg_color="transparent")
        preset_row.pack(fill="x", pady=(4, 0))
        ctk.CTkLabel(preset_row, text="Preset", font=("SF Pro Text", 11),
                     text_color=TEXT_SEC).pack(side="left")
        self.preset_var = tk.StringVar(value=PRESETS[1][0])
        ctk.CTkOptionMenu(preset_row, variable=self.preset_var,
                          values=[p[0] for p in PRESETS],
                          command=self._on_preset,
                          width=160, height=28, corner_radius=6,
                          fg_color=CARD, button_color=SEC_BTN,
                          button_hover_color=SEC_HOVER,
                          dropdown_fg_color=CARD, dropdown_text_color=TEXT,
                          font=("SF Pro Text", 11),
                          text_color=TEXT).pack(side="left", padx=(6, 0))

        dim_row = ctk.CTkFrame(outer, fg_color="transparent")
        dim_row.pack(fill="x", pady=(6, 0))

        ctk.CTkLabel(dim_row, text="W", font=("SF Pro Text", 11),
                     text_color=TEXT_SEC).pack(side="left")
        self.width_var = tk.StringVar(value="100")
        ctk.CTkEntry(dim_row, textvariable=self.width_var,
                     width=65, height=28, corner_radius=6,
                     fg_color=CARD, border_color=ENTRY_BORDER,
                     text_color=TEXT, font=("SF Mono", 11)).pack(side="left", padx=(4, 0))

        ctk.CTkLabel(dim_row, text="×", font=("SF Pro Text", 13),
                     text_color=TEXT_DIM).pack(side="left", padx=(8, 8))

        ctk.CTkLabel(dim_row, text="H", font=("SF Pro Text", 11),
                     text_color=TEXT_SEC).pack(side="left")
        self.height_var = tk.StringVar(value="100")
        ctk.CTkEntry(dim_row, textvariable=self.height_var,
                     width=65, height=28, corner_radius=6,
                     fg_color=CARD, border_color=ENTRY_BORDER,
                     text_color=TEXT, font=("SF Mono", 11)).pack(side="left", padx=(4, 0))

        self.unit_var = tk.StringVar(value="cm")
        ctk.CTkOptionMenu(dim_row, variable=self.unit_var,
                          values=list(UNITS_TO_INCHES.keys()),
                          command=self._on_unit_change,
                          width=60, height=28, corner_radius=6,
                          fg_color=CARD, button_color=SEC_BTN,
                          button_hover_color=SEC_HOVER,
                          dropdown_fg_color=CARD, dropdown_text_color=TEXT,
                          font=("SF Mono", 11),
                          text_color=TEXT).pack(side="left", padx=(12, 0))
        self._prev_unit = "cm"

        self.width_var.trace_add("write", self._on_dim_change)
        self.height_var.trace_add("write", self._on_dim_change)

        # ── Convert ──────────────────────────────────────────────────
        self.convert_btn = ctk.CTkButton(
            outer, text="Convert", command=self._convert,
            width=0, height=38, corner_radius=8,
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            font=("SF Pro Text", 13, "bold"), text_color="white"
        )
        self.convert_btn.pack(fill="x", pady=(16, 0))

        # ── Results ──────────────────────────────────────────────────
        self._sep(outer)
        ctk.CTkLabel(outer, text="Results",
                     font=("SF Pro Text", 12, "bold"),
                     text_color=TEXT).pack(anchor="w")

        log_card = ctk.CTkFrame(outer, fg_color=CARD, corner_radius=8,
                                border_width=1, border_color=BORDER)
        log_card.pack(fill="both", expand=True, pady=(4, 0))

        self.log = tk.Text(log_card, height=3, state="disabled",
                           font=("SF Mono", 11), wrap="none",
                           bg=CARD, fg=TEXT,
                           insertbackground=TEXT,
                           relief="flat", borderwidth=0, highlightthickness=0)
        log_sb = ctk.CTkScrollbar(log_card, command=self.log.yview, height=0)
        self.log.configure(yscrollcommand=log_sb.set)
        self.log.pack(side="left", fill="both", expand=True, padx=(6, 0), pady=4)
        log_sb.pack(side="right", fill="y", padx=(0, 2), pady=4)

        self.log.tag_config("ok",  foreground=GREEN)
        self.log.tag_config("err", foreground=RED)

        # ── Status ───────────────────────────────────────────────────
        status_row = ctk.CTkFrame(outer, fg_color="transparent")
        status_row.pack(fill="x", pady=(6, 0))
        self.status_var = tk.StringVar(value="Add images to get started.")
        ctk.CTkLabel(status_row, textvariable=self.status_var,
                     font=("SF Pro Text", 11), text_color=TEXT_DIM).pack(side="left")
        self.reveal_btn = self._ghost_btn(status_row, "Reveal in Finder",
                                          self._reveal_in_finder)
        self.reveal_btn.pack_forget()

    # ── UI helpers ───────────────────────────────────────────────────

    def _sep(self, parent):
        ctk.CTkFrame(parent, fg_color=BORDER, height=1,
                     corner_radius=0).pack(fill="x", pady=10)

    def _ghost_btn(self, parent, text, command):
        """Secondary button — light bg, dark text."""
        return ctk.CTkButton(parent, text=text, command=command,
                             width=0, height=26, corner_radius=6,
                             fg_color=SEC_BTN, hover_color=SEC_HOVER,
                             font=("SF Pro Text", 11), text_color=TEXT_SEC,
                             border_width=0)

    # ------------------------------------------------------------------
    # Preferences
    # ------------------------------------------------------------------

    def _load_saved_prefs(self):
        prefs = _load_prefs()
        if "unit" in prefs:
            new_unit = prefs["unit"]
            if new_unit in UNITS_TO_INCHES:
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
        stem = Path(path).stem
        if not self.material_name_var.get().strip():
            self.material_name_var.set(stem)

    def _on_dim_change(self, *_):
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
            w_in = h_in = 1.0
        self._show_preview(path, w_in, h_in)

    def _show_preview(self, path, w_in=1.0, h_in=1.0):
        try:
            from PIL import ImageTk
            img = Image.open(path)
            orig_w, orig_h = img.size

            canvas_size = 180
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
            x0 = (canvas_size - disp_w) // 2
            y0 = (canvas_size - disp_h) // 2
            self.preview_canvas.create_rectangle(
                x0, y0, x0 + disp_w, y0 + disp_h,
                outline=BORDER, dash=(2, 2)
            )
            self.preview_canvas.create_image(
                canvas_size // 2, canvas_size // 2,
                image=self._preview_photo, anchor="center"
            )
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
            90, 90,
            text="Select an image\nto preview",
            fill=TEXT_DIM, font=("SF Pro Text", 10), justify="center"
        )
        self.preview_dims_var.set("")

    def _on_output_mode(self):
        custom = self.output_mode.get() == "custom"
        self.output_entry.configure(state="normal" if custom else "disabled")
        self.browse_btn.configure(state="normal" if custom else "disabled")

    def _browse_output(self):
        d = filedialog.askdirectory(title="Select Output Folder")
        if d:
            self.output_path_var.set(d)

    def _on_unit_change(self, new_unit=None):
        old_unit = self._prev_unit
        if new_unit is None:
            new_unit = self.unit_var.get()
        if old_unit == new_unit:
            return
        try:
            w = float(self.width_var.get())
            h = float(self.height_var.get())
            old_to_in = UNITS_TO_INCHES[old_unit]
            new_to_in = UNITS_TO_INCHES[new_unit]
            self.width_var.set(f"{(w * old_to_in) / new_to_in:.4g}")
            self.height_var.set(f"{(h * old_to_in) / new_to_in:.4g}")
        except (ValueError, KeyError):
            pass
        self._prev_unit = new_unit

    def _on_preset(self, label=None):
        if label is None:
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
            to_in = UNITS_TO_INCHES.get(self.unit_var.get(), 1.0)
            w_in = w_val * to_in
            h_in = h_val * to_in
        except ValueError:
            messagebox.showerror("Invalid size", "Width and Height must be positive numbers.")
            return

        mat_name = self.material_name_var.get().strip() or None

        self.convert_btn.configure(state="disabled")
        self.reveal_btn.pack_forget()
        self._log_clear()
        self.status_var.set("Converting…")
        self._save_current_prefs()

        def run():
            ok = err = 0
            last_dir = None
            multi = len(files) > 1
            for idx, path_str in enumerate(files, start=1):
                src = Path(path_str)
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
        self.convert_btn.configure(state="normal")
        self.status_var.set(summary)
        if self._last_output_dir and Path(self._last_output_dir).exists():
            self.reveal_btn.pack(side="right")

    def _reveal_in_finder(self):
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
        self._save_current_prefs()
        self.destroy()
        import os
        os._exit(0)


if __name__ == "__main__":
    app = App()
    app.mainloop()
