import QtQuick
import QtQuick.Controls
import "../core"

ToolTip {
  id: root
  padding: 6
  delay: 600
  contentItem: Label {
    text: root.text
    font.pixelSize: Theme.fontPx(10)
  }
  background: Rectangle {
    color: Theme.surface
    border.width: 1
    border.color: Theme.border
    radius: Theme.radiusFor("tooltip")
  }
}
