import QtQuick
import QtQuick.Window
import "branding.js" as Branding

Item {
  id: root
  property string name: "hyprlarp"
  property color color: "#ffffff"
  implicitWidth: 32
  implicitHeight: 32
  Image {
    anchors.fill: parent
    source: Branding.source(root.name, String(Qt.rgba(root.color.r, root.color.g, root.color.b, 1)), root.color.a)
    sourceSize.width: Math.max(1, Math.ceil(root.width * Screen.devicePixelRatio))
    sourceSize.height: Math.max(1, Math.ceil(root.height * Screen.devicePixelRatio))
    fillMode: Image.PreserveAspectFit
    cache: true
  }
  Accessible.ignored: true
}
