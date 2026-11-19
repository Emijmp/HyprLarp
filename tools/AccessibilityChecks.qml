import QtQuick
import QtQuick.Layouts
import QtQuick.Window
import QtTest
import Quickshell
import Quickshell.Io
import "../core"
import "../components"
import "../widgets"

Scope {
  id: root
  property int step: 0
  property int presses: 0
  property bool finished: false
  property var original: ({})
  signal completed
  function verify(condition, message) {
    if (!condition)
      throw new Error("Accessibility regression: " + message);
  }
  IpcHandler {
    target: "a11yTest"
    function status(): string {
      return JSON.stringify({
        finished: root.finished,
        presses: root.presses,
        step: root.step,
        sliderValue: slider.value,
        sliderMoves: slider.moveSerial,
        secretLabel: secret.Accessible.name,
        secretVisible: secret.visible
      });
    }
    function quit(): void {
      Qt.quit();
    }
  }
  FloatingWindow {
    id: window
    title: "HyprLarp · Prueba de accesibilidad"
    implicitWidth: 740
    implicitHeight: 720
    color: Theme.surface
    ColumnLayout {
      anchors.fill: parent
      anchors.margins: 24
      spacing: 14
      TestEvent {
        id: keys
      }
      SectionTitle {
        text: "Prueba de accesibilidad"
      }
      ActionButton {
        id: button
        objectName: "a11y-button"
        text: "Botón accesible"
        onClicked: root.presses++
      }
      Toggle {
        id: toggle
        text: "Opción accesible"
      }
      LevelSlider {
        id: slider
        Accessible.name: "Nivel accesible"
        from: 0
        to: 10
        stepSize: 1
        value: 3
        Layout.fillWidth: true
      }
      Field {
        id: field
        Accessible.name: "Texto accesible"
        placeholderText: "Texto accesible"
        Layout.fillWidth: true
      }
      Label {
        id: secretLabel
        text: "Contraseña de prueba"
        Accessible.labelFor: secret
      }
      Field {
        id: secret
        Accessible.name: "Contraseña de prueba"
        Accessible.description: "Contraseña de prueba"
        Accessible.labelledBy: secretLabel
        echoMode: TextInput.Password
        text: "fixture-secret"
        Layout.fillWidth: true
      }
      Selection {
        Accessible.name: "Lista accesible"
        choices: ["uno", "dos"]
        value: "uno"
      }
      Label {
        text: "Texto ampliable y contraste verificable"
        Layout.fillWidth: true
        wrapMode: Text.WordWrap
      }
      Item {
        Layout.fillHeight: true
      }
    }
  }
  CaptureEditor {
    id: editor
    visible: false
    width: 800
    height: 600
    draft: ({
        width: 800,
        height: 600,
        url: "",
        token: "test"
      })
  }
  Timer {
    interval: 200
    repeat: true
    running: true
    onTriggered: {
      if (!Bridge.ready || Bridge.saving || Bridge.hasPendingSettings)
        return;
      switch (root.step++) {
      case 0:
        for (const key of ["accessibilityTextScale", "accessibilityHighContrast", "accessibilityReducedMotion", "accessibilityLargeTargets", "animations"])
          root.original[key] = Bridge.settings[key];
        Bridge.setMany({
          accessibilityTextScale: 2,
          accessibilityHighContrast: true,
          accessibilityLargeTargets: true,
          accessibilityReducedMotion: true,
          animations: true
        });
        window.contentItem.Window.window.requestActivate();
        break;
      case 1:
        root.verify(Theme.px(12) === 24 && field.font.pixelSize === 24, "global font scaling");
        root.verify(button.implicitHeight >= 44 && field.implicitHeight >= 44 && toggle.implicitWidth >= 44, "large targets");
        root.verify(String(Theme.text) === "#ffffff" && String(Theme.surface) === "#000000" && Theme.alpha(Theme.surface, .1).a === 1, "opaque high contrast");
        root.verify(Theme.duration === 0, "reduced motion");
        button.forceActiveFocus();
        root.verify(keys.keyClick(Qt.Key_Space, 0, 0) && root.presses === 1, "Space activates custom button");
        root.verify(keys.keyClick(Qt.Key_Tab, 0, 0) && toggle.activeFocus, "Tab reaches checkbox");
        root.verify(keys.keyClick(Qt.Key_Space, 0, 0) && toggle.checked, "Space toggles checkbox");
        root.verify(keys.keyClick(Qt.Key_Backtab, Qt.ShiftModifier, 0) && button.activeFocus, "Shift+Tab returns to button");
        root.verify(keys.keyClick(Qt.Key_Return, 0, 0) && root.presses === 2, "Enter activates custom button");
        slider.forceActiveFocus();
        root.verify(keys.keyClick(Qt.Key_Right, 0, 0) && slider.value === 4, "arrow adjusts slider");
        field.forceActiveFocus();
        root.verify(keys.keyClickChar("a", 0, 0) && field.text === "a", "native text input");
        editor.tool = "redact";
        editor.keyboardAction(Qt.Key_Space, 0);
        editor.keyboardAction(Qt.Key_Right, Qt.ShiftModifier);
        editor.keyboardAction(Qt.Key_Down, Qt.ShiftModifier);
        editor.keyboardAction(Qt.Key_Return, 0);
        root.verify(editor.operations.length === 1 && editor.operations[0].x2 - editor.operations[0].x === 10, "keyboard-only capture editing");
        Bridge.setMany(root.original);
        break;
      default:
        stop();
        root.finished = true;
        console.log("SMOKE accessibility COMPLETE");
        if (Quickshell.env("HYPRLARP_A11Y_HOLD") !== "1")
          window.visible = false;
        root.completed();
      }
    }
  }
}
