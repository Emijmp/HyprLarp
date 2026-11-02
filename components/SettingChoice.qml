import QtQuick
import QtQuick.Layouts

ColumnLayout {
  id: root
  property string title: ""
  property var choices: []
  property var labels: []
  property string value: ""
  signal edited(string value)
  Layout.fillWidth: true
  spacing: 6
  SectionTitle {
    text: root.title
  }
  RowLayout {
    spacing: 4
    Repeater {
      model: root.choices
      ActionButton {
        required property string modelData
        required property int index
        text: root.labels[index] || modelData
        selected: root.value === modelData
        onClicked: root.edited(modelData)
      }
    }
    Item {
      Layout.fillWidth: true
    }
  }
}
