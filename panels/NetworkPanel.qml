import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../core"
import "../components"

ColumnLayout {
  id: root
  property string selectedSsid: ""
  spacing: 12
  SettingToggle {
    enabled: !Bridge.isBusyGroup("wifi-")
    title: "Wi-Fi"
    checked: Bridge.network.enabled
    onEdited: checked => Bridge.perform("wifi-power", {
        enabled: checked
      })
  }
  RowLayout {
    Label {
      text: Bridge.network.ethernet ? "Ethernet conectado" : "Redes disponibles"
      color: Theme.muted
      font.pixelSize: 11
      Layout.fillWidth: true
    }
    ActionButton {
      text: "Buscar"
      enabled: !Bridge.isBusy("refresh")
      onClicked: Bridge.perform("refresh", {
        name: "wifi"
      })
    }
  }
  Repeater {
    model: Bridge.network.networks || []
    ColumnLayout {
      id: row
      required property var modelData
      Layout.fillWidth: true
      spacing: 4
      RowLayout {
        ColumnLayout {
          Layout.fillWidth: true
          spacing: 4
          Label {
            text: row.modelData.ssid
            Layout.fillWidth: true
            font.pixelSize: 12
          }
          Label {
            text: row.modelData.connected ? "Conectada" : row.modelData.signal + "% · " + (row.modelData.security || "Abierta")
            font.pixelSize: 10
            color: Theme.muted
          }
        }
        ActionButton {
          text: row.modelData.connected ? "Desconectar" : "Conectar"
          enabled: !Bridge.isBusyGroup("wifi-")
          onClicked: {
            if (row.modelData.connected)
              Bridge.perform("wifi-disconnect", {
                interface: row.modelData.interface
              });
            else {
              root.selectedSsid = row.modelData.ssid;
              password.text = "";
              password.forceActiveFocus();
            }
          }
        }
      }
      Rule {}
    }
  }
  ColumnLayout {
    visible: root.selectedSsid !== ""
    Layout.fillWidth: true
    spacing: 8
    Label {
      text: root.selectedSsid
      Layout.fillWidth: true
    }
    Field {
      id: password
      Layout.fillWidth: true
      placeholderText: "Contraseña; vacía si está guardada o es abierta"
      echoMode: TextInput.Password
      onAccepted: connect.clicked()
    }
    RowLayout {
      ActionButton {
        text: "Cancelar"
        onClicked: {
          root.selectedSsid = "";
          password.text = "";
        }
      }
      ActionButton {
        id: connect
        text: Bridge.isBusy("wifi-connect") ? "Conectando…" : "Conectar"
        accent: true
        enabled: !Bridge.isBusyGroup("wifi-")
        onClicked: {
          Bridge.perform("wifi-connect", {
            ssid: root.selectedSsid,
            password: password.text
          });
          password.text = "";
        }
      }
      Item {
        Layout.fillWidth: true
      }
    }
  }
  Connections {
    target: Bridge
    function onActionFinished(action) {
      if (action === "wifi-connect")
        root.selectedSsid = "";
    }
  }
  EmptyState {
    visible: (Bridge.network.networks || []).length === 0
    title: Bridge.network.enabled ? "Sin redes disponibles" : "Wi-Fi desactivado"
    description: "Activa el adaptador y pulsa Buscar."
  }
  ActionButton {
    text: "VPN / redes empresariales"
    onClicked: Bridge.perform("open-tool", {
      name: "network"
    })
  }
}
