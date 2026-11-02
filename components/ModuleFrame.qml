import QtQuick
import "../core"

Rectangle {
  id: root
  property var configuration: Bridge.settings
  property bool active: false
  property bool hovered: false
  radius: configuration.moduleRadius ?? 2
  color: Theme.alpha(hovered ? Theme.raised : Theme.moduleSurface, configuration.moduleBackgroundOpacity ?? 1)
  border.width: configuration.moduleBorderWidth ?? 1
  border.color: active || hovered ? Theme.border : Theme.separator
  Rectangle {
    visible: Theme.detail("moduleIndicators") && root.active
    anchors.right: parent.right
    anchors.bottom: parent.bottom
    anchors.margins: root.border.width + 2
    width: 2
    height: 2
    color: Theme.accent
  }
}
