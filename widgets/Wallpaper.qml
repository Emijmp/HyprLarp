import QtQuick
import QtQuick.Window
import "../core"
import "../core/paths.js" as Paths

Rectangle {
  id: root
  readonly property bool external: Bridge.externalWallpaper
  color: Theme.background
  Image {
    anchors.fill: parent
    source: root.external ? "" : Paths.fileUrl(Bridge.settings.wallpaper)
    fillMode: Image.PreserveAspectCrop
    asynchronous: true
    sourceSize.width: Math.min(3840, Math.ceil(parent.width * Screen.devicePixelRatio))
    sourceSize.height: Math.min(2160, Math.ceil(parent.height * Screen.devicePixelRatio))
    cache: false
  }
  Text {
    visible: root.external && Bridge.preview
    anchors.centerIn: parent
    text: "Fondo externo · Waypaper"
    color: Theme.muted
    font.family: Theme.font
    font.pixelSize: Theme.fontPx(12)
  }
}
