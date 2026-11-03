import QtQuick
import QtQuick.Window
import Quickshell
import "../core"

Scope {
  id: root
  required property var view
  property int step: 0
  property var original: null
  property real deadline: Date.now() + 14000
  property int dragHistory: 0
  readonly property var editor: view.currentPage ? find(view.currentPage, "windowGapsEditor") : null
  signal completed
  function verify(condition, message) {
    if (!condition) {
      Qt.exit(1);
      throw new Error("Window gaps regression: " + message);
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
  Timer {
    interval: 110
    running: true
    repeat: true
    onTriggered: {
      root.verify(Date.now() < root.deadline, "spacing controls timed out");
      if (!Bridge.configurationActive) {
        root.view.Window.window.requestActivate();
        return;
      }
      if (Bridge.saving || Bridge.restoring || Bridge.hasPendingSettings || Bridge.afterSaving.length)
        return;
      switch (root.step) {
      case 0:
        root.original = {
          windowGapsEnabled: Bridge.settings.windowGapsEnabled,
          windowGapsIn: Bridge.settings.windowGapsIn,
          windowGapsOut: Object.assign({}, Bridge.settings.windowGapsOut),
          windowGapsLinked: Bridge.settings.windowGapsLinked
        };
        root.view.tab = 0;
        break;
      case 1:
        if (!root.editor)
          return;
        root.editor.setOuter(20, "");
        break;
      case 2:
        root.verify(Bridge.settings.windowGapsEnabled && Object.values(Bridge.settings.windowGapsOut).every(value => value === 20), "uniform spacing enables control and updates all edges");
        Bridge.undo();
        break;
      case 3:
        root.verify(!Bridge.settings.windowGapsEnabled && Bridge.settings.windowGapsOut.left === 8, "spacing and enabling undo together");
        Bridge.redo();
        break;
      case 4:
        root.verify(Bridge.settings.windowGapsEnabled && Bridge.settings.windowGapsOut.left === 20, "spacing can be redone");
        root.editor.setLinked(false);
        break;
      case 5:
        root.verify(!Bridge.settings.windowGapsLinked, "individual edge controls persist");
        root.editor.setOuter(33, "left");
        break;
      case 6:
        root.verify(Bridge.settings.windowGapsOut.left === 33 && Bridge.settings.windowGapsOut.top === 20 && Bridge.settings.windowGapsOut.right === 20, "changing one edge preserves the others");
        root.editor.setInner(6);
        break;
      case 7:
        root.verify(Bridge.settings.windowGapsIn === 6, "inner spacing persists");
        Bridge.undo();
        break;
      case 8:
        root.verify(Bridge.settings.windowGapsIn === 4 && Bridge.settings.windowGapsOut.left === 33, "undoing inner spacing preserves outer spacing");
        Bridge.restoreSettings("settings-reset-section", {
          section: "Appearance"
        });
        break;
      case 9:
        root.verify(!Bridge.settings.windowGapsEnabled && Bridge.settings.windowGapsLinked && Bridge.settings.windowGapsOut.top === 8, "Appearance reset includes compositor spacing");
        Bridge.undo();
        break;
      case 10:
        root.verify(Bridge.settings.windowGapsEnabled && !Bridge.settings.windowGapsLinked && Bridge.settings.windowGapsOut.left === 33, "undo reset restores asymmetric spacing");
        root.editor.setLinked(true);
        break;
      case 11:
        root.verify(Object.values(Bridge.settings.windowGapsOut).every(value => value === 20), "linking edges unifies the values");
        root.dragHistory = Bridge.settingsHistory.undo;
        Bridge.beginSettingsEdit();
        root.editor.setOuter(10, "");
        root.editor.setOuter(11, "");
        root.editor.setOuter(12, "");
        Bridge.endSettingsEdit();
        break;
      case 12:
        root.verify(Bridge.settingsHistory.undo === root.dragHistory + 1 && Bridge.settings.windowGapsOut.top === 12, "a spacing drag is one saved edit");
        Bridge.undo();
        break;
      case 13:
        root.verify(Bridge.settings.windowGapsOut.top === 20, "one undo restores the complete drag");
        Bridge.configure("windowGapsEnabled", false);
        break;
      case 14:
        root.verify(!Bridge.settings.windowGapsEnabled, "compositor spacing control can be disabled");
        Bridge.configureMany(root.original);
        break;
      default:
        stop();
        console.log("SMOKE window gaps COMPLETE");
        root.completed();
      }
      root.step++;
    }
  }
}
