import QtQuick
import "../core"

Item {
  id: root
  property int inset: 4
  property int length: 7
  property color color: Theme.muted
  visible: Theme.detail("panelCorners")
  enabled: false
  Rectangle {
    x: root.inset
    y: root.inset
    width: root.length
    height: 1
    color: root.color
  }
  Rectangle {
    x: root.inset
    y: root.inset
    width: 1
    height: root.length
    color: root.color
  }
  Rectangle {
    x: root.width - root.inset - root.length
    y: root.height - root.inset - 1
    width: root.length
    height: 1
    color: root.color
  }
  Rectangle {
    x: root.width - root.inset - 1
    y: root.height - root.inset - root.length
    width: 1
    height: root.length
    color: root.color
  }
}
