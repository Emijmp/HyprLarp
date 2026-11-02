import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Wayland
import "../core"

RowLayout {
  id: root
  required property string action
  property bool capturing: false
  function sync() {
    input.text = Qt.binding(() => Bridge.settings.shortcuts[root.action]);
  }
  function startCapture() {
    capturing = true;
    input.text = "";
    input.forceActiveFocus();
  }
  function cancelCapture() {
    capturing = false;
    sync();
  }
  LazyLoader {
    active: root.capturing && !Bridge.preview
    component: ShortcutInhibitor {
      window: root.QsWindow.window
      enabled: true
      onCancelled: root.cancelCapture()
    }
  }
  function canonical(chord) {
    return chord.toUpperCase().replace(/MOD4/g, "SUPER").replace(/MOD1/g, "ALT").split(",").map((part, i) => i === 0 ? part.replace(/\+/g, " ").trim().split(/\s+/).filter(Boolean).sort().join(" ") : part.trim()).join(",");
  }
  function commit(chord) {
    const shortcuts = Bridge.settings.shortcuts;
    if (chord && Object.keys(shortcuts).some(name => name !== action && canonical(shortcuts[name]) === canonical(chord))) {
      Bridge.toast("Esta combinación ya pertenece a otro atajo del shell", true);
      root.sync();
      return;
    }
    if (chord && !/^[A-Za-z0-9_ +]*,\s*[A-Za-z0-9_]+$/.test(chord)) {
      Bridge.toast("Formato: SUPER SHIFT, S", true);
      return;
    }
    Bridge.configure("shortcuts", Object.assign({}, shortcuts, {
      [action]: chord
    }));
    input.text = Qt.binding(() => Bridge.settings.shortcuts[root.action]);
  }
  Field {
    id: input
    Layout.preferredWidth: 215
    text: Bridge.settings.shortcuts[root.action]
    placeholderText: root.capturing ? "Pulsa la combinación…" : "Desactivado"
    font.family: Theme.mono
    readOnly: root.capturing
    onEditingFinished: if (!root.capturing)
      root.commit(text.trim())
    Keys.onShortcutOverride: event => {
      if (root.capturing)
        event.accepted = true;
    }
    onActiveFocusChanged: if (!activeFocus && root.capturing)
      Qt.callLater(() => {
        if (!input.activeFocus && root.capturing)
          root.cancelCapture();
      })
    Keys.onPressed: event => {
      if (!root.capturing)
        return;
      event.accepted = true;
      if (event.key === Qt.Key_Escape) {
        root.cancelCapture();
        return;
      }
      if ([Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta, Qt.Key_AltGr].includes(event.key))
        return;
      const names = {};
      names[Qt.Key_Space] = "SPACE";
      names[Qt.Key_Return] = "Return";
      names[Qt.Key_Enter] = "KP_Enter";
      names[Qt.Key_Tab] = "Tab";
      names[Qt.Key_Backspace] = "BackSpace";
      names[Qt.Key_Delete] = "Delete";
      names[Qt.Key_Print] = "Print";
      names[Qt.Key_Home] = "Home";
      names[Qt.Key_End] = "End";
      names[Qt.Key_Left] = "Left";
      names[Qt.Key_Right] = "Right";
      names[Qt.Key_Up] = "Up";
      names[Qt.Key_Down] = "Down";
      names[Qt.Key_PageUp] = "Prior";
      names[Qt.Key_PageDown] = "Next";
      names[Qt.Key_Minus] = "minus";
      names[Qt.Key_Equal] = "equal";
      names[Qt.Key_Comma] = "comma";
      names[Qt.Key_Period] = "period";
      let key = names[event.key] || (event.key >= Qt.Key_F1 && event.key <= Qt.Key_F35 ? "F" + (event.key - Qt.Key_F1 + 1) : event.text.toUpperCase());
      if (!/^[A-Za-z0-9_]+$/.test(key)) {
        Bridge.toast("Usa el campo de texto para esta tecla", true);
        root.cancelCapture();
        return;
      }
      const modifiers = [];
      if (event.modifiers & Qt.MetaModifier)
        modifiers.push("SUPER");
      if (event.modifiers & Qt.ControlModifier)
        modifiers.push("CTRL");
      if (event.modifiers & Qt.AltModifier)
        modifiers.push("ALT");
      if (event.modifiers & Qt.ShiftModifier)
        modifiers.push("SHIFT");
      root.capturing = false;
      root.commit(modifiers.join(" ") + ", " + key);
    }
  }
  ActionButton {
    text: root.capturing ? "Cancelar" : "Capturar"
    onClicked: {
      if (root.capturing)
        root.cancelCapture();
      else
        root.startCapture();
    }
  }
}
