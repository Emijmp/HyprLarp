import QtQuick
import QtQuick.Layouts
import "../core"

ColumnLayout {
  id: root
  property string title: ""
  property string icon: ""
  property real value: 0
  property string detail: ""
  property color tint: Theme.text
  spacing: 8
  Layout.fillWidth: true
  RowLayout {
    Label {
      text: root.title
      Layout.fillWidth: true
      font.pixelSize: Theme.fontPx(12)
    }
    Label {
      text: root.detail || Math.round(root.value) + "%"
      font.family: Theme.mono
      font.pixelSize: Theme.fontPx(11)
      color: Theme.muted
    }
  }
  Rectangle {
    Layout.fillWidth: true
    implicitHeight: 2
    color: Theme.separator
    Rectangle {
      width: parent.width * Math.min(1, Math.max(0, root.value / 100))
      height: parent.height
      color: Theme.text
    }
  }
}
