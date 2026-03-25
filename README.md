# image-to-skm — Convert Images to SketchUp Material (.skm) Files

Convert JPG, PNG, and other image files to SketchUp's `.skm` material format. No SketchUp license required.

## What is an SKM file?

SketchUp uses `.skm` files to store materials (textures + metadata). They are ZIP archives containing:

```
material.skm
├── document.xml            ← material definition (color, texture scale, name)
├── documentProperties.xml  ← metadata (creator, timestamps)
├── references.xml          ← schema references
├── doc_thumbnail.png       ← 128×128 preview thumbnail
└── ref/
    └── texture_1.jpg       ← the texture image
```

The XML format uses SketchUp's `http://sketchup.google.com/schemas/sketchup/1.0/material` namespace. Each material stores:

- **Average color** (`colorRed`, `colorGreen`, `colorBlue`) — computed from the image pixels
- **Packed BGR integer** (`avgColor`) — `blue*65536 + green*256 + red`
- **Texture scale** (`xScale`, `yScale`) — real-world tile size in **inches** (independent width/height)
- **Texture reference** — the image stored under `ref/` with an `_1` id suffix

This format was reverse-engineered from real `.skm` files shipped with SketchUp 2026. It is compatible with SketchUp 2017 and later.

## Why does this exist?

SketchUp doesn't provide a way to batch-create materials from image files. If you have texture images (wood grain, tile, fabric, etc.), the only official way to make them into `.skm` files is to open SketchUp, create a material manually, apply the texture, and save it. For one image that's fine — for dozens it's tedious.

This tool automates it: give it images, get `.skm` files you can import directly into SketchUp's Materials panel.

## Installation

### Requirements

- **Python 3.10+** (macOS, Linux, Windows)
- **Pillow** — for image processing (average color, thumbnail generation)

```bash
pip install Pillow
```

### Optional (macOS GUI app)

To build the native macOS drag-and-drop app:

```bash
pip install py2app pyobjc-framework-Cocoa
```

## Usage

### Command line

Convert a single image (default 1m × 1m tile):

```bash
python img_to_skm.py photo.jpg
# → photo.skm (in same directory)
```

Convert multiple images with custom scale:

```bash
python img_to_skm.py *.jpg --scale 24
# → each .skm at 24" × 24" (2 ft square)
```

The `--scale` flag sets both width and height in inches. For independent width/height, use the Python API or GUI app.

### Python API

```python
import img_to_skm

# Square tile (1 metre)
img_to_skm.convert("brick.jpg", scale=39.37)

# Rectangular — 5 ft wide × 8 ft tall (e.g., a rug)
img_to_skm.convert("rug.jpg", x_scale=60, y_scale=96)

# Custom output directory
img_to_skm.convert("tile.png", scale=12, output_dir="/path/to/materials")
```

### macOS GUI app

Build and launch the native app:

```bash
python setup.py py2app
open dist/SKP\ Converter.app
```

The app provides:
- File picker for source images
- Output folder selection (same as source or custom)
- Preset sizes (1m×1m, 5ft×8ft, etc.) or custom width × height in inches
- Batch conversion with progress log

## Importing into SketchUp

1. Open SketchUp
2. Open the **Materials** panel (Window → Materials on Mac, or Default Tray on Windows)
3. Click the **Details** menu (gear icon) → **Add Collection to Favorites…**
4. Select the folder containing your `.skm` files
5. The materials appear in the panel, ready to paint onto faces

Alternatively, use **File → Import** and select a `.skm` file directly.

## File format reference

### document.xml

```xml
<?xml version="1.0" encoding="UTF-8" standalone="no" ?>
<materialDocument
  xmlns="http://sketchup.google.com/schemas/sketchup/1.0/material"
  xmlns:mat="http://sketchup.google.com/schemas/sketchup/1.0/material"
  xmlns:r="http://sketchup.google.com/schemas/1.0/references"
  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
  xsi:schemaLocation="http://sketchup.google.com/schemas/sketchup/1.0/material
    http://sketchup.google.com/schemas/sketchup/1.0/material.xsd">
  <mat:material name="MaterialName" type="1" workflow="0"
    colorRed="135" colorGreen="103" colorBlue="96"
    colorizeType="0" trans="0" useTrans="0" hasTexture="1">
    <mat:texture textureFilename="image.jpg"
      xScale="39.370100" yScale="39.370100" avgColor="6317959">
      <mat:images>
        <mat:image id="1" path="image_1.jpg" file_name="image.jpg" />
      </mat:images>
    </mat:texture>
  </mat:material>
</materialDocument>
```

**Key fields:**

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Material name (displayed in SketchUp) |
| `type` | int | Always `1` for textured materials |
| `workflow` | int | `0` = basic, `1` = PBR (physically based rendering) |
| `colorRed/Green/Blue` | int 0–255 | Average color of the texture |
| `colorizeType` | int | `0` = none |
| `trans` | float | Transparency (0 = opaque) |
| `useTrans` | int | `0` = no transparency |
| `hasTexture` | int | `1` = has texture image |
| `textureFilename` | string | Original image filename |
| `xScale` / `yScale` | float | Tile size in **inches** (39.37 ≈ 1 metre) |
| `avgColor` | int | Packed BGR: `(blue << 16) \| (green << 8) \| red` |
| `path` | string | Internal filename with `_<id>` suffix |
| `file_name` | string | Original filename |

### documentProperties.xml

Metadata — title, timestamps, revision number. The `generator` element should be `Material` version `1`.

### references.xml

Empty self-closing element with the references namespace. No external references are needed for basic materials.

### Texture storage

Texture images are stored inside the ZIP under `ref/`. The filename gets an `_<id>` suffix inserted before the extension:

- `photo.jpg` → stored as `ref/photo_1.jpg`
- `tile.png` → stored as `ref/tile_1.png`

### PBR materials (workflow="1")

SketchUp 2025+ supports PBR materials with additional texture maps (roughness, normal, ambient occlusion). These use `workflow="1"` and add a `<mat:pbrMR>` element. This tool generates `workflow="0"` (basic) materials which are compatible with all SketchUp versions from 2017 onward.

## Common scale values

| Real-world size | Inches | Use case |
|----------------|--------|----------|
| 0.5 m × 0.5 m | 19.69 | Small tiles |
| 1 m × 1 m | 39.37 | Standard tiles, wood planks |
| 2 m × 2 m | 78.74 | Large wall panels |
| 1 ft × 1 ft | 12.0 | Floor tiles |
| 2 ft × 3 ft | 24 × 36 | Small rugs |
| 5 ft × 8 ft | 60 × 96 | Area rugs |
| 8 ft × 10 ft | 96 × 120 | Large area rugs |

## How it was built

The `.skm` format is not publicly documented by Trimble. This tool was built by reverse-engineering real `.skm` files from SketchUp 2026's shipped materials library. The XML structure, namespace URIs, and attribute semantics were determined by inspecting files like `Tile Mosaic Multi.skm` and `Plywood_01_1K.skm`.

## License

MIT
