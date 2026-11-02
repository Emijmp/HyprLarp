import QtQuick
import QtQuick.Layouts

RowLayout {
  id: root
  property string title: ""
  property bool checked: false
  signal edited(bool checked)
  Layout.fillWidth: true
  Label {
    text: root.title
    Layout.fillWidth: true
    font.pixelSize: 12
  }
  Toggle {
    text: root.title
    checked: root.checked
    onClicked: root.edited(checked)
  }
}
