import QtQuick
import QtQuick.Layouts
import "../core"
import "../components"

ColumnLayout {
  id: root
  property bool configurationEditor: false
  function edit(key, value) {
    if (configurationEditor)
      Bridge.configure(key, value);
    else
      Bridge.set(key, value);
  }
  spacing: 14
  ActionButton {
    text: "Usar fondo del tema"
    selected: !Bridge.settings.wallpaper
    onClicked: root.edit("wallpaper", "")
  }
  GridLayout {
    columns: 2
    rowSpacing: 14
    columnSpacing: 14
    Layout.fillWidth: true
    Repeater {
      model: Bridge.wallpapers
      ColumnLayout {
        id: option
        required property var modelData
        Layout.fillWidth: true
        spacing: 6
        Rectangle {
          Layout.fillWidth: true
          implicitHeight: 100
          color: Theme.surface
          border.width: 1
          border.color: Bridge.settings.wallpaper === option.modelData.path ? Theme.border : Theme.separator
          Image {
            anchors.fill: parent
            anchors.margins: 1
            source: option.modelData.url
            sourceSize.width: 400
            fillMode: Image.PreserveAspectCrop
            asynchronous: true
          }
          MouseArea {
            anchors.fill: parent
            cursorShape: Qt.PointingHandCursor
            onClicked: root.edit("wallpaper", option.modelData.path)
          }
        }
        Label {
          text: option.modelData.name
          font.pixelSize: 11
          Layout.fillWidth: true
        }
      }
    }
  }
  Rule {}
  SectionTitle {
    text: "Carpeta de imágenes"
  }
  Field {
    Layout.fillWidth: true
    placeholderText: "~/Pictures/Wallpapers"
    text: Bridge.settings.wallpaperDirectory || ""
    onEditingFinished: root.edit("wallpaperDirectory", text)
  }
  ActionButton {
    text: "Actualizar"
    onClicked: Bridge.perform("refresh", {
      name: "wallpapers"
    })
  }
}
