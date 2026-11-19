import QtQuick
import QtQuick.Layouts
import "../core"
import "../components"

ColumnLayout {
  spacing: 12
  SectionTitle {
    text: "Pantalla"
  }
  SettingSlider {
    title: "Brillo"
    settingsControl: false
    from: 1
    to: 100
    suffix: "%"
    value: Bridge.system.brightness || 1
    enabled: !!Bridge.system.brightnessAvailable
    displayValue: enabled ? Math.round(value) + "%" : "No disponible"
    onEdited: value => {
      brightness.value = value;
      brightness.restart();
    }
  }
  Timer {
    id: brightness
    property real value: 0
    interval: 100
    onTriggered: Bridge.perform("brightness", {
      value: value
    })
  }
  Label {
    visible: !Bridge.system.brightnessAvailable
    text: "El equipo no expone un dispositivo de brillo compatible."
    font.pixelSize: Theme.fontPx(11)
    color: Theme.muted
    wrapMode: Text.WordWrap
    Layout.fillWidth: true
  }
}
