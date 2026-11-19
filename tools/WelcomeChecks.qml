import QtQuick
import QtQuick.Window
import QtTest
import Quickshell
import "../core"
import "../widgets"
import "../core/focus.js" as Focus

Scope {
  id: root
  property int step: 0
  property double deadline: Date.now() + 15000
  property var original: ({})
  property string expectedLayout: ""
  property int finishedCount: 0
  signal completed
  function verify(condition, message) {
    if (!condition)
      throw new Error("First-run regression: " + message);
  }
  function find(item, name) {
    if (!item)
      return null;
    if (item.objectName === name)
      return item;
    for (const child of item.children || []) {
      const result = find(child, name);
      if (result)
        return result;
    }
    return item.item ? find(item.item, name) : null;
  }
  function checkFocusedControlVisible() {
    const control = Focus.first(find(welcome, "welcome-large-targets"));
    const scroll = find(welcome, "welcome-scroll");
    const y = control.mapToItem(scroll, 0, 0).y;
    verify(control.activeFocus && scroll.contentItem.contentY > 0, "Tab focus scrolls the enlarged form");
    verify(y >= -1 && y + control.height <= scroll.availableHeight + 1, "focused control is visible at text scale " + Bridge.settings.accessibilityTextScale + ": " + [y, control.height, scroll.availableHeight, scroll.contentItem.contentY, scroll.contentHeight, scroll.contentItem.contentHeight, find(welcome, "welcome-pages").implicitHeight, find(welcome, "welcome-pages").height].join(","));
  }
  FloatingWindow {
    id: window
    title: "HyprLarp · Prueba de primeros pasos"
    implicitWidth: 760
    implicitHeight: 600
    color: Theme.surface
    WelcomeContent {
      id: welcome
      anchors.fill: parent
      onFinished: root.finishedCount++
    }
    TestEvent {
      id: keys
    }
  }
  Timer {
    interval: 120
    repeat: true
    running: true
    onTriggered: {
      if (Date.now() > root.deadline)
        throw new Error("First-run regression: timeout in step " + root.step + ": " + welcome.error);
      if (!Bridge.ready || !Bridge.connected || Bridge.saving || Bridge.hasPendingSettings)
        return;
      switch (root.step) {
      case 0:
        root.original = JSON.parse(JSON.stringify(Bridge.settings));
        root.expectedLayout = Bridge.settings.panelLayout === "centered" ? "sidebar" : "centered";
        root.verify(Bridge.releaseVersion.length > 0, "backend provides the release version");
        root.verify(Object.keys(welcome.updates()).length === 0, "opening keeps every preference");
        welcome.edit("panelLayout", root.expectedLayout);
        root.verify(JSON.stringify(Bridge.settings) === JSON.stringify(root.original), "preview never mutates the live configuration");
        root.verify(Object.keys(welcome.updates()).join() === "panelLayout", "only the touched key is sent");
        welcome.edit("theme", Bridge.settings.theme);
        root.verify(welcome.draft.themeScheduleEnabled === false, "explicit theme choice changes the schedule only in the draft");
        root.verify(JSON.stringify(Bridge.settings) === JSON.stringify(root.original), "theme choice remains local");
        welcome.draft = {};
        root.verify(Object.keys(welcome.updates()).length === 0, "discarding choices keeps the current schedule");
        welcome.step = 1;
        welcome.edit("panelLayout", root.expectedLayout);
        break;
      case 1:
        welcome.step = 2;
        welcome.edit("accessibilityTextScale", 1.6);
        break;
      case 2:
        welcome.step = 3;
        root.verify(welcome.changed.length === (root.original.accessibilityTextScale === 1.6 ? 1 : 2), "summary includes only actual changes");
        welcome.submit();
        root.verify(welcome.submitting, "completion waits for the backend");
        break;
      case 3:
        if (welcome.submitting || root.finishedCount < 1)
          return;
        root.verify(Bridge.settings.panelLayout === root.expectedLayout && Bridge.settings.accessibilityTextScale === 1.6, "completion saves the reviewed selection");
        root.verify(Bridge.settings.shortcuts.lock === root.original.shortcuts.lock, "completion preserves shortcuts");
        root.verify(Bridge.onboarding.status === "completed", "completion is acknowledged separately from preferences");
        welcome.step = 2;
        Focus.first(root.find(welcome, "welcome-large-targets")).forceActiveFocus();
        root.verify(keys.keyClick(Qt.Key_Backtab, Qt.ShiftModifier, 0) && keys.keyClick(Qt.Key_Tab, 0, 0), "keyboard traverses the form controls");
        break;
      case 4:
        root.checkFocusedControlVisible();
        root.find(welcome, "welcome-next").forceActiveFocus();
        root.verify(keys.keyClick(Qt.Key_Return, 0, 0) && welcome.step === 3 && !welcome.submitting, "Enter advances exactly one step without submitting twice");
        Bridge.set("accessibilityTextScale", 2);
        Bridge.flush(true);
        break;
      case 5:
        welcome.step = 2;
        Focus.first(root.find(welcome, "welcome-large-targets")).forceActiveFocus();
        root.verify(keys.keyClick(Qt.Key_Backtab, Qt.ShiftModifier, 0) && keys.keyClick(Qt.Key_Tab, 0, 0), "Tab reaches enlarged controls at 200 percent");
        break;
      case 6:
        root.checkFocusedControlVisible();
        Bridge.setMany({
          panelLayout: root.original.panelLayout,
          accessibilityTextScale: root.original.accessibilityTextScale
        });
        Bridge.flush(true);
        break;
      case 7:
        welcome.draft = {};
        welcome.error = "";
        welcome.waitingAction = "onboarding-complete";
        welcome.submitting = true;
        Bridge.actionFailed("onboarding-complete", "Error de prueba recuperable");
        root.verify(welcome.error === "Error de prueba recuperable" && !welcome.submitting && root.finishedCount === 1, "failure keeps the assistant open for retry");
        welcome.edit("theme", Bridge.settings.theme === "paper" ? "amoled" : "paper");
        welcome.skip();
        break;
      case 8:
        if (welcome.submitting || root.finishedCount < 2)
          return;
        root.verify(JSON.stringify(Bridge.settings) === JSON.stringify(root.original), "skipping never applies the draft");
        root.verify(Bridge.onboarding.status === "skipped", "skip is persisted and acknowledged");
        window.visible = false;
        stop();
        console.log("SMOKE first-run COMPLETE");
        root.completed();
        break;
      }
      root.step++;
    }
  }
}
