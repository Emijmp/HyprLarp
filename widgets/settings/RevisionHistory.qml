import QtQuick
import QtQuick.Layouts
import "../../core"
import "../../components"

ColumnLayout {
  id: root
  spacing: 8
  property string selectedId: ""
  function refresh() {
    if (Bridge.configurationActive)
      Bridge.performConfig("settings-revisions");
  }
  Component.onCompleted: refresh()
  Connections {
    target: Bridge
    function onConfigurationActiveChanged() {
      if (Bridge.configurationActive)
        root.refresh();
    }
    function onSettingsSettled() {
      root.selectedId = "";
      root.refresh();
    }
  }
  SectionTitle {
    text: "Historial de configuración"
  }
  Label {
    text: "Las últimas 30 versiones se conservan al reiniciar. Comparar muestra los cambios antes de restaurar; la restauración se puede deshacer. No incluye No molestar, la pausa del portapapeles ni diseños de pantallas."
    Layout.fillWidth: true
    wrapMode: Text.WordWrap
    color: Theme.muted
    font.pixelSize: Theme.fontPx(11)
  }
  ActionButton {
    text: "Actualizar historial"
    onClicked: root.refresh()
  }
  Repeater {
    model: Bridge.settingsRevisions
    RowLayout {
      required property var modelData
      Layout.fillWidth: true
      Label {
        text: new Date(modelData.time * 1000).toLocaleString() + " · " + modelData.label + " · " + modelData.keys.length + " cambios"
        Layout.fillWidth: true
        wrapMode: Text.WordWrap
        font.pixelSize: Theme.fontPx(11)
      }
      ActionButton {
        text: "Comparar"
        onClicked: {
          root.selectedId = modelData.id;
          Bridge.performConfig("settings-revision-diff", {
            id: modelData.id
          });
        }
      }
    }
  }
  Label {
    visible: Bridge.settingsRevisions.length === 0
    text: "El historial se crea al guardar cambios desde Configuración."
    color: Theme.muted
    font.pixelSize: Theme.fontPx(11)
  }
  ColumnLayout {
    visible: root.selectedId !== "" && Bridge.revisionDiff.id === root.selectedId
    Layout.fillWidth: true
    Repeater {
      model: parent.visible ? Bridge.revisionDiff.changes : []
      Label {
        required property var modelData
        text: modelData.key + ": " + JSON.stringify(modelData.current).slice(0, 180) + " → " + JSON.stringify(modelData.saved).slice(0, 180)
        Layout.fillWidth: true
        wrapMode: Text.WrapAnywhere
        font.pixelSize: Theme.fontPx(11)
      }
    }
    ActionButton {
      text: "Restaurar esta versión"
      enabled: Bridge.revisionDiff.changes.length > 0 && !Bridge.restoring
      onClicked: Bridge.restoreSettings("settings-restore-revision", {
        id: root.selectedId
      })
    }
  }
}
