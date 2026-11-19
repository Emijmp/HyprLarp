import QtQuick
import QtQuick.Layouts
import "../core"

Item {
  id: root
  property string title: ""
  property string value: ""
  implicitWidth: 220
  implicitHeight: Math.max(caption.implicitHeight, reading.implicitHeight) + 4
  Layout.fillWidth: true
  Label {
    id: caption
    text: root.title
    width: root.width * 0.4
    height: root.height
    font.pixelSize: Theme.fontPx(11)
  }
  Label {
    id: reading
    text: root.value
    anchors.right: parent.right
    width: root.width * 0.6
    height: root.height
    horizontalAlignment: Text.AlignRight
    color: Theme.muted
    font.family: Theme.mono
    font.pixelSize: Theme.fontPx(11)
  }
}
