import QtQuick
import QtQuick.Window
import QtTest
import Quickshell
import "../core"
import "../widgets"

Scope {
  id: root
  property int step: 0
  property real deadline: Date.now() + 10000
  readonly property var menu: find(overlay, "sessionMenu")
  signal completed
  function verify(condition, message) {
    if (!condition) {
      Qt.exit(1);
      throw new Error("Session regression: " + message);
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
  function press(key, modifiers) {
    verify(events.keyClick(key, modifiers || Qt.NoModifier, 0), "key event reaches the menu window");
  }
  FloatingWindow {
    id: window
    visible: true
    implicitWidth: 700
    implicitHeight: 650
    color: Theme.background
    PanelOverlay {
      id: overlay
      anchors.fill: parent
      TestEvent {
        id: events
      }
    }
  }
  Timer {
    interval: 140
    repeat: true
    running: true
    onTriggered: {
      root.verify(Date.now() < root.deadline, "keyboard checks timed out");
      root.verify(Bridge.preview, "session actions are tested only in preview");
      if (!overlay.Window.window.active) {
        overlay.Window.window.requestActivate();
        return;
      }
      if (Bridge.isBusy("session"))
        return;
      switch (root.step) {
      case 0:
        ShellState.open("session");
        break;
      case 1:
        root.verify(!!root.menu && root.menu.actions[0].name === "lock" && root.menu.actions[4].name === "poweroff", "numbering follows the visible action order");
        root.press(Qt.Key_1, Qt.ControlModifier);
        root.press(Qt.Key_5, Qt.MetaModifier);
        root.press(Qt.Key_6);
        root.verify(!root.menu.confirmation && ShellState.panel === "session", "modified and unrelated keys do not trigger actions");
        root.press(Qt.Key_2);
        root.verify(root.menu.confirmation === "suspend" && !Bridge.isBusy("session"), "2 selects suspend without executing it");
        root.press(Qt.Key_Escape);
        root.verify(!root.menu.confirmation && ShellState.panel === "session", "Escape cancels confirmation");
        root.press(Qt.Key_Escape);
        root.verify(ShellState.panel === "", "Escape closes the menu");
        break;
      case 2:
        ShellState.open("session");
        break;
      case 3:
        root.press(Qt.Key_3);
        root.verify(root.menu.confirmation === "logout", "3 selects logout");
        root.press(Qt.Key_4);
        root.verify(root.menu.confirmation === "reboot", "4 selects reboot");
        root.press(Qt.Key_5, Qt.KeypadModifier);
        root.verify(root.menu.confirmation === "poweroff" && !Bridge.isBusy("session"), "5 on the keypad selects poweroff without executing it");
        const repeat = {
          key: Qt.Key_Return,
          modifiers: Qt.NoModifier,
          isAutoRepeat: true,
          accepted: false
        };
        root.menu.handleKey(repeat);
        root.verify(repeat.accepted && root.menu.confirmation === "poweroff" && !Bridge.isBusy("session"), "held keys never confirm a session action");
        root.press(Qt.Key_Return);
        root.verify(ShellState.panel === "" && Bridge.isBusy("session"), "Enter confirms the selected action");
        break;
      case 4:
        ShellState.open("session");
        break;
      case 5:
        root.press(Qt.Key_1);
        root.verify(ShellState.panel === "" && Bridge.isBusy("session"), "1 locks without a confirmation step");
        break;
      case 6:
        ShellState.openSession("reboot");
        break;
      case 7:
        root.verify(root.menu.confirmation === "reboot", "bar actions still open their requested confirmation");
        root.find(root.menu, "sessionCancel").forceActiveFocus();
        root.press(Qt.Key_2);
        root.verify(root.menu.confirmation === "suspend" && !Bridge.isBusy("session"), "number shortcuts also work while a button has focus");
        root.press(Qt.Key_Escape);
        ShellState.open("calendar");
        break;
      case 8:
        root.press(Qt.Key_5);
        root.verify(ShellState.panel === "calendar" && !Bridge.isBusy("session"), "number shortcuts are confined to the session menu");
        ShellState.close();
        window.visible = false;
        stop();
        console.log("SMOKE session keyboard COMPLETE");
        root.completed();
        break;
      }
      root.step++;
    }
  }
}
