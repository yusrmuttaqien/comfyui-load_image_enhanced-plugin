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


EXCLUDED_FOLDERS = {"clipspace", "3d", "pasted"}


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
                "original_filename": ("STRING", {"default": "", "custom_text": True}),
                # Frontend-only toggle (read by the JS extension, unused in load_image):
                #   False -> "sync only non-clipspace": original_filename ignores
                #           MaskEditor (clipspace-*) writes. [default]
                #   True  -> "always sync": original_filename follows every
                #           source, including MaskEditor outputs.
                "sync_maskeditor": ("BOOLEAN", {"default": False}),
            },
        }

    CATEGORY = "image"
    DESCRIPTION = (
        "Loads an image from the ComfyUI input directory and returns the image tensor, "
        "mask, and original filename. The dropdown lists all images recursively from "
        "subfolders (excluding hidden folders and 'clipspace'). Supports animated images "
        "(GIF, APNG) with multi-frame handling. Optionally specify a custom output "
        "filename via the 'original_filename' text field."
    )

    RETURN_TYPES = ("IMAGE", "MASK", "STRING")
    RETURN_NAMES = ("image", "mask", "filename")

    # ComfyUI Manager catalog entry:
    # {
    #   "author": "yusrmuttaqien",
    #   "title": "ComfyUI-LoadImageEnhanced",
    #   "reference": "https://github.com/yusrmuttaqien/ComfyUI-LoadImageEnhanced",
    #   "files": ["https://github.com/yusrmuttaqien/ComfyUI-LoadImageEnhanced"],
    #   "install_type": "git-clone",
    #   "description": "Loads an image from the ComfyUI input directory and returns the image tensor, mask, and original filename. The dropdown lists all images recursively from subfolders (excluding hidden folders and 'clipspace'). Supports animated images (GIF, APNG) with multi-frame handling. Optionally specify a custom output filename via the 'original_filename' text field."
    # }
    OUTPUT_TOOLTIPS = (
        "The loaded image tensor.",
        "The image mask (if available).",
        "The original filename of the loaded image.",
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

    def load_image(self, image: str, original_filename: str = "", sync_maskeditor: bool = False):
        input_dir = folder_paths.get_input_directory()
        image_path = self._resolve_image_path(image)

        img = node_helpers.pillow(Image.open, image_path)

        output_images = []
        output_masks = []
        w, h = None, None

        excluded_formats = ['MPO']

        for i in ImageSequence.Iterator(img):
            i = node_helpers.pillow(ImageOps.exif_transpose, i)

            if i.mode == 'I':
                i = i.point(lambda i: i * (1 / 255))
            image = i.convert("RGB")

            if len(output_images) == 0:
                w = image.size[0]
                h = image.size[1]

            if image.size[0] != w or image.size[1] != h:
                continue

            image = np.array(image).astype(np.float32) / 255.0
            image = torch.from_numpy(image)[None,]
            if 'A' in i.getbands():
                mask = np.array(i.getchannel('A')).astype(np.float32) / 255.0
                mask = 1. - torch.from_numpy(mask)
            elif i.mode == 'P' and 'transparency' in i.info:
                mask = np.array(i.convert('RGBA').getchannel('A')).astype(np.float32) / 255.0
                mask = 1. - torch.from_numpy(mask)
            else:
                mask = torch.zeros((64,64), dtype=torch.float32, device="cpu")
            output_images.append(image)
            output_masks.append(mask.unsqueeze(0))

        if len(output_images) > 1 and img.format not in excluded_formats:
            output_image = torch.cat(output_images, dim=0)
            output_mask = torch.cat(output_masks, dim=0)
        else:
            output_image = output_images[0]
            output_mask = output_masks[0]

        # Use the original_filename widget value if provided; otherwise fall back to current file's basename
        filename = original_filename if original_filename else os.path.basename(image_path)

        return (output_image, output_mask, filename)

    @classmethod
    def IS_CHANGED(s, image):
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
    def VALIDATE_INPUTS(s, image):
        if not folder_paths.exists_annotated_filepath(image):
            return "Invalid image file: {}".format(image)

        return True