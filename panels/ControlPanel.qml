import QtQuick
import QtQuick.Layouts
import "../core"
import "../components"

ColumnLayout {
  spacing: 6
  SectionTitle {
    text: "Conexiones"
  }
  ControlRow {
    title: "Wi-Fi"
    detail: Bridge.network.ssid || (Bridge.network.ethernet ? "Ethernet" : "Sin conexión")
    onClicked: ShellState.open("wifi")
  }
  ControlRow {
    title: "Bluetooth"
    detail: Bridge.bluetooth.enabled ? "Activado" : "Desactivado"
    onClicked: ShellState.open("bluetooth")
  }
  SettingToggle {
    title: "No molestar"
    checked: !!Bridge.settings.doNotDisturb
    onEdited: checked => Bridge.set("doNotDisturb", checked)
  }
  SettingToggle {
    title: "Modo presentación"
    checked: Presentation.active
    onEdited: checked => Presentation.active = checked
  }
  Rule {}
  SectionTitle {
    text: "Audio y pantalla"
  }
  ControlRow {
    title: "Pantallas y proyección"
    detail: "Duplicar / extender"
    onClicked: ShellState.open("displays")
  }
  SettingSlider {
    id: volume
    settingsControl: false
    title: "Volumen"
    from: 0
    to: 1
    step: 0.01
    value: Audio.volume
    displayValue: Audio.available ? Math.round(value * 100) + "%" : "No disponible"
    enabled: Audio.available
    onEdited: value => {
      volumeTimer.value = value;
      volumeTimer.restart();
    }
  }
  Timer {
    id: volumeTimer
    property real value: 0
    interval: 100
    onTriggered: Audio.setVolume(value)
  }
  RowLayout {
    SettingToggle {
      title: "Silenciar"
      checked: Audio.muted
      enabled: Audio.available
      onEdited: checked => Audio.setMuted(checked)
    }
    ActionButton {
      text: "Mezclador"
      onClicked: ShellState.open("audio")
    }
  }
  SettingSlider {
    title: "Brillo"
    settingsControl: false
    from: 1
    to: 100
    value: Bridge.system.brightness || 1
    suffix: "%"
    displayValue: Bridge.system.brightnessAvailable ? Math.round(value) + "%" : "No disponible"
    enabled: !!Bridge.system.brightnessAvailable
    onEdited: value => {
      brightnessTimer.value = value;
      brightnessTimer.restart();
    }
  }
  Timer {
    id: brightnessTimer
    property real value: 0
    interval: 100
    onTriggered: Bridge.perform("brightness", {
      value: value
    })
  }
  Rule {}
  ControlRow {
    title: "Recursos"
    detail: "CPU " + Math.round(Bridge.system.cpu || 0) + "% · RAM " + Math.round(Bridge.system.memory || 0) + "%"
    onClicked: ShellState.open("resources")
  }
  ControlRow {
    visible: !!Bridge.system.battery && Bridge.system.battery.available
    title: "Batería"
    detail: Bridge.system.battery ? Bridge.system.battery.percent + "%" : ""
    onClicked: ShellState.open("battery")
  }
  ControlRow {
    visible: Media.player !== null
    title: "Multimedia"
    detail: Media.player ? Media.title : ""
    onClicked: ShellState.open("media")
  }
  ControlRow {
    title: "Portapapeles"
    onClicked: ShellState.open("clipboard")
  }
  ControlRow {
    title: "Captura de pantalla"
    onClicked: ShellState.open("capture")
  }
  Rule {}
  ControlRow {
    title: "Perfiles de energía"
    detail: Bridge.power.available ? ({
        "power-saver": "Ahorro",
        balanced: "Equilibrado",
        performance: "Rendimiento"
      })[Bridge.power.profile] || "" : "No disponible"
    onClicked: ShellState.open("energy")
  }
  ControlRow {
    title: "Modo nocturno"
    detail: Bridge.nightLight.active ? "Activo" : "Desactivado"
    onClicked: ShellState.open("night-light")
  }
  ControlRow {
    title: "Dispositivos USB"
    detail: Bridge.usb.available ? String(Bridge.usb.drives.length) : ""
    onClicked: ShellState.open("usb")
  }
  ControlRow {
    title: "Fondos de pantalla"
    onClicked: ShellState.open("wallpapers")
  }
  ControlRow {
    title: "Configuración"
    onClicked: ShellState.open("settings")
  }
  ControlRow {
    title: "Sesión"
    onClicked: ShellState.open("session")
  }
}
