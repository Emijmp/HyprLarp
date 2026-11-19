import QtQuick
import QtQuick.Layouts
import "../core"

Item {
  id: root
  property bool compact: false
  implicitHeight: content.implicitHeight
  ColumnLayout {
    id: content
    anchors.left: parent.left
    anchors.right: parent.right
    spacing: 8
    Label {
      text: Media.player ? Media.title : "Sin reproducción activa"
      font.pixelSize: Theme.fontPx(14)
      Layout.fillWidth: true
      wrapMode: Text.WordWrap
    }
    Label {
      visible: Media.player !== null
      text: Media.artist
      color: Theme.muted
      Layout.fillWidth: true
      font.pixelSize: Theme.fontPx(12)
    }
    RowLayout {
      visible: Media.player !== null
      spacing: 4
      ActionButton {
        icon: "previous"
        hint: "Anterior"
        enabled: !Bridge.preview && Media.player !== null && Media.player.canGoPrevious
        onClicked: Media.previous()
      }
      ActionButton {
        icon: Media.player && Media.player.isPlaying ? "pause" : "play"
        hint: "Reproducir / pausar"
        enabled: !Bridge.preview && Media.player !== null && Media.player.canTogglePlaying
        onClicked: Media.playPause()
      }
      ActionButton {
        icon: "next"
        hint: "Siguiente"
        enabled: !Bridge.preview && Media.player !== null && Media.player.canGoNext
        onClicked: Media.next()
      }
      Item {
        Layout.fillWidth: true
      }
    }
  }
}
