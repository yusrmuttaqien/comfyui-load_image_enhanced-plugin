# ComfyUI LoadImageEnhanced

This custom node extends ComfyUI's image loading functionality with filename output and original filename tracking.

## Features

### LoadImageEnhanced
- **Filename Output**: Returns the filename of the loaded image as a STRING output (the original LoadImage node has no filename output)
- **Original Filename Tracking**: Preserves the original filename even when the image is modified by tools like MaskEditor (toggleable)
- **Sync MaskEditor Toggle**: `sync_maskeditor` input controls whether `original_filename` follows MaskEditor writes
- **Recursive Subfolder Listing**: Lists images from all subfolders (the original LoadImage node only lists the top-level input directory); excludes `clipspace`, `3d`, `pasted`, and any folder/file starting with `.`

## Installation

### ComfyUI Manager / Comfy Registry (recommended)

The node is published to the Comfy Registry as `load-image-enhanced`.

1. Open the ComfyUI Manager (or the Comfy Registry / extensions page).
2. Search for `load-image-enhanced`.
3. Click **Install**.
4. Restart ComfyUI.

### Manual (git clone)

1. Clone the repository into your ComfyUI `custom_nodes` directory:
   ```bash
   git clone https://github.com/yusrmuttaqien/comfyui-load_image_enhanced-plugin.git custom_nodes/load-image-enhanced
   ```
2. Restart ComfyUI.
3. The new node will appear in the "image" category.

## Usage

### LoadImageEnhanced
- **Input**: Select an image file from the dropdown (includes images from subfolders)
- **Inputs**:
  - `image` — Image filename to load
  - `original_filename` — Text field that stores the original selected filename (editable by user)
  - `sync_maskeditor` — Toggle (default **off**): when off, `original_filename` ignores MaskEditor writes; when on, it follows every source including MaskEditor
- **Outputs**:
  - `image`: The loaded image tensor
  - `mask`: The image mask (if available)
  - `filename`: The filename of the loaded image

## Requirements

- ComfyUI
- PIL (Pillow)
- PyTorch
- NumPy

## Notes

### Filename Tracking

The `filename` output uses the value of the `original_filename` widget, falling back to the loaded file's basename when the widget is empty. The widget is automatically updated when you select a new image from the dropdown. Whether it also follows MaskEditor writes is controlled by the `sync_maskeditor` toggle:

- **`sync_maskeditor` off (default)** — `original_filename` ignores MaskEditor (clipspace) writes:
  - Select `characters/hero.png` → filename output is `hero.png`
  - MaskEditor saves to `clipspace-painted-xxx.png` → the dropdown updates, but `original_filename` stays `hero.png`
  - The filename output continues to return `hero.png`
- **`sync_maskeditor` on** — `original_filename` follows every source, including MaskEditor:
  - MaskEditor saves to `clipspace-painted-xxx.png` → `original_filename` updates to `clipspace-painted-xxx.png`

### Frontend Extension (Automatic)

The node includes a frontend extension that automatically syncs the `original_filename` widget when you change the dropdown. It's bundled with the custom node and loads automatically via `WEB_DIRECTORY`.

Without the extension, the `original_filename` field is still available but must be manually edited.

- The node recursively lists all images in the input folder and its subfolders
- Images inside `clipspace`, `3d`, `pasted`, and any hidden (starting with `.`) folders are excluded from the **dropdown listing**
- Any file starting with `.` (e.g., `.DS_Store`) is also excluded from the listing
- However, if a downstream node (e.g., mask editor) passes an image path from an excluded folder, the node will still load it correctly

## Based On

- [ComfyUI LoadImage Node](https://github.com/comfyanonymous/ComfyUI/blob/master/nodes.py)
