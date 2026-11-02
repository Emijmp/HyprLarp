import QtQuick
import QtQuick.Layouts
import "../core"
import "../components"

ColumnLayout {
  id: root
  property string confirmation: ""
  property string confirmationLabel: ""
  function request(command) {
    const labels = {
      suspend: "Suspender",
      logout: "Cerrar sesión",
      reboot: "Reiniciar",
      poweroff: "Apagar"
    };
    if (labels[command]) {
      confirmation = command;
      confirmationLabel = labels[command];
    }
  }
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
    model: [
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
    ControlRow {
      required property var modelData
      title: modelData.label
      onClicked: {
        if (modelData.name === "lock") {
          ShellState.close();
          Bridge.perform("session", {
            command: "lock"
          });
        } else {
          root.confirmation = modelData.name;
          root.confirmationLabel = modelData.label;
        }
      }
    }
  }
  Rule {
    visible: root.confirmation !== ""
    Layout.topMargin: 8
  }
  Label {
    visible: root.confirmation !== ""
    text: "¿" + root.confirmationLabel + "?"
    Layout.topMargin: 8
  }
  RowLayout {
    visible: root.confirmation !== ""
    Layout.topMargin: 8
    ActionButton {
      text: "Cancelar"
      onClicked: root.confirmation = ""
    }
    ActionButton {
      text: "Confirmar"
      accent: true
      onClicked: {
        ShellState.close();
        Bridge.perform("session", {
          command: root.confirmation
        });
      }
    }
    Item {
      Layout.fillWidth: true
    }
  }
}
