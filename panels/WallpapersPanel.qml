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
  readonly property bool external: Bridge.externalWallpaper
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
  SettingChoice {
    title: "Gestor de fondos"
    choices: ["internal", "external"]
    labels: ["HyprLarp", "Externo · Waypaper"]
    value: Bridge.settings.wallpaperProvider || "internal"
    onEdited: value => root.edit("wallpaperProvider", value)
  }
  ColumnLayout {
    visible: root.external
    Layout.fillWidth: true
    spacing: 12
    Label {
      text: "El fondo queda libre para Waypaper u otro gestor. La barra y los paneles siguen por encima. Para vídeos, elige mpvpaper en Waypaper."
      Layout.fillWidth: true
      color: Theme.muted
      font.pixelSize: Theme.fontPx(11)
      wrapMode: Text.WordWrap
    }
    RowLayout {
      ActionButton {
        text: "Abrir Waypaper"
        enabled: !Bridge.preview && Bridge.wallpaperTools.waypaper && !Bridge.isBusy("open-tool")
        onClicked: {
          Bridge.perform("open-tool", {
            name: "waypaper"
          });
          if (!root.configurationEditor)
            ShellState.close();
        }
      }
      ActionButton {
        text: "Restaurar último fondo"
        enabled: !Bridge.preview && Bridge.wallpaperTools.waypaper && Bridge.confirmedSettings.wallpaperProvider === "external" && !Bridge.hasPendingSettings && !Bridge.saving && !Bridge.restoring && !Bridge.isBusy("waypaper-restore")
        onClicked: Bridge.perform("waypaper-restore")
      }
    }
    SettingToggle {
      title: "Restaurar Waypaper al iniciar HyprLarp"
      checked: !!Bridge.settings.waypaperRestoreOnStartup
      onEdited: checked => root.edit("waypaperRestoreOnStartup", checked)
    }
    Label {
      visible: !Bridge.wallpaperTools.waypaper || !Bridge.wallpaperTools.mpvpaper || !Bridge.wallpaperTools.socat
      text: !Bridge.wallpaperTools.waypaper ? "Instala Waypaper para abrir el selector externo." : !Bridge.wallpaperTools.mpvpaper ? "Instala mpvpaper para reproducir fondos de vídeo." : "Falta socat para cambiar, pausar o silenciar vídeos desde Waypaper."
      Layout.fillWidth: true
      color: Theme.muted
      font.pixelSize: Theme.fontPx(11)
      wrapMode: Text.WordWrap
    }
    Label {
      text: "Waypaper conserva sus ajustes y administra el reproductor. Al volver a HyprLarp se recupera tu imagen anterior; para detener un vídeo, gestiónalo desde Waypaper."
      Layout.fillWidth: true
      color: Theme.muted
      font.pixelSize: Theme.fontPx(10)
      wrapMode: Text.WordWrap
    }
  }
  ColumnLayout {
    visible: !root.external
    Layout.fillWidth: true
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
    StatusMessage {
      text: root.directoryError || Bridge.wallpaperState.error || (Bridge.wallpaperState.directory ? "Buscando en " + Bridge.wallpaperState.directory : "Elige una carpeta o escribe su ruta.")
      error: !!root.directoryError || !!Bridge.wallpaperState.error
      fontSize: 10
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
      objectName: "wallpaperGrid"
      Layout.fillWidth: true
      implicitHeight: Math.min(420, Math.ceil(count / 2) * cellHeight)
      clip: true
      model: root.external ? [] : Bridge.wallpapers
      cellWidth: width / 2
      cellHeight: 136
      cacheBuffer: 136
      boundsBehavior: Flickable.StopAtBounds
      ScrollBar.vertical: SlimScrollBar {}
      delegate: Item {
        id: option
        activeFocusOnTab: thumbnail.status === Image.Ready
        Keys.onReturnPressed: root.edit("wallpaper", option.modelData.path)
        Keys.onSpacePressed: root.edit("wallpaper", option.modelData.path)
        Accessible.role: Accessible.Button
        Accessible.name: "Usar fondo · " + modelData.name
        Accessible.selected: Bridge.settings.wallpaper === modelData.path
        Accessible.onPressAction: if (thumbnail.status === Image.Ready)
          root.edit("wallpaper", modelData.path)
        FocusRing {
          control: option
        }
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
              font.pixelSize: Theme.fontPx(10)
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
            font.pixelSize: Theme.fontPx(11)
            Layout.fillWidth: true
            elide: Text.ElideRight
          }
        }
      }
    }
    EmptyState {
      visible: root.imageCount === 0
      error: !!root.directoryError || !!Bridge.wallpaperState.error
      title: error ? "No se pudieron cargar los fondos" : "Sin imágenes"
      description: root.directoryError || Bridge.wallpaperState.error || "Elige una carpeta con imágenes PNG, JPG, WEBP, SVG o BMP."
    }
    Label {
      text: root.imageCount + " imágenes" + (Bridge.wallpaperState.truncated ? " · Se muestran las primeras 200" : "")
      font.pixelSize: Theme.fontPx(10)
      color: Theme.muted
    }
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
