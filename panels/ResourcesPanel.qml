import QtQuick
import QtQuick.Layouts
import "../core"
import "../components"

ColumnLayout {
  spacing: 18
  ActionButton {
    text: "Rendimiento de HyprLarp"
    onClicked: ShellState.open("performance")
  }
  Label {
    text: Bridge.system.hostname || "Sin datos del sistema"
    color: Theme.muted
    font.pixelSize: Theme.fontPx(11)
  }
  StatMeter {
    title: "CPU"
    value: Bridge.system.cpu || 0
    detail: Bridge.system.cpu === undefined ? "N/D" : Math.round(Bridge.system.cpu) + "%"
  }
  StatMeter {
    title: "Memoria"
    value: Bridge.system.memory || 0
    detail: Bridge.system.memoryTotal ? Bridge.system.memoryUsed + " / " + Bridge.system.memoryTotal + " GiB" : "N/D"
  }
  StatMeter {
    title: "Disco"
    value: Bridge.system.disk || 0
    detail: Bridge.system.diskFree === undefined ? "N/D" : Bridge.system.diskFree + " GiB libres"
  }
  Rule {}
  RowLayout {
    Label {
      text: "Descarga"
      Layout.fillWidth: true
    }
    Label {
      text: Bridge.system.download === undefined ? "N/D" : Bridge.system.download + " KiB/s"
      font.family: Theme.mono
      font.pixelSize: Theme.fontPx(11)
      color: Theme.muted
    }
  }
  RowLayout {
    Label {
      text: "Subida"
      Layout.fillWidth: true
    }
    Label {
      text: Bridge.system.upload === undefined ? "N/D" : Bridge.system.upload + " KiB/s"
      font.family: Theme.mono
      font.pixelSize: Theme.fontPx(11)
      color: Theme.muted
    }
  }
  RowLayout {
    Label {
      text: "Temperatura"
      Layout.fillWidth: true
    }
    Label {
      text: Bridge.system.temperature === null || Bridge.system.temperature === undefined ? "N/D" : Bridge.system.temperature + " °C"
      font.family: Theme.mono
      font.pixelSize: Theme.fontPx(11)
      color: Theme.muted
    }
  }
  RowLayout {
    Label {
      text: "Tiempo activo"
      Layout.fillWidth: true
    }
    Label {
      text: Bridge.system.uptime === undefined ? "N/D" : Math.floor(Bridge.system.uptime / 3600) + " h " + Math.floor(Bridge.system.uptime % 3600 / 60) + " min"
      font.family: Theme.mono
      font.pixelSize: Theme.fontPx(11)
      color: Theme.muted
    }
  }
}
