import QtQuick
import QtQuick.Window
import Quickshell
import "../core"

Scope {
  id: root
  required property var view
  property int step: 0
  property double deadline: Date.now() + 16000
  property var original: null
  property var savedSettings: null
  readonly property var editor: view.currentPage
  signal completed

  function verify(condition, message) {
    if (!condition) {
      Qt.exit(1);
      throw new Error("Display regression: " + message);
    }
  }
  function find(item, name) {
    if (item.objectName === name)
      return item;
    for (const child of item.children || []) {
      const found = find(child, name);
      if (found)
        return found;
    }
    return null;
  }
  readonly property var fixtures: [
    {
      name: "eDP-1",
      description: "Pantalla del portátil",
      internal: true,
      enabled: true,
      mode: "1920x1080@60",
      modes: ["1920x1080@60", "1920x1080@40", "1280x720@60"],
      scale: 1.25,
      transform: 0,
      x: 0,
      y: 0,
      mirror: ""
    },
    {
      name: "HDMI-A-1",
      description: "Proyector de prueba",
      internal: false,
      enabled: true,
      mode: "1920x1080@60",
      modes: ["1920x1080@60", "1280x720@60", "1024x768@60"],
      scale: 1,
      transform: 0,
      x: 1536,
      y: 0,
      mirror: ""
    }
  ]
  Timer {
    interval: 120
    repeat: true
    running: true
    onTriggered: {
      root.verify(Date.now() < root.deadline, "display controls timed out");
      if (!Bridge.ready || Bridge.saving || Bridge.hasPendingSettings)
        return;
      switch (root.step) {
      case 0:
        root.original = Bridge.displays;
        root.savedSettings = JSON.stringify(Bridge.confirmedSettings);
        root.view.tab = root.view.pages.indexOf("Displays");
        break;
      case 1:
        if (!root.editor || root.editor.objectName !== "displaysEditor" || Bridge.isBusy("displays-refresh"))
          return;
        Bridge.displays = {
          available: true,
          outputs: root.fixtures,
          pending: null,
          error: "",
          notice: ""
        };
        break;
      case 2:
        root.verify(root.editor.draft.length === 2, "native connected outputs populate the editor");
        root.verify(root.editor.selectedName === "eDP-1", "first output is initially selected");
        if (Quickshell.env("HYPRLARP_DISPLAY_CAPTURE"))
          root.view.grabToImage(result => result.saveToFile(Quickshell.env("HYPRLARP_DISPLAY_CAPTURE")));
        root.editor.chooseResolution("1280x720");
        break;
      case 3:
        root.verify(root.editor.selected.mode === "1280x720@60" && root.editor.dirty, "resolution edits stay in a draft");
        root.verify(Bridge.displays.outputs[0].mode === "1920x1080@60", "editing does not mutate the active output snapshot");
        root.editor.selectedName = "HDMI-A-1";
        root.editor.relativeName = "eDP-1";
        root.editor.place("below");
        break;
      case 4:
        root.verify(root.editor.selected.x === 0 && root.editor.selected.y === 576, "relative placement uses the source's draft scale and resolution");
        root.editor.move("HDMI-A-1", 1030, 9);
        break;
      case 5:
        root.verify(root.editor.selected.x === 1024 && root.editor.selected.y === 0, "dragging snaps adjoining display edges");
        root.editor.update({
          mirror: "eDP-1"
        });
        break;
      case 6:
        root.verify(root.editor.selected.mirror === "eDP-1", "a mirror source can be chosen explicitly");
        root.verify(!root.find(root.editor, "projection-duplicate").enabled, "preview cannot change native projection modes");
        root.verify(JSON.stringify(Bridge.confirmedSettings) === root.savedSettings, "display drafts never alter appearance, binds or generic undo history");
        Bridge.displays = {
          available: true,
          outputs: root.fixtures,
          pending: {
            token: "fixture",
            deadline: Date.now() / 1000 + 20
          },
          error: "",
          notice: ""
        };
        break;
      case 7:
        root.verify(!root.find(root.editor, "testDisplayChanges").enabled, "pending trial prevents overlapping changes");
        root.verify(!root.editor.dirty && root.editor.draft[0].mode === "1920x1080@60", "trial snapshot refreshes the editor");
        Bridge.displays = {
          available: true,
          outputs: root.fixtures,
          pending: null,
          error: "",
          notice: ""
        };
        break;
      case 8:
        Bridge.displays = {
          available: true,
          outputs: [root.fixtures[0]],
          pending: null,
          error: "",
          notice: ""
        };
        break;
      case 9:
        root.verify(root.editor.draft.length === 1 && root.editor.selectedName === "eDP-1", "unplugging the selected projector returns to the laptop");
        Bridge.displays = root.original;
        root.view.tab = 0;
        break;
      default:
        stop();
        console.log("SMOKE displays COMPLETE");
        root.completed();
      }
      root.step++;
    }
  }
}
