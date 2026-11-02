import QtQuick
import QtQuick.Controls
import "../core"

TextField {
  id: root
  implicitHeight: 34
  leftPadding: 9
  rightPadding: 9
  font.family: Theme.font
  font.pixelSize: 12
  color: Theme.text
  selectionColor: Theme.text
  selectedTextColor: Theme.surface
  placeholderTextColor: Theme.muted
  background: Rectangle {
    color: Theme.surface
    radius: Theme.radiusFor("field")
    border.width: 1
    border.color: root.activeFocus ? Theme.border : Theme.separator
    Rectangle {
      visible: Theme.decorated && root.activeFocus
      x: 3
      y: 3
      width: 4
      height: 1
      color: Theme.border
    }
  }
}
