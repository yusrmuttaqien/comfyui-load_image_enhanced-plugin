import { app } from "../../scripts/app.js";

// Matches ComfyUI MaskEditor output filenames, e.g.
// "clipspace-painted-masked-1700000000000.png", "clipspace-mask-....png", etc.
// The native MaskEditor repoints the `image` widget at one of these on save.
const CLIPSACE_PATTERN = /^clipspace-(painted-masked|mask|paint|painted)-/;

// Strip ComfyUI's " [input]"/" [output]" suffix (leading space included).
function stripTypeSuffix(value) {
  return value.replace(/\s*\[(input|output)\]\s*$/, "");
}

// Check if a value is a clipspace filename (after stripping type suffix).
function isClipspaceValue(value) {
  if (typeof value !== "string") return false;
  const clean = stripTypeSuffix(value);
  return CLIPSACE_PATTERN.test(clean.split(/[\\/]/).pop());
}

// Add a value to the widget's combo options if not already present.
// This ensures the frontend's missing-media check passes for runtime-created
// files (e.g. MaskEditor saves) that are not in the static dropdown list.
function ensureInComboOptions(widget, value) {
  const values = widget && widget.options && widget.options.values;
  if (Array.isArray(values) && typeof value === "string" && value &&
      !values.includes(value)) {
    values.push(value);
  }
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

      // On reload, if the widget value is a clipspace path, add it to the
      // dropdown list to avoid a false "missing media" error. The repointed
      // path (clipspace/<filename>) may not exist on disk (the file is in the
      // input root), so it's not in the static dropdown list.
      if (imageWidget && isClipspaceValue(imageWidget.value)) {
        ensureInComboOptions(imageWidget, imageWidget.value);
      }

      if (imageWidget && filenameWidget) {
        const origCallback = imageWidget.callback;
        imageWidget.callback = (value, ...args) => {
          if (value && typeof value === "string") {
            const clean = stripTypeSuffix(value);
            const newFilename = clean.split(/[\\/]/).pop();
            const isClipspace = CLIPSACE_PATTERN.test(newFilename);

            // MaskEditor's programmatic save goes through writeImageWidgetValue,
            // which sets node.properties['image'] = value. A manual
            // dropdown/upload selection does not set that property, so we can
            // distinguish the two.
            const isMaskEditorSave = node.properties?.["image"] === value;

            if (isClipspace && isMaskEditorSave) {
              // MaskEditor save: repoint the widget to clipspace/<filename>
              // and refresh the dropdown list with the new entry.
              const repointed = `clipspace/${newFilename}`;
              ensureInComboOptions(imageWidget, repointed);
              imageWidget.value = repointed;
            } else {
              // Manual selection or non-MaskEditor source: ensure the value
              // is in the combo options.
              ensureInComboOptions(imageWidget, value);
            }

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
