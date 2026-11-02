import QtQuick
import "../core"

FocusScope {
  id: root
  visible: ShellState.panel !== ""
  BarGeometry {
    id: layout
    configuration: BarLayout.forScreen(ShellState.activeScreen)
  }
  focus: visible
  onVisibleChanged: if (visible)
    forceActiveFocus()
  Keys.onEscapePressed: ShellState.close()
  MouseArea {
    anchors.fill: parent
    onClicked: ShellState.close()
  }
  PanelSurface {
    id: panel
    readonly property int gap: layout.size + layout.edgeMargin + 8
    width: Math.min(implicitWidth, root.width - 16)
    height: implicitHeight
    availableHeight: Math.max(180, root.height - (layout.vertical ? 16 : gap + 8))
    x: ShellState.panel === "launcher" ? (root.width - width) / 2 : layout.position === "left" ? gap : root.width - width - (layout.position === "right" ? gap : Math.max(8, layout.margins.right))
    y: ShellState.panel === "launcher" ? (root.height - height) / 2 : layout.position === "bottom" ? root.height - height - gap : layout.vertical ? 8 : gap
  }
}
