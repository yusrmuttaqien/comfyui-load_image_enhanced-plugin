import { app } from "../../scripts/app.js";

// Matches ComfyUI MaskEditor output filenames, e.g.
// "clipspace-painted-masked-1700000000000.png", "clipspace-mask-....png", etc.
// The native MaskEditor repoints the `image` widget at one of these on save.
const CLIPSACE_PATTERN = /^clipspace-(painted-masked|mask|paint|painted)-/;

app.registerExtension({
  name: "LoadImageEnhanced.FilenameSync",

  async beforeRegisterNodeDef(nodeType, nodeData, app) {
    if (nodeType.comfyClass !== "LoadImageEnhanced") {
      return;
    }

    const origOnCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      const result = origOnCreated?.apply(this, arguments);

      const imageWidget = this.widgets.find((w) => w.name === "image");
      const filenameWidget = this.widgets.find(
        (w) => w.name === "original_filename"
      );
      const syncWidget = this.widgets.find((w) => w.name === "sync_maskeditor");

      if (imageWidget && filenameWidget) {
        const origCallback = imageWidget.callback;
        imageWidget.callback = (value, ...args) => {
          if (value && typeof value === "string") {
            // Strip ComfyUI's "[input]"/"[output]" suffix, then take the basename.
            const clean = value.replace(/\s*\[(input|output)\]\s*$/, "");
            const newFilename = clean.split(/[\/\\]/).pop();
            const isClipspace = CLIPSACE_PATTERN.test(newFilename);

            // sync_maskeditor:
            //   true  -> "always sync": follow every source (incl. MaskEditor)
            //   false -> "sync only non-clipspace": skip MaskEditor writes
            const syncMaskeditor = syncWidget ? syncWidget.value : false;
            if (syncMaskeditor || !isClipspace) {
              filenameWidget.value = newFilename;
            }
          }
          return origCallback?.apply(this, args);
        };
      }

      return result;
    };
  },
});
