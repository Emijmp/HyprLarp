import QtQuick
import "../core"

Rectangle {
  color: Theme.background
  Image {
    anchors.fill: parent
    source: Bridge.settings.wallpaper ? "file://" + Bridge.settings.wallpaper : ""
    fillMode: Image.PreserveAspectCrop
    asynchronous: true
    sourceSize.width: Math.min(3840, parent.width * 1.5)
  }
}
