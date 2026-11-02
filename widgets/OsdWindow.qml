import QtQuick
import Quickshell
import Quickshell.Wayland
import "../core"

PanelWindow {
  visible: Osd.visible
  screen: Quickshell.screens.find(screen => screen.name === Compositor.focusedScreenName) || ShellState.activeScreen || Quickshell.screens[0]
  color: "transparent"
  implicitWidth: 280
  implicitHeight: 66
  anchors {
    top: Bridge.settings.osdPosition === "top"
    bottom: Bridge.settings.osdPosition !== "top"
  }
  margins {
    top: 64
    bottom: 64
  }
  exclusionMode: ExclusionMode.Ignore
  WlrLayershell.layer: WlrLayer.Overlay
  WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
  WlrLayershell.namespace: "hyprlarp-osd"
  mask: Region {}
  OsdView {
    anchors.fill: parent
  }
}
