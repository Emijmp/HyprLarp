import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../core"
import "../components"

ColumnLayout {
  id: root
  property var selectedNetwork: null
  property string connectionError: ""
  readonly property bool multipleAdapters: new Set((Bridge.network.networks || []).map(network => network.interface)).size > 1
  signal revealRequested(var item)
  spacing: 12
  function choose(network) {
    connectionError = "";
    selectedNetwork = Object.assign({}, network);
    password.text = "";
    if ((!network.security || network.security === "--") && !Bridge.preview)
      connectSelected();
    else
      Qt.callLater(() => {
        password.forceActiveFocus();
        root.revealRequested(connectionForm);
      });
  }
  function connectSelected() {
    if (!selectedNetwork || Bridge.preview || Bridge.isBusyGroup("wifi-"))
      return;
    connectionError = "";
    Bridge.perform("wifi-connect", {
      ssid: selectedNetwork.ssid,
      interface: selectedNetwork.interface,
      password: password.text
    });
  }
  SettingToggle {
    enabled: !!Bridge.network.available && !Bridge.preview && !Bridge.isBusyGroup("wifi-")
    title: "Wi-Fi"
    checked: Bridge.network.enabled
    onEdited: checked => Bridge.perform("wifi-power", {
        enabled: checked
      })
  }
  Label {
    visible: Bridge.preview
    text: "Vista previa · las conexiones están desactivadas."
    color: Theme.muted
    font.pixelSize: Theme.fontPx(11)
    Layout.fillWidth: true
    wrapMode: Text.WordWrap
  }
  RowLayout {
    Label {
      text: Bridge.network.ethernet ? "Ethernet conectado" : "Redes disponibles"
      color: Theme.muted
      font.pixelSize: Theme.fontPx(11)
      Layout.fillWidth: true
    }
    ActionButton {
      text: Bridge.isBusy("refresh") ? "Buscando…" : "Buscar"
      enabled: Bridge.network.enabled && !Bridge.isBusy("refresh") && !Bridge.isBusyGroup("wifi-")
      onClicked: Bridge.perform("refresh", {
        name: "wifi"
      })
    }
  }
  ColumnLayout {
    id: connectionForm
    visible: root.selectedNetwork !== null
    Layout.fillWidth: true
    spacing: 8
    SectionTitle {
      text: root.selectedNetwork ? root.selectedNetwork.ssid : ""
    }
    Label {
      text: root.selectedNetwork ? "Adaptador: " + root.selectedNetwork.interface : ""
      color: Theme.muted
      font.pixelSize: Theme.fontPx(10)
    }
    Field {
      id: password
      Layout.fillWidth: true
      placeholderText: "Contraseña · deja vacío si está guardada"
      echoMode: TextInput.Password
      enabled: !Bridge.isBusy("wifi-connect")
      onAccepted: root.connectSelected()
    }
    RowLayout {
      ActionButton {
        text: "Cancelar"
        enabled: !Bridge.isBusy("wifi-connect")
        onClicked: {
          root.selectedNetwork = null;
          password.text = "";
          root.connectionError = "";
        }
      }
      ActionButton {
        text: Bridge.isBusy("wifi-connect") ? "Conectando…" : "Conectar"
        accent: true
        enabled: !Bridge.preview && !Bridge.isBusyGroup("wifi-")
        onClicked: root.connectSelected()
      }
    }
    Rule {}
  }
  StatusMessage {
    visible: !!root.connectionError || !!Bridge.network.error
    text: root.connectionError || Bridge.network.error || ""
    error: true
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
            font.pixelSize: Theme.fontPx(12)
            elide: Text.ElideRight
          }
          Label {
            text: (row.modelData.connected ? "Conectada" : row.modelData.signal + "% · " + (row.modelData.security && row.modelData.security !== "--" ? row.modelData.security : "Abierta")) + (root.multipleAdapters ? " · " + row.modelData.interface : "")
            font.pixelSize: Theme.fontPx(10)
            color: Theme.muted
          }
        }
        ActionButton {
          text: row.modelData.connected ? "Desconectar" : "Conectar"
          enabled: !Bridge.isBusyGroup("wifi-") && (!row.modelData.connected || !Bridge.preview)
          onClicked: {
            root.connectionError = "";
            if (row.modelData.connected)
              Bridge.perform("wifi-disconnect", {
                interface: row.modelData.interface
              });
            else
              root.choose(row.modelData);
          }
        }
      }
      Rule {}
    }
  }
  Connections {
    target: Bridge
    function onActionFinished(action) {
      if (action === "wifi-connect") {
        root.selectedNetwork = null;
        password.text = "";
        root.connectionError = "";
      }
    }
    function onActionFailed(action, reason) {
      if (action.startsWith("wifi-"))
        root.connectionError = reason;
    }
  }
  EmptyState {
    visible: (Bridge.network.networks || []).length === 0
    error: !Bridge.network.available || !!Bridge.network.error
    title: !Bridge.network.available ? "NetworkManager no disponible" : Bridge.network.enabled ? "Sin redes disponibles" : "Wi-Fi desactivado"
    description: Bridge.network.available ? "Activa el adaptador y pulsa Buscar." : "Comprueba que NetworkManager esté iniciado."
  }
  ActionButton {
    text: "VPN / redes empresariales"
    onClicked: Bridge.perform("open-tool", {
      name: "network"
    })
  }
}
