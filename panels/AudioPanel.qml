import QtQuick
import QtQuick.Layouts
import "../core"
import "../components"

ColumnLayout {
  spacing: 10
  SectionTitle {
    text: "Salida"
  }
  Label {
    visible: Audio.outputs.length === 0
    text: "No hay salidas disponibles"
    color: Theme.muted
  }
  Repeater {
    model: Audio.outputs
    AudioStream {
      required property var modelData
      node: modelData
      device: true
      Layout.fillWidth: true
    }
  }
  SectionTitle {
    text: "Entrada · micrófono"
  }
  Label {
    visible: Audio.inputs.length === 0
    text: "No hay entradas disponibles"
    color: Theme.muted
  }
  Repeater {
    model: Audio.inputs
    AudioStream {
      required property var modelData
      node: modelData
      device: true
      input: true
      Layout.fillWidth: true
    }
  }
  SectionTitle {
    text: "Aplicaciones"
  }
  Label {
    visible: Audio.streams.length === 0
    text: "Sin flujos de audio activos"
    color: Theme.muted
  }
  Repeater {
    model: Audio.streams
    AudioStream {
      required property var modelData
      node: modelData
      Layout.fillWidth: true
    }
  }
}
