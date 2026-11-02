import QtQuick
import QtQuick.Layouts
import "../core"
import "../components"
import "../core/formats.js" as Format

ColumnLayout {
  id: root
  readonly property var battery: Bridge.system.battery || {
    available: false,
    batteries: []
  }
  spacing: 14
  EmptyState {
    visible: !root.battery.available
    title: "Sin batería"
    description: "El equipo no informa de una batería."
  }
  Repeater {
    model: root.battery.batteries || []
    ColumnLayout {
      id: pack
      required property var modelData
      readonly property var b: modelData
      readonly property var remaining: b.status === "Charging" ? b.timeToFull : b.timeToEmpty
      Layout.fillWidth: true
      spacing: 8
      SectionTitle {
        text: pack.b.name + (pack.b.model ? " · " + pack.b.model : "")
      }
      StatMeter {
        visible: pack.b.percent !== null && pack.b.percent !== undefined
        title: "Carga"
        value: pack.b.percent || 0
      }
      ValueRow {
        title: "Estado"
        value: ({
            Charging: "Cargando",
            Discharging: "En uso",
            Full: "Carga completa",
            "Not charging": "Sin cargar",
            Unknown: "No disponible"
          })[pack.b.status] || pack.b.status
      }
      ValueRow {
        title: "Salud"
        value: Format.number(pack.b.health, "%")
      }
      ValueRow {
        title: "Desgaste"
        value: Format.number(pack.b.degradation, "%")
      }
      ValueRow {
        title: pack.b.status === "Charging" ? "Potencia de carga" : "Consumo"
        value: Format.number(pack.b.watts, "W", 2)
      }
      ValueRow {
        title: "Capacidad actual"
        value: Format.number(pack.b.energyNow, "Wh", 2)
      }
      ValueRow {
        title: "Capacidad máxima"
        value: Format.number(pack.b.energyFull, "Wh", 2)
      }
      ValueRow {
        title: "Capacidad de diseño"
        value: Format.number(pack.b.energyDesign, "Wh", 2)
      }
      ValueRow {
        title: "Ciclos"
        value: Format.number(pack.b.cycles, "", 0)
      }
      ValueRow {
        title: "Voltaje"
        value: Format.number(pack.b.voltage, "V", 2)
      }
      ValueRow {
        title: "Temperatura"
        value: Format.number(pack.b.temperature, "°C")
      }
      ValueRow {
        title: pack.b.status === "Charging" ? "Hasta completar" : "Tiempo restante"
        value: (pack.b.timeEstimated && pack.remaining > 0 ? "~ " : "") + Format.duration(pack.remaining)
      }
      ValueRow {
        title: "Fabricante"
        value: pack.b.manufacturer || "No disponible"
      }
      ValueRow {
        title: "Tecnología"
        value: pack.b.technology || "No disponible"
      }
      ValueRow {
        visible: pack.b.chargeStart !== null && pack.b.chargeStart !== undefined
        title: "Inicio de carga"
        value: Format.number(pack.b.chargeStart, "%", 0)
      }
      ValueRow {
        visible: pack.b.chargeEnd !== null && pack.b.chargeEnd !== undefined
        title: "Límite de carga"
        value: Format.number(pack.b.chargeEnd, "%", 0)
      }
      Label {
        visible: !!pack.b.capacityEstimated
        text: "Capacidades estimadas a partir de carga y voltaje."
        color: Theme.muted
        font.pixelSize: 10
        wrapMode: Text.WordWrap
        Layout.fillWidth: true
      }
      Rule {}
    }
  }
  ControlRow {
    title: "Perfiles de energía"
    onClicked: ShellState.open("energy")
  }
}
