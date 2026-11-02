import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../core"

Control {
  id: root
  property string text: ""
  property string icon: ""
  property bool accent: false
  property bool selected: false
  property bool danger: false
  property string hint: ""
  signal clicked
  implicitWidth: contentItem.implicitWidth + 16
  implicitHeight: 30
  leftPadding: 8
  rightPadding: 8
  hoverEnabled: true
  activeFocusOnTab: true
  opacity: enabled ? 1 : 0.35
  Keys.onReturnPressed: if (enabled)
    clicked()
  Keys.onSpacePressed: if (enabled)
    clicked()
  background: Rectangle {
    radius: Theme.radiusFor("button")
    color: interaction.containsMouse || interaction.pressed ? Theme.raised : "transparent"
    Behavior on color {
      ColorAnimation {
        duration: Theme.duration
      }
    }
    border.width: root.accent || root.activeFocus ? 1 : 0
    border.color: Theme.border
    Rectangle {
      anchors.left: parent.left
      anchors.right: parent.right
      anchors.leftMargin: Theme.decorated ? 6 : 0
      anchors.rightMargin: Theme.decorated ? 6 : 0
      anchors.bottom: parent.bottom
      height: root.selected ? 1 : 0
      color: Theme.accent
    }
  }
  contentItem: RowLayout {
    spacing: 6
    Icon {
      visible: root.icon !== ""
      name: root.icon
      color: Theme.text
      implicitWidth: 14
      implicitHeight: 14
    }
    Label {
      visible: root.text !== ""
      text: root.text
      color: root.danger ? Theme.danger : Theme.text
      font.pixelSize: 12
      Layout.alignment: Qt.AlignLeft | Qt.AlignVCenter
    }
  }
  MouseArea {
    id: interaction
    anchors.fill: parent
    hoverEnabled: true
    cursorShape: Qt.PointingHandCursor
    onClicked: {
      root.forceActiveFocus();
      root.clicked();
    }
  }
  Hint {
    visible: interaction.containsMouse && root.hint !== ""
    text: root.hint
  }
  Accessible.name: text || hint || icon
  Accessible.role: Accessible.Button
  Accessible.onPressAction: if (enabled)
    clicked()
}
