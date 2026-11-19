import QtQuick
import QtQuick.Window
import "../core"
import "icons.js" as Icons
import "../assets/branding.js" as Branding

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
    source: Branding.supports(root.name) ? Branding.source(root.name, root.stroke, root.color.a) : Icons.source(root.name, root.stroke, root.color.a)
    sourceSize.width: Math.max(1, Math.ceil(root.width * Screen.devicePixelRatio))
    sourceSize.height: Math.max(1, Math.ceil(root.height * Screen.devicePixelRatio))
    fillMode: Image.PreserveAspectFit
    cache: true
  }
  Accessible.ignored: true
}
