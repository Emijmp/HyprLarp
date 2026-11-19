import QtQuick
import "../core"
import "../core/panelGeometry.js" as Geometry

FocusScope {
  id: root
  property alias surface: panel
  readonly property string layoutMode: Bridge.settings.panelLayout || "floating"
  readonly property var availableArea: Geometry.availableArea(width, height, {
    layoutMode: layoutMode,
    position: layout.position,
    gap: layout.configuration.barEnabled !== false ? layout.size + layout.edgeMargin + 8 : 8,
    margins: layout.margins
  })
  readonly property real surfaceWidth: Geometry.widthFor(availableArea, layoutMode, panel.implicitWidth, Theme.textScale)
  readonly property var placement: Geometry.place(availableArea, surfaceWidth, panel.implicitHeight, {
    layoutMode: layoutMode,
    panelName: ShellState.panel,
    position: layout.position
  })
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
    width: root.surfaceWidth
    height: root.placement.height
    availableHeight: root.availableArea.height
    x: root.placement.x
    y: root.placement.y
  }
}
