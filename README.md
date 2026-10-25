# ComfyUI LoadImageEnhanced

This custom node extends ComfyUI's image loading functionality with a filename output and filename tracking.

## Features

### LoadImageEnhanced
- **Filename Output**: Returns the filename as a STRING output (the original LoadImage node has no filename output)
- **Filename Tracking**: Preserves the selected filename even when the image is modified by tools like MaskEditor (toggleable)
- **Sync MaskEditor Toggle**: `sync_maskeditor` input controls whether `filename` follows MaskEditor programmatic saves
- **Recursive Subfolder Listing**: Lists images from all subfolders (the original LoadImage node only lists the top-level input directory); excludes `3d`, `pasted`, and any folder/file starting with `.`

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
  - `filename` — Text field that stores the selected filename (editable by user)
  - `sync_maskeditor` — Toggle (default **off**): when off, `filename` ignores MaskEditor programmatic saves (but still follows manual dropdown/upload selections); when on, it follows every source including MaskEditor
- **Outputs**:
  - `image`: The loaded image tensor
  - `mask`: The image mask (if available)
  - `filename`: Always returns the value from the `filename` field. Falls back to the loaded file's basename only when the field is empty

## Requirements

- ComfyUI
- PIL (Pillow)
- PyTorch
- NumPy

## Notes

### Filename Tracking

The `filename` output always returns the value of the `filename` field, falling back to the loaded file's basename only when the field is empty. The field is automatically updated when you select a new image from the dropdown. Whether it also follows MaskEditor programmatic saves is controlled by the `sync_maskeditor` toggle:

- **`sync_maskeditor` off (default)** — `filename` ignores MaskEditor programmatic saves, but still follows manual selections:
  - Select `characters/hero.png` → filename output is `hero.png`
  - MaskEditor saves to `clipspace-painted-xxx.png` → the dropdown updates, but `filename` stays `hero.png`
  - Manually select `clipspace-painted-xxx.png` from the dropdown → `filename` updates to `clipspace-painted-xxx.png`
  - The filename output continues to return the field's value
- **`sync_maskeditor` on** — `filename` follows every source, including MaskEditor:
  - MaskEditor saves to `clipspace-painted-xxx.png` → `filename` updates to `clipspace-painted-xxx.png`

### Frontend Extension (Automatic)

The node includes a frontend extension that automatically syncs the `filename` field when you change the dropdown. It's bundled with the custom node and loads automatically via `WEB_DIRECTORY`.

Without the extension, the `filename` field is still available but must be manually edited.

- The node recursively lists all images in the input folder and its subfolders
- Images inside `3d`, `pasted`, and any hidden (starting with `.`) folders are excluded from the **dropdown listing**
- Any file starting with `.` (e.g., `.DS_Store`) is also excluded from the listing
- However, if a downstream node (e.g., mask editor) passes an image path from an excluded folder, the node will still load it correctly

## Based On

- [ComfyUI LoadImage Node](https://github.com/comfyanonymous/ComfyUI/blob/master/nodes.py)
