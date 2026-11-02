import QtQuick
import QtQuick.Layouts
import "../core"
import "../components"

ColumnLayout {
  id: root
  property string connectionError: ""
  signal revealRequested(var item)
  spacing: 12
  function operate(action, values) {
    connectionError = "";
    Bridge.perform(action, Object.assign({
      adapter: Bridge.bluetooth.adapter || ""
    }, values || {}));
  }
  SettingToggle {
    title: "Bluetooth"
    checked: Bridge.bluetooth.enabled
    enabled: !!Bridge.bluetooth.available && !Bridge.preview && !Bridge.isBusyGroup("bluetooth-")
    onEdited: checked => root.operate("bluetooth-power", {
        enabled: checked
      })
  }
  Label {
    visible: Bridge.preview
    text: "Vista previa · las conexiones están desactivadas."
    font.pixelSize: 11
    color: Theme.muted
    Layout.fillWidth: true
    wrapMode: Text.WordWrap
  }
  BluetoothPrompt {
    Layout.fillWidth: true
    onRevealRequested: item => root.revealRequested(item)
  }
  RowLayout {
    visible: Bridge.isBusy("bluetooth-pair") && !Bridge.bluetoothPrompt
    Label {
      text: "Vinculando y conectando…"
      Layout.fillWidth: true
      font.pixelSize: 11
    }
    ActionButton {
      text: "Cancelar"
      onClicked: Bridge.perform("bluetooth-cancel")
    }
  }
  Label {
    visible: !!root.connectionError || !!Bridge.bluetooth.error
    text: root.connectionError || Bridge.bluetooth.error || ""
    font.pixelSize: 11
    Layout.fillWidth: true
    wrapMode: Text.WordWrap
  }
  RowLayout {
    SectionTitle {
      text: "Dispositivos"
      Layout.fillWidth: true
    }
    ActionButton {
      text: Bridge.bluetooth.discovering ? "Buscando…" : "Buscar"
      enabled: Bridge.bluetooth.enabled && !Bridge.preview && !Bridge.isBusyGroup("bluetooth-") && !Bridge.bluetooth.discovering
      onClicked: root.operate("bluetooth-scan")
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
          enabled: Bridge.bluetooth.enabled && !Bridge.preview && !Bridge.isBusyGroup("bluetooth-")
          onClicked: root.operate(row.modelData.connected ? "bluetooth-disconnect" : row.modelData.paired ? "bluetooth-connect" : "bluetooth-pair", {
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
  Connections {
    target: Bridge
    function onActionFailed(action, reason) {
      if (action.startsWith("bluetooth-"))
        root.connectionError = reason;
    }
    function onActionFinished(action) {
      if (["bluetooth-pair", "bluetooth-connect", "bluetooth-disconnect"].includes(action))
        root.connectionError = "";
    }
  }
  ActionButton {
    text: "Abrir gestor Bluetooth"
    onClicked: Bridge.perform("open-tool", {
      name: "bluetooth"
    })
  }
}
