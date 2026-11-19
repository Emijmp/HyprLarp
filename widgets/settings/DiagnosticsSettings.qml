import QtQuick
import QtQuick.Layouts
import QtQuick.Dialogs
import "../../core"
import "../../components"

ColumnLayout {
  id: root
  spacing: 8
  property string pendingPath: ""
  readonly property bool busy: Bridge.isBusyGroup("diagnostics-")
  function exportPending() {
    if (pendingPath && Bridge.configurationActive) {
      Bridge.performConfig("diagnostics-export", {
        path: pendingPath
      });
      pendingPath = "";
    }
  }
  Connections {
    target: Bridge
    function onConfigurationActiveChanged() {
      root.exportPending();
    }
  }
  SectionTitle {
    text: "Estado del sistema"
  }
  Label {
    text: "Comprueba las herramientas instaladas, la conexión con HyprLarp y sus servicios. El informe incluye versiones y los últimos errores; las comprobaciones no modifican el sistema."
    Layout.fillWidth: true
    wrapMode: Text.WordWrap
    color: Theme.muted
    font.pixelSize: Theme.fontPx(11)
  }
  RowLayout {
    ActionButton {
      text: root.busy ? "Comprobando…" : "Comprobar estado"
      enabled: !root.busy
      onClicked: Bridge.performConfig("diagnostics-run")
    }
    ActionButton {
      text: "Exportar informe…"
      enabled: !root.busy
      onClicked: file.open()
    }
  }
  Repeater {
    model: Bridge.diagnostics.checks || []
    Label {
      required property var modelData
      text: ({
          ok: "✓",
          warning: "!",
          error: "✗",
          optional: "·"
        })[modelData.status] + " " + modelData.name + " · " + modelData.detail.replace(/\n/g, " · ").slice(0, 260)
      Layout.fillWidth: true
      wrapMode: Text.WordWrap
      color: modelData.status === "error" ? Theme.danger : modelData.status === "ok" ? Theme.text : Theme.muted
      font.pixelSize: Theme.fontPx(11)
    }
  }
  FileDialog {
    id: file
    title: "Exportar diagnóstico"
    fileMode: FileDialog.SaveFile
    nameFilters: ["JSON (*.json)"]
    defaultSuffix: "json"
    onAccepted: {
      root.pendingPath = selectedFile.toString();
      Qt.callLater(root.exportPending);
    }
  }
}
