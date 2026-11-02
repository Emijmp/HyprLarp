import QtQuick
import "../core"

Rectangle {
  id: root
  property var screen: null
  property var configuration: BarLayout.forScreen(screen)
  readonly property bool vertical: geometry.vertical
  BarGeometry {
    id: geometry
    configuration: root.configuration
  }
  radius: Theme.radiusFor("bar")
  color: Theme.alpha(Theme.surface, configuration.barOpacity ?? 1)
  border.width: geometry.border
  border.color: Theme.border
  clip: true
  MouseArea {
    anchors.fill: parent
    acceptedButtons: Qt.RightButton
    onClicked: ShellState.open("settings", root.screen)
  }
  Flickable {
    id: viewport
    anchors.fill: parent
    anchors.leftMargin: geometry.paddingX + geometry.border
    anchors.rightMargin: geometry.paddingX + geometry.border
    anchors.topMargin: geometry.paddingY + geometry.border
    anchors.bottomMargin: geometry.paddingY + geometry.border
    readonly property real needed: start.extent + center.extent + end.extent + 2 * geometry.spacing
    contentWidth: geometry.vertical ? width : Math.max(width, needed)
    contentHeight: geometry.vertical ? Math.max(height, needed) : height
    flickableDirection: geometry.vertical ? Flickable.VerticalFlick : Flickable.HorizontalFlick
    boundsBehavior: Flickable.StopAtBounds
    clip: true
    readonly property real extent: geometry.vertical ? contentHeight : contentWidth
    ModuleStrip {
      id: start
      names: BarLayout.modules(root.configuration, "start")
      configuration: root.configuration
      guide: geometry
      screen: root.screen
      readonly property real extent: geometry.vertical ? implicitHeight : implicitWidth
      width: geometry.vertical ? viewport.width : implicitWidth
      height: geometry.vertical ? implicitHeight : viewport.height
    }
    ModuleStrip {
      id: center
      names: BarLayout.modules(root.configuration, "center")
      configuration: root.configuration
      guide: geometry
      screen: root.screen
      readonly property real extent: geometry.vertical ? implicitHeight : implicitWidth
      readonly property real offset: Math.max(start.extent + geometry.spacing, Math.min((viewport.extent - extent) / 2, viewport.extent - end.extent - extent - geometry.spacing))
      x: geometry.vertical ? 0 : offset
      y: geometry.vertical ? offset : 0
      width: geometry.vertical ? viewport.width : implicitWidth
      height: geometry.vertical ? implicitHeight : viewport.height
    }
    ModuleStrip {
      id: end
      names: BarLayout.modules(root.configuration, "end")
      configuration: root.configuration
      guide: geometry
      screen: root.screen
      readonly property real extent: geometry.vertical ? implicitHeight : implicitWidth
      x: geometry.vertical ? 0 : viewport.extent - extent
      y: geometry.vertical ? viewport.extent - extent : 0
      width: geometry.vertical ? viewport.width : implicitWidth
      height: geometry.vertical ? implicitHeight : viewport.height
    }
  }
}
