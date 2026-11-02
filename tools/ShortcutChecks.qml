import QtQuick
import QtQuick.Window
import Quickshell
import "../core"

Scope {
  id: root
  required property var view
  property int step: 0
  property var original: null
  property var originalState: Bridge.shortcutState
  property bool popupChecked: false
  property real deadline: Date.now() + 12000
  readonly property var page: view.currentPage
  signal completed
  function verify(condition, message) {
    if (!condition)
      throw new Error("Shortcut regression: " + message);
  }
  function input(item, name) {
    if (item.objectName === name)
      return item;
    for (const child of item.children || []) {
      const found = input(child, name);
      if (found)
        return found;
    }
    return null;
  }
  function existing() {
    return Bridge.settings.customBindings.find(item => item.id === "gui-test-bind");
  }
  Timer {
    interval: 110
    repeat: true
    running: true
    onTriggered: {
      root.verify(Date.now() < root.deadline, "editor checks timed out");
      if (!Bridge.configurationActive) {
        root.view.Window.window.requestActivate();
        return;
      }
      if (Bridge.saving || Bridge.restoring || Bridge.hasPendingSettings || Bridge.afterSaving.length)
        return;
      const page = root.page;
      switch (root.step) {
      case 0:
        root.original = {
          shortcuts: Object.assign({}, Bridge.settings.shortcuts),
          customBindings: Bridge.settings.customBindings.slice(),
          migrateNoctaliaBinds: Bridge.settings.migrateNoctaliaBinds
        };
        root.view.tab = 4;
        break;
      case 1:
        page.mode = "custom";
        page.edit({
          id: "gui-test-bind",
          name: "Terminal",
          chord: "SUPER CTRL ALT, T",
          command: "kitty"
        });
        break;
      case 2:
        if (!root.popupChecked) {
          root.input(page, "bindType").popup.open();
          root.popupChecked = true;
          return;
        }
        root.input(page, "bindType").popup.close();
        root.input(page, "bindName").text = "Terminal personal";
        root.input(page, "bindCommand").text = "kitty --title personal";
        page.updateDraft("locked", true);
        root.verify(root.input(page, "bindName").text === "Terminal personal", "changing flags preserves pending name edits");
        root.input(page, "bindChord").commit("SUPER CTRL ALT, Y");
        page.saveDraft();
        break;
      case 3:
        root.verify(root.existing() && root.existing().name === "Terminal personal" && root.existing().command === "kitty --title personal" && root.existing().locked, "custom command, flags and captured chord persist");
        Bridge.undo();
        break;
      case 4:
        root.verify(!root.existing(), "adding a bind can be undone");
        Bridge.redo();
        break;
      case 5:
        root.verify(!!root.existing(), "adding a bind can be redone");
        page.edit(root.existing());
        break;
      case 6:
        root.input(page, "bindCommand").text = "kitty --hold";
        page.saveDraft();
        break;
      case 7:
        root.verify(root.existing().command === "kitty --hold", "editing a bind preserves its identity");
        page.toggleCustom(root.existing());
        break;
      case 8:
        root.verify(!root.existing().enabled, "a custom bind can be disabled");
        Bridge.shortcutState = {
          available: true,
          conflicts: [],
          bindings: [
            {
              source: "|SUPER,T",
              chord: "SUPER, T",
              command: "kitty",
              submap: "",
              enabled: true
            }
          ]
        };
        page.mode = "current";
        page.personalize(Bridge.shortcutState.bindings[0], true);
        break;
      case 9:
        root.verify(Bridge.settings.customBindings.some(item => item.source === "|SUPER,T" && !item.enabled), "disabling an original bind stores an override");
        Bridge.undo();
        break;
      case 10:
        root.verify(!Bridge.settings.customBindings.some(item => item.source === "|SUPER,T"), "undo restores the original bind");
        page.personalize(Bridge.shortcutState.bindings[0], false);
        break;
      case 11:
        root.input(page, "bindChord").commit("SUPER ALT, T");
        page.saveDraft();
        break;
      case 12:
        root.verify(Bridge.settings.customBindings.some(item => item.source === "|SUPER,T" && item.type === "inherit" && item.chord.includes("T")), "moving an original bind preserves its Lua action");
        page.removeCustom("gui-test-bind");
        break;
      case 13:
        root.verify(!root.existing(), "a custom bind can be deleted");
        page.removeBuiltin("settings");
        break;
      case 14:
        root.verify(!Bridge.settings.shortcuts.settings, "a shell action can be removed");
        page.edit({
          type: "shell",
          action: "settings",
          chord: "SUPER, comma"
        }, true);
        break;
      case 15:
        page.saveDraft();
        break;
      case 16:
        root.verify(Bridge.settings.shortcuts.settings === "SUPER, comma", "a removed shell action can be added again");
        Bridge.shortcutState = {
          available: true,
          conflicts: [],
          bindings: [
            {
              source: "|ALT SUPER,M",
              chord: "SUPER ALT, M",
              command: "noctalia msg panel-toggle control-center",
              submap: "",
              enabled: true
            }
          ]
        };
        page.adoptCurrent();
        break;
      case 17:
        root.verify(Bridge.settings.shortcuts.control === "SUPER ALT, M", "existing Noctalia combinations can be adopted from Hyprland");
        Bridge.configureMany(root.original);
        Bridge.shortcutState = root.originalState;
        break;
      default:
        stop();
        console.log("SMOKE shortcuts COMPLETE");
        root.completed();
      }
      root.step++;
    }
  }
}
