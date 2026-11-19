import QtQuick
import "../core"

Rectangle {
  required property Item control
  anchors.fill: parent
  anchors.margins: 1
  visible: control.activeFocus && control.enabled
  color: "transparent"
  border.width: 2
  border.color: Theme.accent
  radius: Theme.radiusFor("button")
  z: 20
  Accessible.ignored: true
}
