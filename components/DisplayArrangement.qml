import QtQuick
import QtQuick.Layouts
import "../core"
import "../core/displays.js" as Displays
import "." as Controls

Rectangle {
  id: root
  property var outputs: []
  property var information: []
  property string selected: ""
  property bool interactive: true
  readonly property var roots: outputs.filter(output => output.enabled && !output.mirror)
  readonly property var bounds: {
    if (!roots.length)
      return {
        x: 0,
        y: 0,
        width: 1920,
        height: 1080
      };
    const minX = Math.min(...roots.map(output => output.x));
    const minY = Math.min(...roots.map(output => output.y));
    return {
      x: minX,
      y: minY,
      width: Math.max(...roots.map(output => output.x + dimensions(output).width)) - minX,
      height: Math.max(...roots.map(output => output.y + dimensions(output).height)) - minY
    };
  }
  readonly property real factor: Math.min((width - 60) / Math.max(1, bounds.width), (height - 60) / Math.max(1, bounds.height))
  readonly property real originX: (width - bounds.width * factor) / 2
  readonly property real originY: (height - bounds.height * factor) / 2
  signal selectedOutput(string name)
  signal moved(string name, int x, int y)
  Layout.fillWidth: true
  implicitHeight: 220
  color: Theme.background
  radius: Theme.radiusFor("panel")
  border.width: 1
  border.color: Theme.separator
  clip: true

  function dimensions(output) {
    return Displays.size(output, information.find(info => info.name === output.name));
  }

  Repeater {
    model: root.roots
    Rectangle {
      id: screen
      required property var modelData
      readonly property var dimensions: root.dimensions(modelData)
      function restorePosition() {
        x = Qt.binding(() => root.originX + (modelData.x - root.bounds.x) * root.factor);
        y = Qt.binding(() => root.originY + (modelData.y - root.bounds.y) * root.factor);
      }
      x: root.originX + (modelData.x - root.bounds.x) * root.factor
      y: root.originY + (modelData.y - root.bounds.y) * root.factor
      width: Math.max(54, dimensions.width * root.factor)
      height: Math.max(45, dimensions.height * root.factor)
      color: root.selected === modelData.name ? Theme.raised : Theme.surface
      border.width: root.selected === modelData.name ? 2 : 1
      border.color: root.selected === modelData.name ? Theme.accent : Theme.border
      radius: Theme.radiusFor("field")
      activeFocusOnTab: root.interactive
      Keys.onReturnPressed: root.selectedOutput(modelData.name)
      Keys.onSpacePressed: root.selectedOutput(modelData.name)
      Column {
        anchors.centerIn: parent
        width: parent.width - 12
        spacing: 4
        Controls.Label {
          width: parent.width
          horizontalAlignment: Text.AlignHCenter
          text: String(root.outputs.findIndex(output => output.name === screen.modelData.name) + 1)
          font.pixelSize: Math.min(28, screen.height * .26)
        }
        Controls.Label {
          width: parent.width
          horizontalAlignment: Text.AlignHCenter
          text: screen.modelData.name
          font.pixelSize: Theme.fontPx(10)
          elide: Text.ElideRight
        }
        Controls.Label {
          width: parent.width
          horizontalAlignment: Text.AlignHCenter
          visible: root.outputs.some(output => output.enabled && output.mirror === screen.modelData.name)
          text: "Duplicada"
          color: Theme.muted
          font.pixelSize: Theme.fontPx(9)
        }
      }
      MouseArea {
        property bool moved: false
        anchors.fill: parent
        enabled: root.interactive
        cursorShape: pressed ? Qt.ClosedHandCursor : Qt.OpenHandCursor
        drag.target: screen
        onPressed: {
          moved = false;
          root.selectedOutput(screen.modelData.name);
        }
        onPositionChanged: if (drag.active)
          moved = true
        onReleased: {
          if (moved)
            root.moved(screen.modelData.name, Math.round((screen.x - root.originX) / root.factor + root.bounds.x), Math.round((screen.y - root.originY) / root.factor + root.bounds.y));
          screen.restorePosition();
        }
      }
      Accessible.role: Accessible.Button
      Accessible.name: "Pantalla " + modelData.name
      Accessible.description: "Selecciona la pantalla. También puedes cambiar su posición con los campos X e Y."
      Accessible.selected: root.selected === modelData.name
      Accessible.onPressAction: if (root.interactive)
        root.selectedOutput(modelData.name)
      Controls.FocusRing {
        control: screen
      }
    }
  }
  Controls.Label {
    anchors.centerIn: parent
    visible: root.roots.length === 0
    text: "Activa una pantalla para organizar el escritorio"
    color: Theme.muted
  }
}
