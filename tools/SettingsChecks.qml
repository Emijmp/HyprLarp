import QtQuick
import QtQuick.Window
import Quickshell
import "../core"

Scope {
  id: root
  required property var view
  property bool running: false
  property int step: 0
  property real deadline: 0
  property string original: ""
  property string baseline: ""
  property string preset: ""
  property string custom: ""
  property string editedCustom: ""
  property string beforePending: ""
  property string beforeReset: ""
  property string beforeRejected: ""
  property int dragUndoCount: 0
  property int dragSize: 0
  property string beforeOutside: ""
  property int outsideUndoCount: 0
  signal completed
  function snapshot() {
    return JSON.stringify(Bridge.settings);
  }
  function verify(condition, message) {
    if (!condition)
      throw new Error("Settings regression: " + message);
  }
  readonly property var actions: [() => {
      root.view.tab = 0;
      root.original = root.snapshot();
      Bridge.resetSettings();
    }, () => {
      root.verify(Bridge.settings.theme === "amoled" && Bridge.settings.barPosition === "top", "reset defaults");
      Bridge.undo();
    }, () => {
      root.verify(root.snapshot() === root.original, "undo reset restores every setting");
      Bridge.redo();
    }, () => {
      root.baseline = root.snapshot();
      Theme.apply("oxocarbon");
      Bridge.flush();
    }, () => {
      root.verify(Bridge.settings.theme === "oxocarbon" && String(Theme.accent) === "#3ddbd9", "preset colors");
      root.preset = root.snapshot();
      Bridge.undo();
    }, () => {
      root.verify(root.snapshot() === root.baseline, "undo theme and accent together");
      Bridge.redo();
    }, () => {
      root.verify(root.snapshot() === root.preset, "redo theme");
      Theme.customize();
      Bridge.flush();
    }, () => {
      root.verify(Bridge.settings.theme === "custom" && String(Theme.background) === "#161616", "copy preset into custom");
      root.custom = root.snapshot();
      Theme.setCustom("background", "#101820");
      Theme.setCustom("accent", "#e8d5b5");
      Bridge.flush();
    }, () => {
      root.verify(String(Theme.background) === "#101820" && String(Theme.accent) === "#e8d5b5", "custom roles apply live");
      root.editedCustom = root.snapshot();
      Bridge.undo();
    }, () => {
      root.verify(root.snapshot() === root.custom, "undo custom colors atomically");
      Bridge.redo();
    }, () => {
      root.verify(root.snapshot() === root.editedCustom, "redo custom palette");
      Theme.apply("tokyonight");
      Bridge.flush();
    }, () => {
      root.verify(Bridge.settings.theme === "tokyonight", "switch away from custom");
      Theme.apply("custom");
      Bridge.flush();
    }, () => {
      root.verify(String(Theme.background) === "#101820", "custom palette retained after switching");
      root.dragUndoCount = Bridge.settingsHistory.undo;
      root.dragSize = Bridge.settings.barSize;
      Bridge.beginSettingsEdit();
      Bridge.configure("barSize", 40);
      dragTimer.start();
    }, () => {
      root.verify(Bridge.settings.barSize === 44 && Bridge.settingsHistory.undo === root.dragUndoCount + 1, "one undo entry for a complete slider drag");
      Bridge.undo();
    }, () => {
      root.verify(Bridge.settings.barSize === root.dragSize, "undo complete slider drag");
      root.beforePending = root.snapshot();
      Bridge.configure("barOpacity", 0.6);
      Bridge.undo();
    }, () => {
      root.verify(root.snapshot() === root.beforePending, "undo flushes and reverts pending changes");
      Bridge.configure("font", "Sans Serif");
      Bridge.flush();
      Bridge.configure("font", "JetBrains Mono");
    }, () => {
      root.verify(Bridge.settings.font === "JetBrains Mono", "older save acknowledgment keeps the latest edit");
      Bridge.undo();
    }, () => {
      root.verify(Bridge.settings.font === "Sans Serif", "undo latest serialized write");
      Bridge.redo();
    }, () => {
      root.verify(Bridge.settings.font === "JetBrains Mono", "redo latest serialized write");
      root.beforeReset = root.snapshot();
      root.view.confirmReset = true;
      Bridge.resetSettings();
    }, () => {
      root.view.confirmReset = false;
      root.verify(Bridge.settings.theme === "amoled" && Bridge.settings.font === "Inter", "reset custom configuration");
      Bridge.undo();
    }, () => {
      root.verify(root.snapshot() === root.beforeReset, "undo reset preserves custom palette");
      root.beforeRejected = root.snapshot();
      Bridge.configure("barSize", 22);
      Bridge.undo();
    }, () => {
      root.verify(root.snapshot() === root.beforeRejected, "rejected edit does not undo a preceding valid change");
      Bridge.message = "";
      const light = {
        name: "Prueba clara",
        background: "#f4f4f4",
        surface: "#ffffff",
        raised: "#dddddd",
        moduleSurface: "#efefef",
        border: "#161616",
        separator: "#b0b0b0",
        text: "#161616",
        muted: "#525252",
        accent: "#0f62fe",
        danger: "#da1e28"
      };
      Bridge.configureMany({
        theme: "custom",
        customPalette: light,
        accent: light.accent
      });
      Bridge.flush();
    }, () => {
      root.verify(String(Theme.surface) === "#ffffff" && String(Theme.text) === "#161616", "custom light palette");
      Bridge.resetSettings();
    }, () => {
      Bridge.configure("barSpacing", 12);
      Bridge.flush();
    }, () => {
      root.beforeOutside = root.snapshot();
      root.outsideUndoCount = Bridge.settingsHistory.undo;
      outside.visible = true;
      outsideFocus.Window.window.requestActivate();
    }, () => {
      root.verify(!Bridge.configurationActive && !root.view.configurationFocused, "configuration loses focus to another window");
      root.verify(!Bridge.canUndo && !Bridge.canRedo && !Bridge.canReset, "configuration actions disabled outside their window");
      Bridge.undo();
      Bridge.redo();
      Bridge.resetSettings();
      Bridge.restoreSettings("settings-reset");
      root.verify(root.snapshot() === root.beforeOutside && !Bridge.saving, "calls outside configuration do not modify settings");
      Bridge.set("doNotDisturb", true);
      Bridge.flush();
    }, () => {
      root.verify(Bridge.settings.doNotDisturb && Bridge.settingsHistory.undo === root.outsideUndoCount, "shell changes excluded from configuration history");
      outside.visible = false;
      root.view.Window.window.requestActivate();
    }, () => {
      root.verify(Bridge.configurationActive, "configuration actions resume on focus");
      Bridge.undo();
    }, () => {
      root.verify(Bridge.settings.barSpacing === 10 && Bridge.settings.doNotDisturb, "undo keeps external shell changes");
      Bridge.redo();
    }, () => {
      root.verify(Bridge.settings.barSpacing === 12 && Bridge.settings.doNotDisturb, "redo keeps external shell changes");
      Bridge.configure("barSize", 40);
      Bridge.set("doNotDisturb", false);
      Bridge.configure("barSpacing", 14);
      Bridge.flush();
    }, () => {
      root.verify(Bridge.settings.barSize === 40 && Bridge.settings.barSpacing === 14 && !Bridge.settings.doNotDisturb, "mixed edit sources retain write order");
      Bridge.undo();
    }, () => {
      root.verify(Bridge.settings.barSize === 40 && Bridge.settings.barSpacing === 12 && !Bridge.settings.doNotDisturb, "undo latest configuration batch only");
      Bridge.undo();
    }, () => {
      root.verify(Bridge.settings.barSize === 34 && !Bridge.settings.doNotDisturb, "undo first batch without undoing the shell batch");
      root.beforeOutside = root.snapshot();
      root.view.visible = false;
      root.verify(!Bridge.canUndo && !Bridge.canReset, "hidden configuration cannot restore settings");
      Bridge.undo();
      Bridge.resetSettings();
      root.verify(root.snapshot() === root.beforeOutside, "hidden configuration leaves settings intact");
      root.view.visible = true;
    }, () => {
      Bridge.resetSettings();
    }, () => {
      Bridge.configure("barSpacing", 17);
      Bridge.flush();
      Bridge.set("doNotDisturb", true);
      Bridge.configure("barSize", 42);
      Bridge.performConfig("profile-save", {
        name: "Queue check"
      });
    }, () => {
      root.verify(Bridge.library.profiles.includes("Queue check"), "profile action waits for every queued write");
      Bridge.configure("barSpacing", 20);
      Bridge.restoreSettings("profile-apply", {
        name: "Queue check"
      });
    }, () => {
      root.verify(Bridge.settings.barSpacing === 17 && Bridge.settings.barSize === 42, "profile contains latest configuration from multiple queued batches");
      Bridge.undo();
    }, () => {
      root.verify(Bridge.settings.barSpacing === 20, "applying a profile is undoable");
      Bridge.restoreSettings("settings-reset-section", {
        section: "Bar"
      });
    }, () => {
      root.verify(Bridge.settings.barSpacing === 10 && Bridge.settings.barSize === 34, "section reset applies default geometry");
      Bridge.undo();
    }, () => {
      root.verify(Bridge.settings.barSpacing === 20 && Bridge.settings.barSize === 42, "section reset is undoable");
      BarEditor.target = "Virtual-1";
      BarEditor.set("barPosition", "left");
      ModuleCatalog.place("clock", "end");
    }, () => {
      root.verify(Bridge.settings.barPosition === "top" && BarEditor.settings.barPosition === "left", "monitor settings stay independent");
      root.verify(BarEditor.settings.barZones.end.includes("clock") && Bridge.settings.barZones.center.includes("clock"), "monitor module zones stay independent");
      BarEditor.inherit();
      BarEditor.target = "";
      Bridge.performConfig("profile-delete", {
        name: "Queue check"
      });
      Bridge.resetSettings();
    }, () => {
      Bridge.configure("radius", 6);
      Theme.setRadius("bar", 0);
      Theme.setRadius("workspace", 2);
      Theme.setRadius("button", 8);
      Bridge.flush();
    }, () => {
      root.verify(Theme.radius === 6 && Theme.radiusFor("panel") === 6 && Theme.radiusFor("bar") === 0 && Theme.radiusFor("workspace") === 2 && Theme.radiusFor("button") === 8, "corner radii inherit independently and preserve zero overrides");
      Theme.setRadius("button", null);
      Bridge.flush();
    }, () => {
      root.verify(Theme.radiusFor("button") === 6 && Theme.radiusFor("workspace") === 2, "restoring corner inheritance preserves other elements");
      Bridge.undo();
    }, () => {
      root.verify(Theme.radiusFor("button") === 8, "corner inheritance change is undoable");
      Bridge.undo();
    }, () => {
      root.verify(Theme.radius === 0 && Object.keys(Bridge.settings.cornerRadii).length === 0, "radius edits undo as one configuration change");
      Bridge.configureMany({
        nightLightTemperature: 3500,
        nightLightSchedule: true,
        nightLightStart: "22:00",
        nightLightEnd: "06:00",
        osdTimeout: 2200
      });
      Bridge.flush();
    }, () => {
      root.verify(Bridge.settings.nightLightTemperature === 3500 && Bridge.settings.osdTimeout === 2200 && Bridge.settings.nightLightSchedule, "night and OSD preferences persist together");
      Bridge.undo();
    }, () => {
      root.verify(Bridge.settings.nightLightTemperature === 4000 && Bridge.settings.osdTimeout === 1500 && !Bridge.settings.nightLightSchedule, "night and OSD configuration is undoable");
      Bridge.redo();
    }, () => {
      root.verify(Bridge.settings.nightLightStart === "22:00" && Bridge.settings.osdTimeout === 2200, "night and OSD preferences redo");
      Bridge.restoreSettings("settings-reset-section", {
        section: "General"
      });
    }, () => {
      root.verify(!Bridge.settings.nightLightSchedule && Bridge.settings.nightLightTemperature === 4000 && Bridge.settings.osdTimeout === 1500, "General reset includes night and OSD");
      Bridge.undo();
    }, () => {
      root.verify(Bridge.settings.nightLightSchedule && Bridge.settings.nightLightTemperature === 3500 && Bridge.settings.osdTimeout === 2200, "General reset is undoable for night and OSD");
      Theme.setDetail("panelCorners", false);
      Theme.setDetail("sectionMarks", false);
      Bridge.flush();
    }, () => {
      root.verify(!Theme.detail("panelCorners") && !Theme.detail("sectionMarks") && Theme.detail("headerIcons"), "decorative details are independent");
      Bridge.undo();
    }, () => {
      root.verify(Theme.detail("panelCorners") && Theme.detail("sectionMarks"), "decoration changes undo as a group");
      Bridge.redo();
    }, () => {
      root.verify(!Theme.detail("panelCorners") && !Theme.detail("sectionMarks"), "decoration changes redo");
      Bridge.restoreSettings("settings-reset-section", {
        section: "Appearance"
      });
    }, () => {
      root.verify(Theme.detail("panelCorners") && Theme.detail("sectionMarks"), "Appearance reset restores decorations");
      Bridge.resetSettings();
    }]
  onRunningChanged: if (running) {
    deadline = Date.now() + 15000;
    view.Window.window.requestActivate();
  }
  FloatingWindow {
    id: outside
    title: "Settings scope test"
    visible: false
    implicitWidth: 200
    implicitHeight: 100
    Item {
      id: outsideFocus
      anchors.fill: parent
    }
  }
  Timer {
    id: dragTimer
    interval: 400
    onTriggered: {
      root.verify(Bridge.settingsHistory.undo === root.dragUndoCount, "held slider does not save intermediate steps");
      Bridge.configure("barSize", 44);
      Bridge.endSettingsEdit();
    }
  }
  Timer {
    interval: 80
    running: root.running
    repeat: true
    onTriggered: {
      root.verify(Date.now() < root.deadline, "history checks timed out");
      if (root.step === 0 && !Bridge.configurationActive) {
        root.view.Window.window.requestActivate();
        return;
      }
      if (Bridge.saving || Bridge.restoring || Bridge.settingsEditDepth > 0 || Bridge.hasPendingSettings || Bridge.afterSaving.length || Object.values(Bridge.busyActions).some(count => count > 0))
        return;
      if (root.step < root.actions.length) {
        console.log("SMOKE settings history", root.step);
        root.actions[root.step++]();
      } else {
        root.running = false;
        console.log("SMOKE settings history COMPLETE");
        root.completed();
      }
    }
  }
}
