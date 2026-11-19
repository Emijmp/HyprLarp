import QtQuick
import QtQuick.Controls
import Quickshell
import "../core"
import "../components"
import "../widgets/settings" as Settings
import "../core/accessibility.js" as Accessibility

Scope {
  id: root
  property int step: 0
  property var initialPanel: ({})
  property int scaleStep: 0
  function verify(condition, message) {
    if (!condition)
      throw new Error("Visual regression: " + message);
  }
  function find(item, name) {
    if (!item)
      return null;
    if (item.objectName === name)
      return item;
    for (const child of item.children || []) {
      const match = find(child, name);
      if (match)
        return match;
    }
    return null;
  }
  function panelEquals(settings, wanted) {
    return ["panelLayout", "panelStyle", "panelOpacity", "panelBlur"].every(key => settings[key] === wanted[key]);
  }
  FloatingWindow {
    implicitWidth: 980
    implicitHeight: 820
    color: Theme.surface
    ScrollView {
      anchors.fill: parent
      contentWidth: availableWidth
      contentHeight: page.implicitHeight
      Settings.AppearanceSettings {
        id: page
        width: parent.width
      }
    }
  }
  Timer {
    interval: 100
    running: true
    repeat: true
    onTriggered: {
      if (!Bridge.ready || !Bridge.connected || Bridge.saving || Bridge.hasPendingSettings || Bridge.queuedSettingsOperation)
        return;
      switch (root.step) {
      case 0:
        Bridge.configurationWindow("visual-check", true);
        root.initialPanel = Object.assign({}, page.panelDraft.saved);
        page.editPanel("panelLayout", "sidebar");
        page.editPanel("panelOpacity", .42);
        root.verify(page.panelPreviewPending, "editing marks the local draft");
        root.verify(root.panelEquals(Bridge.settings, root.initialPanel), "editing does not apply settings");
        page.applyPanel();
        root.step++;
        break;
      case 1:
        if (page.panelApplying || !Bridge.canUndo)
          return;
        root.verify(Bridge.confirmedSettings.panelLayout === "sidebar" && Bridge.confirmedSettings.panelOpacity === .42, "Apply is acknowledged by the real backend");
        root.verify(!page.panelPreviewPending, "acknowledged draft becomes clean");
        Bridge.undo();
        root.step++;
        break;
      case 2:
        root.verify(root.panelEquals(Bridge.confirmedSettings, root.initialPanel), "Undo restores the previous panel");
        root.verify(!page.panelPreviewPending && root.panelEquals(page.panelDraft.values, root.initialPanel), "Undo synchronizes the draft");
        page.editPanel("panelStyle", "glass");
        Bridge.configure("font", "Monospace");
        root.step++;
        break;
      case 3:
        root.verify(page.panelPreviewPending && page.panelDraft.values.panelStyle === "glass", "unrelated saved edits retain the pending draft");
        page.discardPanel();
        root.verify(!page.panelPreviewPending, "Discard restores saved values");
        page.editPanel("panelLayout", "centered");
        page.editPanel("panelStyle", "flat");
        page.editPanel("panelOpacity", .65);
        page.applyPanel();
        root.step++;
        break;
      case 4:
        if (page.panelApplying)
          return;
        root.verify(Bridge.confirmedSettings.panelStyle === "flat", "second design is applied");
        page.editPanel("panelStyle", "glass");
        Bridge.restoreSettings("settings-reset-section", {
          section: "Appearance"
        });
        root.step++;
        break;
      case 5:
        root.verify(Bridge.confirmedSettings.panelLayout === "floating" && Bridge.confirmedSettings.panelStyle === "standard", "Reset restores Appearance defaults");
        root.verify(!page.panelPreviewPending && page.panelDraft.values.panelStyle === "standard", "Reset synchronizes a previously edited draft");
        page.editPanel("panelLayout", "invalid-layout");
        page.applyPanel();
        root.step++;
        break;
      case 6:
        if (page.panelApplying)
          return;
        root.verify(!!page.panelDraft.error && page.panelPreviewPending, "rejected Apply remains editable and shows the failure");
        root.verify(Bridge.confirmedSettings.panelLayout === "floating", "rejected Apply preserves saved settings");
        page.discardPanel();
        root.verify(!page.panelDraft.error && !page.panelPreviewPending, "Discard clears a rejected draft");
        Bridge.setMany({
          accessibilityTextScale: 2,
          accessibilityMinimumFontSize: 18,
          accessibilityHighContrast: true,
          accessibilityLargeTargets: true,
          wallpaper: Quickshell.env("HYPRLARP_VISUAL_WALLPAPER")
        });
        root.step++;
        break;
      case 7:
        {
          const image = root.find(page, "preview-wallpaper");
          if (image.status === Image.Loading)
            return;
          root.verify(image.status === Image.Ready, "selected wallpaper loads in the preview, including special characters in its path");
          Bridge.perform("wallpaper-palette-extract");
          root.step++;
          break;
        }
      case 8:
        {
          if (Bridge.isBusy("wallpaper-palette-extract"))
            return;
          root.verify(Bridge.wallpaperPalette.path === Bridge.confirmedSettings.wallpaper && page.extractedWallpaperColors.length === 2, "real backend extraction reaches the color previews");
          for (const color of page.extractedWallpaperColors) {
            const safe = Theme.safeAccent(color);
            root.verify(Accessibility.contrast(safe, Theme.surface.toString()) >= 7, "dark extracted colors are adjusted for the current high-contrast surface");
          }
          const preview = root.find(page, "panel-design-preview");
          const card = root.find(page, "theme-preview-card");
          root.verify(preview && card, "both preview types are instantiated");
          root.verify(card.implicitHeight > 240, "theme cards grow with large text instead of clipping into a fixed height");
          for (const mode of ["floating", "centered", "sidebar"]) {
            preview.layoutMode = mode;
            const geometry = preview.surfaceGeometry;
            root.verify(geometry.x >= 0 && geometry.y >= 0 && geometry.x + geometry.width <= preview.logicalWidth + .1 && geometry.y + geometry.height <= preview.logicalHeight + .1, "scaled " + mode + " preview remains inside the monitor");
          }
          root.verify(Theme.onAccent.toString() === "#000000" || Theme.onAccent.toString() === "#ffffff", "filled actions use a contrast-aware foreground");
          Bridge.consume(JSON.stringify({
            type: "clipboard",
            data: Array.from({
              length: 24
            }, (_, index) => ({
                  id: String(index)
                }))
          }));
          for (let index = 0; index < 24; index++)
            Bridge.consume(JSON.stringify({
              type: "clipboard-thumbnail",
              data: {
                id: String(index),
                url: "image-" + index
              }
            }));
          root.verify(Object.keys(Bridge.clipboardThumbnails).length <= 16, "clipboard thumbnail memory is bounded");
          Bridge.consume(JSON.stringify({
            type: "clipboard",
            data: []
          }));
          root.verify(Object.keys(Bridge.clipboardThumbnails).length === 0, "removed clipboard entries release thumbnails");
          const prefix = Quickshell.env("HYPRLARP_VISUAL_CAPTURE");
          if (prefix) {
            preview.grabToImage(result => root.verify(result.saveToFile(prefix + "-panel.png"), "panel screenshot"));
            card.grabToImage(result => root.verify(result.saveToFile(prefix + "-theme.png"), "theme screenshot"));
          }
          root.step++;
          break;
        }
      default:
        Bridge.configurationWindow("visual-check", null);
        console.log("VISUAL COMPLETE");
        stop();
        Qt.quit();
      }
    }
  }
}
