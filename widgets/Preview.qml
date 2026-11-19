import QtQuick
import Quickshell
import "../core"
import "../components"

Item {
  id: root
  Wallpaper {
    anchors.fill: parent
  }
  BarContent {
    x: BarLayout.position === "right" ? root.width - width - BarLayout.margins.right : BarLayout.vertical ? BarLayout.margins.left : BarLayout.offset(root.width)
    y: BarLayout.position === "bottom" ? root.height - height - BarLayout.margins.bottom : BarLayout.vertical ? BarLayout.offset(root.height) : BarLayout.margins.top
    width: BarLayout.vertical ? BarLayout.size : BarLayout.length(root.width)
    height: BarLayout.vertical ? BarLayout.length(root.height) : BarLayout.size
  }
  Label {
    anchors.left: parent.left
    anchors.bottom: parent.bottom
    anchors.margins: 16
    anchors.leftMargin: BarLayout.position === "left" ? BarLayout.size + BarLayout.margins.left + 8 : 16
    anchors.bottomMargin: BarLayout.position === "bottom" ? BarLayout.size + BarLayout.margins.bottom + 8 : 16
    text: "HyprLarp · Vista previa · Controles del sistema desactivados"
    font.pixelSize: Theme.fontPx(10)
    color: Theme.muted
  }
  PanelOverlay {
    anchors.fill: parent
  }
  OsdView {
    x: (root.width - width) / 2
    y: Bridge.settings.osdPosition === "top" ? 64 : root.height - height - 64
    width: implicitWidth
    height: implicitHeight
    z: 20
  }
  CaptureCountdown {
    anchors.horizontalCenter: parent.horizontalCenter
    y: 70
  }
  Timer {
    interval: 1200
    running: Quickshell.env("HYPRLARP_OSD_DEMO") === "1"
    onTriggered: Osd.show("brightness", 0.6, false, true)
  }
  Timer {
    interval: 2500
    running: !!Quickshell.env("HYPRLARP_CAPTURE") && Quickshell.env("HYPRLARP_SMOKE_TEST") !== "1"
    onTriggered: root.grabToImage(result => {
      console.log("Preview saved:", result.saveToFile(Quickshell.env("HYPRLARP_CAPTURE")));
      Qt.quit();
    })
  }
}
