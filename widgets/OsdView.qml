import QtQuick
import QtQuick.Layouts
import "../core"
import "../components"

Rectangle {
  implicitWidth: Theme.px(280)
  implicitHeight: Theme.controlHeight(66)
  Accessible.role: Accessible.StatusBar
  Accessible.name: Osd.title + " · " + (Osd.muted ? "Silenciado" : Math.round(Osd.value * 100) + "%")
  onVisibleChanged: if (visible)
    Accessible.announce(Accessible.name, Accessible.Polite)
  visible: Osd.visible
  color: Theme.surface
  radius: Theme.radiusFor("panel")
  border.width: 1
  border.color: Theme.border
  ColumnLayout {
    anchors.fill: parent
    anchors.margins: 12
    spacing: 8
    RowLayout {
      Icon {
        name: Osd.icon
        Layout.preferredWidth: 18
        Layout.preferredHeight: 18
      }
      Label {
        text: Osd.title + (Osd.demo ? " · Prueba" : "")
        font.pixelSize: Theme.fontPx(12)
        Layout.fillWidth: true
      }
      Label {
        text: Osd.muted ? "Silenciado" : Math.round(Osd.value * 100) + "%"
        font.pixelSize: Theme.fontPx(11)
        font.family: Theme.mono
      }
    }
    Rectangle {
      Layout.fillWidth: true
      implicitHeight: 2
      color: Theme.separator
      Rectangle {
        height: parent.height
        width: parent.width * (Osd.muted ? 0 : Osd.value)
        color: Theme.text
      }
    }
  }
}
