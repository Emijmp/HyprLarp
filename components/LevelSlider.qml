import QtQuick
import QtQuick.Controls
import "../core"

Slider {
  id: root
  property bool settingsControl: false
  readonly property bool trackingSettingsEdit: settingsControl && pressed
  onTrackingSettingsEditChanged: {
    if (trackingSettingsEdit)
      Bridge.beginSettingsEdit();
    else
      Bridge.endSettingsEdit();
  }
  Component.onDestruction: if (trackingSettingsEdit)
    Bridge.endSettingsEdit()
  from: 0
  to: 1
  implicitHeight: 20
  background: Rectangle {
    x: root.leftPadding
    y: root.topPadding + root.availableHeight / 2 - 1
    width: root.availableWidth
    height: 2
    radius: 0
    color: Theme.separator
    Rectangle {
      width: root.visualPosition * parent.width
      height: parent.height
      color: Theme.accent
    }
  }
  handle: Rectangle {
    x: root.leftPadding + root.visualPosition * (root.availableWidth - width)
    y: root.topPadding + root.availableHeight / 2 - height / 2
    width: 6
    height: 12
    radius: 0
    color: Theme.accent
  }
}
