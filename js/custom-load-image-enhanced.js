import { app } from "../../scripts/app.js";

// Matches ComfyUI MaskEditor output filenames, e.g.
// "clipspace-painted-masked-1700000000000.png", "clipspace-mask-....png", etc.
// The native MaskEditor repoints the `image` widget at one of these on save.
const CLIPSACE_PATTERN = /^clipspace-(painted-masked|mask|paint|painted)-/;

// ComfyUI's missing-media check flags a media input as "missing" when the
// widget value is not present in the widget's combo options (the dropdown
// list). clipspace files are excluded from our dropdown listing AND are
// created at runtime (after the static option list is built), so a persisted
// clipspace value is never in the options and gets flagged after a reload.
// Pushing the current value into options.values makes the check pass without
// cluttering the dropdown with every historical clipspace file.
function ensureInComboOptions(widget, value) {
  const values = widget && widget.options && widget.options.values;
  if (Array.isArray(values) && typeof value === "string" && value &&
      !values.includes(value)) {
    values.push(value);
  }
}

function isClipspaceValue(value) {
  if (typeof value !== "string") return false;
  const clean = value.replace(/\s*\[(input|output)\]\s*$/, "");
  return CLIPSACE_PATTERN.test(clean.split(/[\\/]/).pop());
}

app.registerExtension({
  name: "LoadImageEnhanced.FilenameSync",

  async beforeRegisterNodeDef(nodeType, nodeData, app) {
    if (nodeType.comfyClass !== "LoadImageEnhanced") {
      return;
    }

    const origOnCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      const result = origOnCreated?.apply(this, arguments);

      const node = this;
      const imageWidget = this.widgets.find((w) => w.name === "image");
      const filenameWidget = this.widgets.find((w) => w.name === "filename");
      const syncWidget = this.widgets.find((w) => w.name === "sync_maskeditor");

      // On reload the persisted clipspace value is not in the static combo
      // options, so add it back to avoid a false "missing media" error.
      if (imageWidget && isClipspaceValue(imageWidget.value)) {
        ensureInComboOptions(imageWidget, imageWidget.value);
      }

      if (imageWidget && filenameWidget) {
        const origCallback = imageWidget.callback;
        imageWidget.callback = (value, ...args) => {
          if (value && typeof value === "string") {
            // Strip ComfyUI's " [input]"/" [output]" suffix (leading space included),
            // then take the basename.
            const clean = value.replace(/\s*\[(input|output)\]\s*$/, "");
            const newFilename = clean.split(/[\/\\]/).pop();
            const isClipspace = CLIPSACE_PATTERN.test(newFilename);

            // Keep the runtime clipspace value in the combo options so the
            // frontend's missing-media check passes.
            if (isClipspace) {
              ensureInComboOptions(imageWidget, value);
            }

            // MaskEditor's programmatic save goes through writeImageWidgetValue,
            // which sets node.properties['image'] = value. A manual
            // dropdown/upload selection does not set that property, so we can
            // distinguish the two.
            const isMaskEditorSave = node.properties?.["image"] === value;

            // sync_maskeditor:
            //   true  -> "always sync": follow every source (incl. MaskEditor
            //           programmatic saves)
            //   false -> "sync except MaskEditor saves": follow manual
            //           selections (dropdown/upload) and non-clipspace sources,
            //           but ignore MaskEditor programmatic saves.
            const syncMaskeditor = syncWidget ? syncWidget.value : false;
            if (syncMaskeditor || !isClipspace || !isMaskEditorSave) {
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
