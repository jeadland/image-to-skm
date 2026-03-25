#!/usr/bin/env python3
"""Convert image files (JPG, PNG, etc.) to SketchUp SKM material format.

Usage:
    python3 img_to_skm.py image.jpg [image2.png ...] [--scale INCHES]

The .skm file is written next to each source image.
Default scale: 39.37 inches (1 metre per tile).
"""

import argparse
import io
import os
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    sys.exit("Pillow is required: pip3 install Pillow")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _average_color(img: Image.Image) -> tuple[int, int, int]:
    """Return (r, g, b) average colour of the image."""
    rgb = img.convert("RGB").resize((1, 1), Image.LANCZOS)
    return rgb.getpixel((0, 0))  # type: ignore[return-value]


def _packed_bgr(r: int, g: int, b: int) -> int:
    """Pack RGB into BGR integer as SketchUp expects for avgColor."""
    return (b << 16) | (g << 8) | r


def _thumbnail_bytes(img: Image.Image, size: int = 128) -> bytes:
    """Return a PNG thumbnail as bytes."""
    thumb = img.copy()
    thumb.thumbnail((size, size), Image.LANCZOS)

    # Paste onto a square canvas (keeps aspect ratio, fills rest transparent)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    offset = ((size - thumb.width) // 2, (size - thumb.height) // 2)
    canvas.paste(thumb.convert("RGBA"), offset)

    buf = io.BytesIO()
    canvas.save(buf, format="PNG")
    return buf.getvalue()


def _internal_name(filename: str) -> str:
    """Add _1 suffix before extension: image.jpg → image_1.jpg"""
    stem = Path(filename).stem
    suffix = Path(filename).suffix
    return f"{stem}_1{suffix}"


# ---------------------------------------------------------------------------
# XML builders
# ---------------------------------------------------------------------------

def _document_xml(name: str, filename: str, r: int, g: int, b: int,
                  avg: int, x_scale: float, y_scale: float) -> str:
    internal = _internal_name(filename)
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="no" ?>\n'
        '<materialDocument'
        ' xmlns="http://sketchup.google.com/schemas/sketchup/1.0/material"'
        ' xmlns:mat="http://sketchup.google.com/schemas/sketchup/1.0/material"'
        ' xmlns:r="http://sketchup.google.com/schemas/1.0/references"'
        ' xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"'
        ' xsi:schemaLocation="http://sketchup.google.com/schemas/sketchup/1.0/material'
        ' http://sketchup.google.com/schemas/sketchup/1.0/material.xsd">\n'
        f'  <mat:material name="{name}" type="1" workflow="0"'
        f' colorRed="{r}" colorGreen="{g}" colorBlue="{b}"'
        f' colorizeType="0" trans="0" useTrans="0" hasTexture="1">\n'
        f'    <mat:texture textureFilename="{filename}"'
        f' xScale="{x_scale:.6f}" yScale="{y_scale:.6f}" avgColor="{avg}">\n'
        '      <mat:images>\n'
        f'        <mat:image id="1" path="{internal}" file_name="{filename}" />\n'
        '      </mat:images>\n'
        '    </mat:texture>\n'
        '  </mat:material>\n'
        '</materialDocument>\n'
    )


def _properties_xml(name: str) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="no" ?>\n'
        '<documentProperties'
        ' xmlns="http://sketchup.google.com/schemas/1.0/documentproperties"'
        ' xmlns:dp="http://sketchup.google.com/schemas/1.0/documentproperties"'
        ' xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"'
        ' xsi:schemaLocation="http://sketchup.google.com/schemas/1.0/documentproperties'
        ' http://sketchup.google.com/schemas/1.0/documentproperties.xsd">\n'
        f'  <dp:title>{name}</dp:title>\n'
        '  <dp:description></dp:description>\n'
        '  <dp:creator></dp:creator>\n'
        '  <dp:keywords></dp:keywords>\n'
        '  <dp:lastModifiedBy></dp:lastModifiedBy>\n'
        '  <dp:revision>0</dp:revision>\n'
        f'  <dp:created>{now}</dp:created>\n'
        f'  <dp:modified>{now}</dp:modified>\n'
        '  <dp:thumbnail>doc_thumbnail.png</dp:thumbnail>\n'
        '  <dp:generator dp:name="Material" dp:version="1" />\n'
        '</documentProperties>\n'
    )


_REFERENCES_XML = (
    '<?xml version="1.0" encoding="UTF-8" standalone="no" ?>\n'
    '<references'
    ' xmlns="http://sketchup.google.com/schemas/1.0/references"'
    ' xmlns:r="http://sketchup.google.com/schemas/1.0/references"'
    ' xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"'
    ' xsi:schemaLocation="http://sketchup.google.com/schemas/1.0/references'
    ' http://sketchup.google.com/schemas/1.0/references.xsd" />\n'
)


# ---------------------------------------------------------------------------
# Main converter
# ---------------------------------------------------------------------------

def convert(image_path: str, scale: float = 39.37,
            x_scale: float | None = None, y_scale: float | None = None,
            output_dir: str | None = None) -> str:
    """Convert a single image to SKM. Returns the output .skm path.

    x_scale / y_scale override scale when provided (inches per tile axis).
    """
    src = Path(image_path).resolve()
    if not src.exists():
        raise FileNotFoundError(f"Image not found: {src}")

    xs = x_scale if x_scale is not None else scale
    ys = y_scale if y_scale is not None else scale

    img = Image.open(src)
    r, g, b = _average_color(img)
    avg = _packed_bgr(r, g, b)

    name = src.stem
    filename = src.name
    internal = _internal_name(filename)

    out_dir = Path(output_dir) if output_dir else src.parent
    skm_path = out_dir / src.with_suffix(".skm").name

    with zipfile.ZipFile(skm_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("document.xml",
                    _document_xml(name, filename, r, g, b, avg, xs, ys))
        zf.writestr("documentProperties.xml", _properties_xml(name))
        zf.writestr("references.xml", _REFERENCES_XML)
        zf.writestr("doc_thumbnail.png", _thumbnail_bytes(img))

        with open(src, "rb") as f:
            zf.writestr(f"ref/{internal}", f.read())

    return str(skm_path)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert image files to SketchUp SKM material format."
    )
    parser.add_argument("images", nargs="+", metavar="IMAGE",
                        help="Image file(s) to convert")
    parser.add_argument("--scale", type=float, default=39.37, metavar="INCHES",
                        help="Texture tile size in inches (default: 39.37 = 1 metre)")
    args = parser.parse_args()

    ok = err = 0
    for path in args.images:
        try:
            out = convert(path, scale=args.scale)
            print(f"✓  {out}")
            ok += 1
        except Exception as e:
            print(f"✗  {path}: {e}", file=sys.stderr)
            err += 1

    if err:
        sys.exit(1)


if __name__ == "__main__":
    main()
