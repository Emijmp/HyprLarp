import QtQuick
import "../core"

Label {
  id: root
  font.pixelSize: 11
  font.weight: Font.Medium
  color: Theme.muted
  leftPadding: Theme.decorated ? 12 : 0
  topPadding: Theme.decorated ? 2 : 0
  bottomPadding: Theme.decorated ? 2 : 0
  Rectangle {
    visible: Theme.decorated
    x: 0
    anchors.verticalCenter: parent.verticalCenter
    width: 5
    height: 2
    color: Theme.border
  }
}
