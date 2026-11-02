import QtQuick
import QtQuick.Layouts
import "../core"
import "../components"

ColumnLayout {
  spacing: 16
  MediaCard {
    Layout.fillWidth: true
  }
  Label {
    visible: Media.player === null
    text: "Los reproductores con MPRIS aparecerán aquí."
    color: Theme.muted
    font.pixelSize: 11
    wrapMode: Text.WordWrap
    Layout.fillWidth: true
  }
  ColumnLayout {
    visible: Media.player !== null
    Layout.fillWidth: true
    spacing: 6
    LevelSlider {
      Layout.fillWidth: true
      from: 0
      to: Media.player ? Math.max(1, Media.player.length) : 1
      value: Media.player ? Media.player.position : 0
      enabled: !Bridge.preview && Media.player !== null && Media.player.canSeek && Media.player.positionSupported
      onMoved: if (Media.player)
        Media.player.position = value
    }
    RowLayout {
      Label {
        text: Media.time(Media.player ? Media.player.position : 0)
        color: Theme.muted
        font.pixelSize: 10
        font.family: Theme.mono
      }
      Item {
        Layout.fillWidth: true
      }
      Label {
        text: Media.time(Media.player ? Media.player.length : 0)
        color: Theme.muted
        font.pixelSize: 10
        font.family: Theme.mono
      }
    }
  }
  Repeater {
    model: Media.players
    ActionButton {
      required property var modelData
      text: modelData.identity
      selected: Media.player === modelData
      onClicked: Media.selected = modelData.dbusName
    }
  }
}
