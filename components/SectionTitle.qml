import QtQuick
import "../core"

Label {
  id: root
  font.pixelSize: 11
  font.weight: Font.Medium
  color: Theme.muted
  leftPadding: Theme.detail("sectionMarks") ? 12 : 0
  topPadding: Theme.detail("sectionMarks") ? 2 : 0
  bottomPadding: Theme.detail("sectionMarks") ? 2 : 0
  Rectangle {
    visible: Theme.detail("sectionMarks")
    x: 0
    anchors.verticalCenter: parent.verticalCenter
    width: 5
    height: 2
    color: Theme.border
  }
}
