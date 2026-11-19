import QtQuick
import QtQuick.Layouts
import "../core"

RowLayout {
  id: root
  property string title: ""
  property bool checked: false
  signal edited(bool checked)
  Layout.fillWidth: true
  Label {
    text: root.title
    wrapMode: Text.WordWrap
    Layout.fillWidth: true
    font.pixelSize: Theme.fontPx(12)
  }
  Toggle {
    text: root.title
    checked: root.checked
    onClicked: root.edited(checked)
  }
}
