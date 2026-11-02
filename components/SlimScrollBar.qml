import QtQuick
import QtQuick.Controls
import "../core"

ScrollBar {
  implicitWidth: 6
  padding: 2
  background: Item {}
  contentItem: Rectangle {
    color: Theme.muted
    radius: 0
    implicitWidth: 2
    implicitHeight: 2
  }
}
