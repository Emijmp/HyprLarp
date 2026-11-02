import QtQuick
import QtQuick.Layouts
import "../core"

ColumnLayout {
  Layout.fillWidth: true
  spacing: 8
  SettingChoice {
    title: "Configurar barra de"
    choices: BarEditor.targets
    labels: BarEditor.targetLabels
    value: BarEditor.target
    onEdited: value => BarEditor.target = value
  }
  RowLayout {
    visible: BarEditor.target !== ""
    Label {
      text: "Los ajustes sin modificar heredan los valores base."
      color: Theme.muted
      font.pixelSize: 11
      wrapMode: Text.WordWrap
      Layout.fillWidth: true
    }
    ActionButton {
      text: "Heredar todo"
      onClicked: BarEditor.inherit()
    }
  }
  Rule {}
}
