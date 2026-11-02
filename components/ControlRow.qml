import QtQuick
import QtQuick.Layouts
import "../core"

Item {
  id: root
  property string title: ""
  property string detail: ""
  property bool divider: false
  signal clicked
  Layout.fillWidth: true
  implicitHeight: 30
  activeFocusOnTab: true
  Keys.onReturnPressed: clicked()
  Keys.onSpacePressed: clicked()
  Rectangle {
    anchors.fill: parent
    color: hover.containsMouse ? Theme.raised : "transparent"
  }
  Rectangle {
    visible: Theme.decorated
    x: 1
    anchors.verticalCenter: parent.verticalCenter
    width: 2
    height: hover.containsMouse || root.activeFocus ? 12 : 4
    color: hover.containsMouse || root.activeFocus ? Theme.border : Theme.separator
  }
  RowLayout {
    anchors.fill: parent
    anchors.leftMargin: Theme.decorated ? 10 : 2
    anchors.rightMargin: 2
    Label {
      text: root.title
      font.pixelSize: 12
      Layout.fillWidth: true
    }
    Label {
      text: root.detail
      font.pixelSize: 11
      color: Theme.muted
      Layout.maximumWidth: root.width * 0.52
    }
    Icon {
      name: "chevron"
      color: hover.containsMouse ? Theme.text : Theme.muted
      Layout.preferredWidth: 12
      Layout.preferredHeight: 12
    }
  }
  Rectangle {
    visible: root.divider
    anchors.left: parent.left
    anchors.right: parent.right
    anchors.bottom: parent.bottom
    height: 1
    color: Theme.separator
  }
  MouseArea {
    id: hover
    anchors.fill: parent
    hoverEnabled: true
    cursorShape: Qt.PointingHandCursor
    onClicked: root.clicked()
  }
  Accessible.role: Accessible.Button
  Accessible.name: title + " " + detail
}
