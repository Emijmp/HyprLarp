import QtQuick
import Quickshell
import Quickshell.Wayland
import "../core"
import "../components"

Scope {
  BarGeometry {
    id: activeLayout
    configuration: BarLayout.forScreen(ShellState.activeScreen)
  }
  Variants {
    model: Quickshell.screens
    Scope {
      id: output
      required property var modelData
      BarGeometry {
        id: layout
        configuration: BarLayout.forScreen(output.modelData)
      }
      LazyLoader {
        active: Bridge.ready && !Bridge.externalWallpaper
        component: PanelWindow {
          screen: output.modelData
          anchors {
            top: true
            bottom: true
            left: true
            right: true
          }
          exclusionMode: ExclusionMode.Ignore
          WlrLayershell.layer: WlrLayer.Background
          WlrLayershell.namespace: "hyprlarp-wallpaper"
          mask: Region {}
          Wallpaper {
            anchors.fill: parent
          }
        }
      }
      PanelWindow {
        id: bar
        readonly property var placementMargins: layout.windowMargins(screen.width, screen.height)
        visible: layout.configuration.barEnabled !== false
        screen: output.modelData
        color: "transparent"
        anchors {
          top: layout.windowAnchors.top
          bottom: layout.windowAnchors.bottom
          left: layout.windowAnchors.left
          right: layout.windowAnchors.right
        }
        margins {
          top: bar.placementMargins.top
          bottom: bar.placementMargins.bottom
          left: bar.placementMargins.left
          right: bar.placementMargins.right
        }
        implicitWidth: layout.vertical ? layout.size : layout.length(screen.width)
        implicitHeight: layout.vertical ? layout.length(screen.height) : layout.size
        exclusiveZone: layout.exclusiveZone
        exclusionMode: layout.reserveSpace ? ExclusionMode.Normal : ExclusionMode.Ignore
        WlrLayershell.layer: WlrLayer.Top
        WlrLayershell.namespace: "hyprlarp-bar"
        BackgroundEffect.blurRegion: layout.configuration.barBlur ? blurRegion : null
        Region {
          id: blurRegion
          item: barContent
        }
        BarContent {
          id: barContent
          anchors.fill: parent
          screen: bar.screen
        }
      }
    }
  }
  PanelWindow {
    id: presentationWindow
    visible: Presentation.active
    color: "transparent"
    implicitWidth: 1
    implicitHeight: 1
    anchors {
      bottom: true
      left: true
    }
    exclusionMode: ExclusionMode.Ignore
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.namespace: "hyprlarp-presentation"
    mask: Region {}
    IdleInhibitor {
      window: presentationWindow
      enabled: Presentation.active
    }
  }
  PanelWindow {
    visible: ShellState.captureRemaining > 0
    color: "transparent"
    anchors {
      top: true
    }
    margins.top: 70
    implicitWidth: captureCountdown.implicitWidth
    implicitHeight: captureCountdown.implicitHeight
    exclusionMode: ExclusionMode.Ignore
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.namespace: "hyprlarp-capture-countdown"
    CaptureCountdown {
      id: captureCountdown
      anchors.fill: parent
    }
  }
  PanelWindow {
    visible: ShellState.panel !== ""
    screen: ShellState.activeScreen || Quickshell.screens[0]
    color: "transparent"
    anchors {
      top: true
      bottom: true
      left: true
      right: true
    }
    exclusionMode: ExclusionMode.Ignore
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.namespace: "hyprlarp-panel"
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.Exclusive
    PanelOverlay {
      anchors.fill: parent
    }
  }
  PanelWindow {
    visible: Notices.popups.length > 0
    screen: ShellState.activeScreen || Quickshell.screens[0]
    color: "transparent"
    anchors {
      top: true
      right: true
    }
    margins {
      top: activeLayout.position === "top" ? activeLayout.size + activeLayout.margins.top + 8 : 8
      right: activeLayout.position === "right" ? activeLayout.size + activeLayout.margins.right + 8 : 8
    }
    implicitWidth: 340
    implicitHeight: toasts.implicitHeight
    exclusionMode: ExclusionMode.Ignore
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.namespace: "hyprlarp-notifications"
    Column {
      id: toasts
      width: parent.width
      spacing: 8
      Repeater {
        model: Notices.popups
        NotificationCard {
          required property var modelData
          width: toasts.width
          entry: modelData
          toast: true
        }
      }
    }
  }
}
