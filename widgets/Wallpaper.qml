import QtQuick
import "../core"
import "../core/paths.js" as Paths

Rectangle {
  color: Theme.background
  Image {
    anchors.fill: parent
    source: Paths.fileUrl(Bridge.settings.wallpaper)
    fillMode: Image.PreserveAspectCrop
    asynchronous: true
    sourceSize.width: Math.min(3840, parent.width * 1.5)
  }
}
