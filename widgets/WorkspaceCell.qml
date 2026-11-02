import QtQuick
import "../core"
import "../components"

Item {
  id: root
  required property var entry
  property var screen: null
  property int fontSize: 12
  property int workspaceCount: 5
  implicitWidth: Math.max(20, Math.ceil(Math.min(entry.label.length, 12) * fontSize * 0.65) + 8)
  implicitHeight: Math.max(20, fontSize + 4)
  activeFocusOnTab: true
  function activate() {
    Compositor.activate(entry, screen);
  }
  Keys.onReturnPressed: activate()
  Keys.onSpacePressed: activate()
  Rectangle {
    anchors.fill: parent
    color: root.entry.active ? Theme.text : mouse.containsMouse || root.activeFocus ? Theme.raised : "transparent"
    border.width: root.entry.active ? 2 : mouse.containsMouse || root.activeFocus ? 1 : 0
    border.color: root.entry.active || root.activeFocus ? Theme.border : Theme.separator
    radius: Theme.radiusFor("workspace")
  }
  Label {
    anchors.fill: parent
    text: root.entry.label
    font.family: Theme.mono
    font.pixelSize: root.fontSize
    font.weight: root.entry.active ? Font.DemiBold : Font.Normal
    horizontalAlignment: Text.AlignHCenter
    color: root.entry.active ? Theme.surface : root.entry.occupied ? Theme.text : Theme.muted
    font.underline: !!root.entry.urgent
  }
  MouseArea {
    id: mouse
    anchors.fill: parent
    hoverEnabled: true
    cursorShape: Qt.PointingHandCursor
    acceptedButtons: Qt.LeftButton | Qt.RightButton
    onClicked: event => {
      if (event.button === Qt.RightButton) {
        BarEditor.target = root.screen ? root.screen.name : "";
        ShellState.openSettings("Bar");
      } else
        root.activate();
    }
    onWheel: event => {
      const delta = event.angleDelta.y || event.pixelDelta.y;
      if (delta)
        Compositor.cycle(root.screen, delta > 0 ? -1 : 1, root.workspaceCount);
      else
        event.accepted = false;
    }
  }
  Hint {
    visible: mouse.containsMouse
    text: root.entry.gap ? "Espacios ocultos: " + root.entry.name + " · Clic: " + root.entry.target.label + " · Rueda: recorrer espacios" : "Espacio " + root.entry.name + " · Rueda: recorrer espacios"
  }
  Accessible.name: entry.gap ? "Espacios ocultos: " + entry.name : "Espacio " + entry.name
  Accessible.role: Accessible.Button
  Accessible.onPressAction: activate()
}
