import QtQuick
import QtQuick.Layouts
import "../core"
import "../components"

ColumnLayout {
  spacing: 12
  readonly property var labels: ({
      "power-saver": "Ahorro de energía",
      balanced: "Equilibrado",
      performance: "Rendimiento"
    })
  SectionTitle {
    text: "Perfil del sistema"
  }
  Label {
    text: Bridge.power.available ? parent.labels[Bridge.power.profile] || Bridge.power.profile : "Servicio de energía no disponible"
    Layout.fillWidth: true
    font.pixelSize: 13
  }
  Repeater {
    model: Bridge.power.profiles || []
    ActionButton {
      required property string modelData
      text: ({
          "power-saver": "Ahorro de energía",
          balanced: "Equilibrado",
          performance: "Rendimiento"
        })[modelData]
      selected: Bridge.power.profile === modelData
      enabled: Bridge.power.available && !Bridge.preview && !Bridge.settingsOnly && !Bridge.isBusy("power-profile")
      onClicked: Bridge.perform("power-profile", {
        profile: modelData
      })
    }
  }
  Label {
    visible: !Bridge.power.available
    text: Bridge.power.error || "Requiere power-profiles-daemon y acceso a D-Bus."
    color: Theme.muted
    font.pixelSize: 11
    Layout.fillWidth: true
    wrapMode: Text.WordWrap
  }
  Label {
    visible: !!Bridge.power.reason
    text: "Rendimiento limitado: " + (({
          "lap-detected": "equipo sobre el regazo",
          "high-operating-temperature": "temperatura elevada"
        })[Bridge.power.reason] || Bridge.power.reason)
    color: Theme.muted
    font.pixelSize: 11
    Layout.fillWidth: true
    wrapMode: Text.WordWrap
  }
  ActionButton {
    text: "Actualizar"
    onClicked: Bridge.perform("system-refresh", {
      name: "power"
    })
  }
  Rule {}
  ControlRow {
    title: "Información y salud de batería"
    detail: Bridge.system.battery && Bridge.system.battery.percent !== null ? Bridge.system.battery.percent + "%" : ""
    onClicked: ShellState.open("battery")
  }
}
