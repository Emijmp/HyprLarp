import QtQuick
import QtQuick.Controls
import "../core"

CheckBox {
  id: root
  implicitWidth: Theme.controlHeight(24)
  implicitHeight: Theme.controlHeight(26)
  activeFocusOnTab: true
  padding: 0
  contentItem: Item {}
  indicator: Rectangle {
    x: 4
    y: (root.height - height) / 2
    implicitWidth: 16
    implicitHeight: 16
    radius: Math.min(6, Theme.radiusFor("button"))
    color: root.checked ? Theme.text : "transparent"
    border.width: 1
    border.color: root.enabled ? Theme.border : Theme.muted
    Icon {
      anchors.centerIn: parent
      width: 12
      height: 12
      name: "check"
      color: Theme.surface
      visible: root.checked
    }
  }
  Accessible.name: text
  FocusRing {
    control: root
  }
}
