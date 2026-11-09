import QtQuick
import QtQuick.Layouts
import "../core"
import "../components"

ColumnLayout {
  id: root
  objectName: "sessionMenu"
  property string confirmation: ""
  property string confirmationLabel: ""
  readonly property var actions: [
    {
      name: "lock",
      label: "Bloquear"
    },
    {
      name: "suspend",
      label: "Suspender"
    },
    {
      name: "logout",
      label: "Cerrar sesión"
    },
    {
      name: "reboot",
      label: "Reiniciar"
    },
    {
      name: "poweroff",
      label: "Apagar"
    }
  ]
  function request(command) {
    const action = actions.find(item => item.name === command && item.name !== "lock");
    if (action) {
      confirmation = command;
      confirmationLabel = action.label;
      root.forceActiveFocus();
    }
  }
  function select(index) {
    const action = actions[index];
    if (!action)
      return;
    if (action.name === "lock") {
      ShellState.close();
      Bridge.perform("session", {
        command: "lock"
      });
    } else {
      request(action.name);
    }
  }
  function confirm() {
    const command = confirmation;
    if (!command)
      return;
    confirmation = "";
    ShellState.close();
    Bridge.perform("session", {
      command: command
    });
  }
  function handleKey(event) {
    if (ShellState.panel !== "session" || (event.modifiers & ~Qt.KeypadModifier) !== Qt.NoModifier)
      return;
    const index = event.key - Qt.Key_1;
    const number = index >= 0 && index < actions.length;
    const enter = event.key === Qt.Key_Return || event.key === Qt.Key_Enter;
    if (!number && event.key !== Qt.Key_Escape && !(enter && confirmation))
      return;
    event.accepted = true;
    if (event.isAutoRepeat)
      return;
    if (number)
      select(index);
    else if (event.key === Qt.Key_Escape) {
      if (confirmation)
        confirmation = "";
      else
        ShellState.close();
    } else {
      confirm();
    }
  }
  Keys.onPressed: event => root.handleKey(event)
  Component.onCompleted: request(ShellState.sessionRequest)
  Connections {
    target: ShellState
    function onSessionRequested(command) {
      root.request(command);
    }
  }
  spacing: 4
  Label {
    text: (Bridge.system.user || "") + " @ " + (Bridge.system.hostname || "Hyprland")
    color: Theme.muted
    font.pixelSize: 11
    Layout.fillWidth: true
    Layout.bottomMargin: 8
  }
  Repeater {
    model: root.actions
    ControlRow {
      required property var modelData
      required property int index
      title: modelData.label
      detail: String(index + 1)
      onClicked: root.select(index)
    }
  }
  Rule {
    visible: root.confirmation !== ""
    Layout.topMargin: 8
  }
  Label {
    visible: root.confirmation !== ""
    text: "¿" + root.confirmationLabel + "? · Enter para confirmar · Esc para cancelar"
    Layout.topMargin: 8
    Layout.fillWidth: true
    wrapMode: Text.WordWrap
  }
  RowLayout {
    visible: root.confirmation !== ""
    Layout.topMargin: 8
    ActionButton {
      objectName: "sessionCancel"
      text: "Cancelar"
      onClicked: root.confirmation = ""
    }
    ActionButton {
      objectName: "sessionConfirm"
      text: "Confirmar"
      accent: true
      onClicked: root.confirm()
    }
    Item {
      Layout.fillWidth: true
    }
  }
}
