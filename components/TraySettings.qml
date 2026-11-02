import QtQuick
import QtQuick.Layouts
import Quickshell.Services.SystemTray
import "../core"

ColumnLayout {
  spacing: 6
  Label {
    text: "Iconos ocultos de la bandeja"
    color: Theme.muted
  }
  Label {
    visible: SystemTray.items.values.length === 0
    text: "No hay aplicaciones registradas"
    color: Theme.muted
  }
  Repeater {
    model: SystemTray.items
    SettingToggle {
      required property var modelData
      title: modelData.title || modelData.id
      checked: (Bridge.settings.trayHiddenItems || []).includes(modelData.id)
      onEdited: checked => {
        const ids = Bridge.settings.trayHiddenItems || [];
        Bridge.configure("trayHiddenItems", checked ? ids.concat([modelData.id]) : ids.filter(id => id !== modelData.id));
      }
    }
  }
}
