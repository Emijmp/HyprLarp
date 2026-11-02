import QtQuick
import QtQuick.Layouts
import "../../core"
import "../../components"

ColumnLayout {
  id: root
  spacing: 12
  property bool confirmApply: false
  readonly property var labels: ({
      energy: "Perfiles de energía",
      "night-light": "Modo nocturno",
      usb: "Dispositivos USB",
      osd: "Ajustes OSD",
      launcher: "Aplicaciones",
      control: "Centro de control",
      notifications: "Notificaciones",
      clipboard: "Portapapeles",
      media: "Multimedia",
      calendar: "Calendario",
      wallpapers: "Fondos",
      session: "Sesión",
      settings: "Configuración",
      wifi: "Wi-Fi",
      bluetooth: "Bluetooth",
      resources: "Recursos",
      battery: "Batería",
      capture: "Menú de capturas",
      "screenshot-region": "Capturar región",
      "screenshot-screen": "Capturar escritorio",
      lock: "Bloquear",
      audio: "Audio",
      presentation: "Presentación"
    })
  Label {
    text: "Capturar registra la siguiente combinación; Escape cancela. También puedes escribir SUPER SHIFT, S o dejarlo vacío. Requiere cargar hyprlarp.lua en Hyprland."
    color: Theme.muted
    wrapMode: Text.WordWrap
    Layout.fillWidth: true
    font.pixelSize: 11
  }
  Repeater {
    model: Object.keys(Bridge.settings.shortcuts || {})
    RowLayout {
      id: entry
      required property string modelData
      Label {
        text: root.labels[entry.modelData]
        Layout.fillWidth: true
        font.pixelSize: 12
      }
      ShortcutField {
        action: entry.modelData
      }
    }
  }
  Rule {}
  RowLayout {
    ActionButton {
      text: "Comprobar conflictos"
      enabled: !Bridge.preview && !Bridge.isBusy("shortcut-conflicts")
      onClicked: {
        root.confirmApply = false;
        Bridge.performConfig("shortcut-conflicts");
      }
    }
    ActionButton {
      text: root.confirmApply ? "Aplicar y reemplazar coincidencias" : "Aplicar atajos"
      accent: true
      enabled: !Bridge.preview && !Bridge.restoring && !Bridge.isBusy("apply-shortcuts")
      onClicked: {
        if (Bridge.shortcutConflicts.length && !root.confirmApply) {
          root.confirmApply = true;
          return;
        }
        Bridge.performConfig("apply-shortcuts");
        root.confirmApply = false;
      }
    }
  }
  Repeater {
    model: Bridge.shortcutConflicts
    Label {
      required property var modelData
      text: modelData.chord + " coincide con " + modelData.command
      color: Theme.muted
      font.pixelSize: 11
      wrapMode: Text.WordWrap
      Layout.fillWidth: true
    }
  }
  Connections {
    target: Bridge
    function onSettingsChanged() {
      root.confirmApply = false;
    }
  }
}
