# image-to-skm — Convert Images to SketchUp Material (.skm) Files

Convert JPG, PNG, BMP, GIF, TIFF, and WebP images to SketchUp's `.skm` material format. No SketchUp license required.

## What is an SKM file?

SketchUp uses `.skm` files to store materials (textures + metadata). An `.skm` file is a ZIP archive containing:

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

This format was reverse-engineered from real `.skm` files shipped with SketchUp 2026. It is compatible with **SketchUp 2017 and later**.

## Why does this exist?

SketchUp doesn't provide a way to batch-create materials from image files. If you have texture images (wood grain, tile, fabric, etc.), the only official way to make them into `.skm` files is to open SketchUp, create a material manually, apply the texture, and save it. For one image that's fine — for dozens it's tedious.

This tool automates it: give it images, get `.skm` files you can import directly into SketchUp's Materials panel.

## Supported input formats

| Format | Extensions |
|--------|-----------|
| JPEG | `.jpg`, `.jpeg` |
| PNG | `.png` |
| BMP | `.bmp` |
| TIFF | `.tif`, `.tiff` |
| WebP | `.webp` |
| GIF | `.gif` |

## Installation

### Requirements

- **Python 3.10+** (macOS, Linux, Windows)
- **Pillow** — for image processing (average color, thumbnail generation)

```bash
pip install Pillow
```

### macOS GUI app (optional)

To build the native macOS app with image preview and batch conversion:

```bash
pip install py2app pyobjc-framework-Cocoa
python build_app.py
```

This creates `SKP Converter.app` on your Desktop — double-click to launch.

## Usage

### macOS GUI app

The app provides a complete interface for converting images to SKM:

1. **Add images** — click "Add Files…" to select one or more images
2. **Set material name** — optionally enter a custom name
   - Leave blank to use each image's original filename
   - With multiple images, a custom name produces `Name-1.skm`, `Name-2.skm`, etc.
   - With a single image, the name is used as-is: `Name.skm`
3. **Choose output folder** — same folder as source, or pick a custom destination
4. **Set tile size** — pick a preset or enter custom width × height
   - **Units dropdown**: choose between inches (`in`), centimetres (`cm`), feet (`ft`), or metres (`m`)
   - Switching units auto-converts the displayed values
   - Presets include common sizes: 1m×1m, 5ft×8ft, 8ft×10ft, etc.
5. **Preview** — shows the selected image scaled to your chosen tile proportions
6. Click **Convert**

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

The `--scale` flag sets both width and height in **inches**. For independent width/height, use the Python API or GUI app.

### Python API

```python
import img_to_skm

# Square tile (1 metre = 39.37 inches)
img_to_skm.convert("brick.jpg", scale=39.37)

# Rectangular — 5 ft wide × 8 ft tall (e.g., a rug)
img_to_skm.convert("rug.jpg", x_scale=60, y_scale=96)

# Custom output directory and material name
img_to_skm.convert("tile.png", scale=12, output_dir="/path/to/materials", material_name="My Tile")
```

## Importing into SketchUp

### SketchUp for Web (free online version)

1. Open the **Materials** panel by clicking the materials icon in the right sidebar
2. Click the **Upload** button (arrow pointing up)
3. In the "Choose Material" popup, click **My device** or drag and drop your `.skm` file
4. The material is added and ready to paint onto faces

### SketchUp Desktop (Pro / Studio)

1. Open the **Materials** panel (Window → Materials on Mac, or Default Tray on Windows)
2. Click the **Details** menu (gear icon) → **Add Collection to Favorites…**
3. Select the folder containing your `.skm` files
4. The materials appear in the panel, ready to paint onto faces

Alternatively, use **File → Import** and select a `.skm` file directly.

## Common scale values

| Real-world size | Inches | Centimetres | Use case |
|----------------|--------|-------------|----------|
| 0.5 m × 0.5 m | 19.69 × 19.69 | 50 × 50 | Small tiles |
| 1 m × 1 m | 39.37 × 39.37 | 100 × 100 | Standard tiles, wood planks |
| 2 m × 2 m | 78.74 × 78.74 | 200 × 200 | Large wall panels |
| 1 ft × 1 ft | 12 × 12 | 30.48 × 30.48 | Floor tiles |
| 2 ft × 3 ft | 24 × 36 | 60.96 × 91.44 | Small rugs |
| 5 ft × 8 ft | 60 × 96 | 152.4 × 243.8 | Area rugs |
| 8 ft × 10 ft | 96 × 120 | 243.8 × 304.8 | Large area rugs |

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

## How it was built

The `.skm` format is not publicly documented by Trimble. This tool was built by reverse-engineering real `.skm` files from SketchUp 2026's shipped materials library. The XML structure, namespace URIs, and attribute semantics were determined by inspecting files like `Tile Mosaic Multi.skm` and `Plywood_01_1K.skm`.

## Project structure

```
image-to-skm/
├── img_to_skm.py      ← core converter (CLI + Python API)
├── converter_app.py    ← macOS GUI app (tkinter)
├── build_app.py        ← builds SKP Converter.app using py2app
├── setup.py            ← py2app configuration
├── README.md
└── LICENSE             ← MIT
```

## License

MIT
