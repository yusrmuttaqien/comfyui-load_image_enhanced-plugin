import os
import re
import hashlib
import numpy as np
import torch
from PIL import Image, ImageOps, ImageSequence
import folder_paths
import node_helpers

try:
    from comfy.comfy_types import IO, ComfyNodeABC, CheckLazyMixin
except ImportError:
    ComfyNodeABC = object  # fallback for older versions


EXCLUDED_FOLDERS = {"3d", "pasted"}


def _collect_images_recursive(input_dir):
    """Recursively collect image files from input directory, excluding certain subfolders."""
    image_files = []
    for root, dirs, files in os.walk(input_dir):
        # Filter out excluded and hidden directories in-place so os.walk skips them
        dirs[:] = sorted([d for d in dirs if d not in EXCLUDED_FOLDERS and not d.startswith(".")])

        for filename in files:
            # Skip hidden files (starting with ".")
            if filename.startswith("."):
                continue
            filepath = os.path.join(root, filename)
            # Create relative path from input_dir root
            rel_path = os.path.relpath(filepath, input_dir)
            image_files.append(rel_path)

    return image_files


class LoadImageEnhanced(ComfyNodeABC):
    @classmethod
    def INPUT_TYPES(s):
        input_dir = folder_paths.get_input_directory()
        all_files = _collect_images_recursive(input_dir)
        # Filter for image content types
        filtered_files = folder_paths.filter_files_content_types(all_files, ["image"])
        return {
            "required": {
                "image": (sorted(filtered_files), {"image_upload": True}),
                "filename": ("STRING", {"default": "", "custom_text": True}),
                # Frontend-only toggle (read by the JS extension, unused in load_image):
                #   False -> "sync except MaskEditor saves": filename follows
                #           manual selections (dropdown/upload) and non-clipspace
                #           sources, but ignores MaskEditor programmatic saves.
                #           [default]
                #   True  -> "always sync": filename follows every source,
                #           including MaskEditor programmatic saves.
                "sync_maskeditor": ("BOOLEAN", {"default": False}),
            },
        }

    CATEGORY = "image"
    DESCRIPTION = (
        "Loads an image from the ComfyUI input directory and returns the image tensor, "
        "mask, and filename. The dropdown lists all images recursively from subfolders "
        "(excluding hidden folders). Supports animated images (GIF, APNG) with "
        "multi-frame handling. Optionally specify a custom output filename via the "
        "'filename' text field."
    )

    RETURN_TYPES = ("IMAGE", "MASK", "STRING")
    RETURN_NAMES = ("image", "mask", "filename")

    # ComfyUI Manager catalog entry:
    # {
    #   "author": "yusrmuttaqien",
    #   "title": "ComfyUI-LoadImageEnhanced",
    #   "reference": "https://github.com/yusrmuttaqien/comfyui-load_image_enhanced-plugin",
    #   "files": ["https://github.com/yusrmuttaqien/comfyui-load_image_enhanced-plugin"],
    #   "install_type": "git-clone",
    #   "description": "Loads an image from the ComfyUI input directory and returns the image tensor, mask, and filename. The dropdown lists all images recursively from subfolders (excluding hidden folders). Supports animated images (GIF, APNG) with multi-frame handling. Optionally specify a custom output filename via the 'filename' text field."
    # }
    OUTPUT_TOOLTIPS = (
        "The loaded image tensor.",
        "The image mask (if available).",
        "Always returns the value from the 'filename' field. Falls back to the loaded file's basename only when the field is empty.",
    )
    FUNCTION = "load_image"

    def _resolve_image_path(self, image):
        """Resolve an image reference to a filesystem path."""
        input_dir = folder_paths.get_input_directory()

        # Strip ComfyUI's [input] annotation suffix if present (added by some internal routing)
        clean_image = re.sub(r'\s*\[input\]\s*$', '', image).strip()

        # Strategy 1: normal path from dropdown (e.g., "characters/hero.png")
        candidate = os.path.join(input_dir, clean_image)
        if os.path.isfile(candidate):
            return candidate

        # Strategy 2: treat the reference as a direct relative path (handles clipspace/ etc.)
        if os.path.isfile(clean_image):
            return clean_image

        # Strategy 3: search for the file anywhere under input_dir (handles nested subfolders)
        target_basename = os.path.basename(clean_image)
        for root, dirs, files in os.walk(input_dir):
            if target_basename in files:
                return os.path.join(root, target_basename)

        # Fallback: return original string and let PIL raise a descriptive error
        return image

    def _load_image(self, image_path):
        """Load an image file into (image_tensor, mask_tensor)."""
        img = node_helpers.pillow(Image.open, image_path)

        output_images = []
        output_masks = []
        w, h = None, None

        excluded_formats = ['MPO']

        for i in ImageSequence.Iterator(img):
            i = node_helpers.pillow(ImageOps.exif_transpose, i)

            if i.mode == 'I':
                i = i.point(lambda i: i * (1 / 255))
            rgb = i.convert("RGB")

            if len(output_images) == 0:
                w = rgb.size[0]
                h = rgb.size[1]

            if rgb.size[0] != w or rgb.size[1] != h:
                continue

            tensor = np.array(rgb).astype(np.float32) / 255.0
            tensor = torch.from_numpy(tensor)[None,]
            if 'A' in i.getbands():
                mask = np.array(i.getchannel('A')).astype(np.float32) / 255.0
                mask = 1. - torch.from_numpy(mask)
            elif i.mode == 'P' and 'transparency' in i.info:
                mask = np.array(i.convert('RGBA').getchannel('A')).astype(np.float32) / 255.0
                mask = 1. - torch.from_numpy(mask)
            else:
                mask = torch.zeros((64, 64), dtype=torch.float32, device="cpu")
            output_images.append(tensor)
            output_masks.append(mask.unsqueeze(0))

        if len(output_images) > 1 and img.format not in excluded_formats:
            image = torch.cat(output_images, dim=0)
            mask = torch.cat(output_masks, dim=0)
        else:
            image = output_images[0]
            mask = output_masks[0]

        return image, mask

    def load_image(self, image: str, filename: str = "", sync_maskeditor: bool = False):
        image_path = self._resolve_image_path(image)

        output_image, output_mask = self._load_image(image_path)

        # The filename output always returns the 'filename' field value; only
        # when the field is empty does it fall back to the loaded file's basename.
        output_filename = filename if filename else os.path.basename(image_path)

        return (output_image, output_mask, output_filename)

    @classmethod
    def IS_CHANGED(s, image, **kwargs):
        # Use the same resolution logic to get a valid file path
        temp_node = s()
        image_path = temp_node._resolve_image_path(image)
        try:
            m = hashlib.sha256()
            with open(image_path, 'rb') as f:
                m.update(f.read())
            return m.digest().hex()
        except (FileNotFoundError, PermissionError):
            # If we can't read the file for hashing, return a hash of the image ref string
            return hashlib.sha256(image.encode()).hexdigest()

    @classmethod
    def VALIDATE_INPUTS(s, image, **kwargs):
        # Use the same resolution logic as load_image/IS_CHANGED so that files
        # in subfolders (e.g. MaskEditor's clipspace/ output on older ComfyUI
        # versions) pass validation the same way they load.
        temp_node = s()
        image_path = temp_node._resolve_image_path(image)
        if not os.path.isfile(image_path):
            return "Invalid image file: {}".format(image)

        return True