import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import QtQuick.Layouts
import "../core"
import "../components"

ColumnLayout {
  id: root
  property bool configurationEditor: false
  property string directoryError: ""
  readonly property int imageCount: Bridge.wallpapers.length
  function edit(key, value) {
    if (configurationEditor)
      Bridge.configure(key, value);
    else
      Bridge.set(key, value);
  }
  function chooseDirectory(value) {
    directoryError = "";
    edit("wallpaperDirectory", String(value));
    Bridge.flush();
  }
  function openRequestedDirectory() {
    if (configurationEditor && ShellState.wallpaperDirectoryRequested) {
      ShellState.wallpaperDirectoryRequested = false;
      Qt.callLater(() => folderDialog.open());
    }
  }
  onConfigurationEditorChanged: openRequestedDirectory()
  spacing: 12
  SectionTitle {
    text: "Carpeta de fondos"
  }
  Field {
    id: directory
    Layout.fillWidth: true
    placeholderText: "~/Pictures/Wallpapers"
    text: Bridge.settings.wallpaperDirectory || ""
    onAccepted: root.chooseDirectory(text)
  }
  RowLayout {
    ActionButton {
      text: "Elegir carpeta…"
      onClicked: {
        if (root.configurationEditor || Bridge.preview)
          folderDialog.open();
        else
          ShellState.browseWallpaperDirectory();
      }
    }
    ActionButton {
      text: "Aplicar ruta"
      onClicked: root.chooseDirectory(directory.text)
    }
    ActionButton {
      text: "Actualizar"
      enabled: !Bridge.isBusy("refresh")
      onClicked: Bridge.perform("refresh", {
        name: "wallpapers"
      })
    }
  }
  Label {
    text: root.directoryError || Bridge.wallpaperState.error || (Bridge.wallpaperState.directory ? "Buscando en " + Bridge.wallpaperState.directory : "Elige una carpeta o escribe su ruta.")
    Layout.fillWidth: true
    font.pixelSize: 10
    color: Theme.muted
    wrapMode: Text.WrapAnywhere
  }
  FolderDialog {
    id: folderDialog
    title: "Seleccionar carpeta de fondos"
    currentFolder: Bridge.wallpaperState.browseUrl || "file:///home"
    onAccepted: root.chooseDirectory(selectedFolder)
  }
  Rule {}
  ActionButton {
    text: "Usar fondo del tema"
    selected: !Bridge.settings.wallpaper
    onClicked: root.edit("wallpaper", "")
  }
  GridView {
    id: grid
    Layout.fillWidth: true
    implicitHeight: Math.min(420, Math.ceil(count / 2) * cellHeight)
    clip: true
    model: Bridge.wallpapers
    cellWidth: width / 2
    cellHeight: 136
    cacheBuffer: 136
    boundsBehavior: Flickable.StopAtBounds
    ScrollBar.vertical: SlimScrollBar {}
    delegate: Item {
      id: option
      required property var modelData
      required property int index
      width: grid.cellWidth
      height: grid.cellHeight
      ColumnLayout {
        anchors.fill: parent
        anchors.rightMargin: option.index % 2 === 0 ? 8 : 0
        anchors.leftMargin: option.index % 2 === 1 ? 8 : 0
        anchors.bottomMargin: 12
        spacing: 6
        Rectangle {
          Layout.fillWidth: true
          Layout.preferredHeight: 100
          color: Theme.surface
          border.width: Bridge.settings.wallpaper === option.modelData.path ? 2 : 1
          border.color: Bridge.settings.wallpaper === option.modelData.path ? Theme.border : Theme.separator
          Image {
            id: thumbnail
            anchors.fill: parent
            anchors.margins: 2
            source: option.modelData.url
            sourceSize.width: 400
            fillMode: Image.PreserveAspectCrop
            asynchronous: true
          }
          Label {
            visible: thumbnail.status === Image.Error
            anchors.centerIn: parent
            text: "Imagen no disponible"
            font.pixelSize: 10
            color: Theme.muted
          }
          MouseArea {
            anchors.fill: parent
            enabled: thumbnail.status === Image.Ready
            cursorShape: Qt.PointingHandCursor
            onClicked: root.edit("wallpaper", option.modelData.path)
          }
        }
        Label {
          text: option.modelData.name
          font.pixelSize: 11
          Layout.fillWidth: true
          elide: Text.ElideRight
        }
      }
    }
  }
  EmptyState {
    visible: root.imageCount === 0
    title: "Sin imágenes"
    description: "Elige una carpeta con imágenes PNG, JPG, WEBP, SVG o BMP."
  }
  Label {
    text: root.imageCount + " imágenes" + (Bridge.wallpaperState.truncated ? " · Se muestran las primeras 200" : "")
    font.pixelSize: 10
    color: Theme.muted
  }
  Connections {
    target: Bridge
    function onActionFailed(action, reason) {
      if (action === "settings")
        root.directoryError = reason;
    }
    function onSettingsSettled() {
      root.directoryError = "";
    }
  }
  Connections {
    target: ShellState
    function onWallpaperDirectoryRequestedChanged() {
      root.openRequestedDirectory();
    }
  }
}
