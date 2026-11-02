import QtQuick
import QtQuick.Layouts
import "../core"
import "../components"

ColumnLayout {
  spacing: 12
  SettingToggle {
    title: "Bluetooth"
    checked: Bridge.bluetooth.enabled
    enabled: !!Bridge.bluetooth.available && !Bridge.isBusyGroup("bluetooth-")
    onEdited: checked => Bridge.perform("bluetooth-power", {
        enabled: checked
      })
  }
  RowLayout {
    SectionTitle {
      text: "Dispositivos"
      Layout.fillWidth: true
    }
    ActionButton {
      text: "Buscar"
      enabled: Bridge.bluetooth.enabled
      onClicked: Bridge.perform("bluetooth-scan")
    }
    ActionButton {
      text: "Actualizar"
      onClicked: Bridge.perform("refresh", {
        name: "bluetooth"
      })
    }
  }
  Repeater {
    model: Bridge.bluetooth.devices || []
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
            text: row.modelData.name
            Layout.fillWidth: true
            font.pixelSize: 12
          }
          Label {
            text: row.modelData.connected ? "Conectado" : row.modelData.paired ? "Vinculado" : "Disponible"
            color: Theme.muted
            font.pixelSize: 10
          }
        }
        ActionButton {
          text: row.modelData.connected ? "Desconectar" : row.modelData.paired ? "Conectar" : "Vincular"
          enabled: !Bridge.isBusyGroup("bluetooth-")
          onClicked: Bridge.perform(row.modelData.connected ? "bluetooth-disconnect" : row.modelData.paired ? "bluetooth-connect" : "bluetooth-pair", {
            address: row.modelData.address
          })
        }
      }
      Rule {}
    }
  }
  EmptyState {
    visible: (Bridge.bluetooth.devices || []).length === 0
    title: Bridge.bluetooth.available ? "Sin dispositivos" : "Sin adaptador Bluetooth"
    description: "Pon el dispositivo en modo de vinculación y pulsa Buscar."
  }
  ActionButton {
    text: "Vinculación con PIN"
    onClicked: Bridge.perform("open-tool", {
      name: "bluetooth"
    })
  }
}
