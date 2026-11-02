import QtQuick
import QtQuick.Window
import "../core"
import "icons.js" as Icons

Item {
  id: root
  property string name: "grid"
  property color color: Theme.text
  implicitWidth: 20
  implicitHeight: 20
  readonly property string stroke: String(Qt.rgba(color.r, color.g, color.b, 1))
  Image {
    anchors.fill: parent
    // Shared SVG images obey ancestor clipping, including the software renderer.
    source: "data:image/svg+xml;charset=utf-8," + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"><path d="' + (Icons.paths[root.name] || Icons.paths.grid) + '" fill="none" stroke="' + root.stroke + '" stroke-opacity="' + root.color.a + '" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round"/></svg>')
    sourceSize.width: Math.max(1, Math.ceil(root.width * Screen.devicePixelRatio))
    sourceSize.height: Math.max(1, Math.ceil(root.height * Screen.devicePixelRatio))
    fillMode: Image.PreserveAspectFit
    cache: true
  }
  Accessible.ignored: true
}
