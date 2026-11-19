import QtQuick
import QtQuick.Controls

Button {
  id: root

  property var look: ({})
  property bool primary: false
  property string trailing: ""

  implicitHeight: Math.max(42 * (root.look.textScale || 1), root.look.largeTargets ? 44 : 0)
  font.family: look.font || "Inter"
  font.pixelSize: Math.round(13 * (root.look.textScale || 1))
  hoverEnabled: true
  padding: 12
  Accessible.name: text

  background: Rectangle {
    color: root.primary ? (root.look.accent || "#ffffff") : (root.hovered ? (root.look.raised || "#101010") : "transparent")
    radius: Math.min(8, root.look.radius || 0)
    border.width: root.activeFocus ? 2 : root.primary ? 0 : 1
    border.color: root.activeFocus ? (root.look.accent || "#ffffff") : (root.look.border || "#ffffff")
    opacity: root.enabled ? 1 : 0.45
  }

  contentItem: Item {
    implicitWidth: label.implicitWidth + (root.trailing ? 24 : 0)
    implicitHeight: label.implicitHeight

    Text {
      id: label

      anchors.left: parent.left
      anchors.verticalCenter: parent.verticalCenter
      text: root.text
      font: root.font
      textFormat: Text.PlainText
      color: root.primary ? (root.look.onAccent || "#000000") : (root.look.text || "#ffffff")
      opacity: root.enabled ? 1 : 0.45
      Accessible.ignored: true
    }

    Text {
      anchors.right: parent.right
      anchors.verticalCenter: parent.verticalCenter
      visible: root.trailing !== ""
      text: root.trailing
      font: root.font
      color: label.color
      opacity: label.opacity
      Accessible.ignored: true
    }
  }
}
