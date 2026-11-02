import QtQuick
import QtQuick.Controls
import QtQuick.Window
import QtQuick.Layouts
import "../core"
import "../components"
import "../core/configuration.js" as ConfigIndex

Rectangle {
  id: root
  color: Theme.surface
  radius: Theme.radiusFor("panel")
  border.width: 1
  border.color: Theme.border
  EdgeDetail {
    anchors.fill: parent
    inset: 7
    length: 8
  }
  property int tab: Math.max(0, pages.indexOf(ShellState.settingsPage))
  onTabChanged: if (pages && pages[tab])
    ShellState.settingsPage = pages[tab]
  readonly property var currentPage: pageLoader.item
  property bool confirmReset: false
  property bool resetSection: false
  readonly property string contextId: "config-" + Date.now() + "-" + Math.random()
  readonly property bool configurationFocused: visible && Window.active
  onConfigurationFocusedChanged: Bridge.configurationWindow(contextId, configurationFocused)
  Component.onCompleted: Bridge.configurationWindow(contextId, configurationFocused)
  Component.onDestruction: Bridge.configurationWindow(contextId, null)
  readonly property var sections: ["Apariencia", "Barra", "Módulos", "Fondos", "Atajos", "General", "Perfiles"]
  readonly property var pages: ["Appearance", "Bar", "Modules", "Wallpapers", "Shortcuts", "General", "Profiles"]
  Connections {
    target: ShellState
    function onSettingsRequested(page) {
      const index = root.pages.indexOf(page);
      if (index < 0)
        return;
      root.tab = index;
      root.confirmReset = false;
      settingsSearch.text = "";
      if (scroll.contentItem)
        scroll.contentItem.contentY = 0;
      if (root.Window.window)
        root.Window.window.requestActivate();
    }
  }
  Shortcut {
    sequence: "Ctrl+Z"
    context: Qt.WindowShortcut
    enabled: root.configurationFocused && Bridge.canUndo && !root.confirmReset
    onActivated: Bridge.undo()
  }
  Shortcut {
    sequences: ["Ctrl+Shift+Z", "Ctrl+Y"]
    context: Qt.WindowShortcut
    enabled: root.configurationFocused && Bridge.canRedo && !root.confirmReset
    onActivated: Bridge.redo()
  }
  Keys.onEscapePressed: event => {
    if (root.confirmReset)
      root.confirmReset = false;
    else
      event.accepted = false;
  }
  ColumnLayout {
    anchors.fill: parent
    anchors.margins: 22
    spacing: 16
    RowLayout {
      Layout.fillWidth: true
      Icon {
        visible: Theme.decorated
        name: "sliders"
        Layout.preferredWidth: 18
        Layout.preferredHeight: 18
      }
      Label {
        text: "HyprLarp / Configuración"
        font.pixelSize: 15
        Layout.fillWidth: true
      }
      Label {
        text: !Bridge.connected ? "Sin conexión" : Bridge.restoring ? "Aplicando…" : Bridge.hasPendingSettings || Bridge.saving ? "Guardando…" : "Guardado"
        font.pixelSize: 11
        color: Theme.muted
      }
      ActionButton {
        text: "Deshacer"
        hint: "Deshacer último cambio · Ctrl+Z"
        enabled: root.configurationFocused && Bridge.canUndo
        onClicked: {
          root.confirmReset = false;
          Bridge.undo();
        }
      }
      ActionButton {
        text: "Rehacer"
        hint: "Rehacer · Ctrl+Shift+Z / Ctrl+Y"
        enabled: root.configurationFocused && Bridge.canRedo
        onClicked: {
          root.confirmReset = false;
          Bridge.redo();
        }
      }
      ActionButton {
        text: "Restablecer…"
        hint: "Volver a los valores iniciales"
        enabled: root.configurationFocused && Bridge.canReset
        onClicked: {
          root.resetSection = false;
          root.confirmReset = !root.confirmReset;
        }
      }
    }
    Rectangle {
      visible: root.confirmReset
      Layout.fillWidth: true
      implicitHeight: resetContent.implicitHeight + 24
      color: Theme.surface
      border.width: 1
      border.color: Theme.border
      ColumnLayout {
        id: resetContent
        anchors.fill: parent
        anchors.margins: 12
        spacing: 8
        Label {
          text: root.resetSection ? "Restablecer sección: " + root.sections[root.tab] : "Restablecer toda la configuración"
          font.pixelSize: 13
          Layout.fillWidth: true
        }
        Label {
          text: root.resetSection ? "Esta sección volverá a sus valores iniciales. En Barra y Módulos se respeta el monitor seleccionado. Podrás deshacerlo." : "Volverás a AMOLED Black y a los ajustes iniciales de barra, módulos, colores y atajos. Podrás deshacerlo. Los historiales de notificaciones y portapapeles se conservan."
          color: Theme.muted
          font.pixelSize: 11
          wrapMode: Text.WordWrap
          Layout.fillWidth: true
        }
        RowLayout {
          ActionButton {
            text: "Cancelar"
            onClicked: root.confirmReset = false
          }
          ActionButton {
            text: root.resetSection ? "Restablecer sección" : "Restablecer todo"
            enabled: root.configurationFocused && Bridge.canReset
            accent: true
            onClicked: {
              root.confirmReset = false;
              if (root.resetSection)
                Bridge.restoreSettings("settings-reset-section", {
                  section: root.pages[root.tab],
                  monitor: ["Bar", "Modules"].includes(root.pages[root.tab]) ? BarEditor.target : ""
                });
              else
                Bridge.resetSettings();
            }
          }
          Item {
            Layout.fillWidth: true
          }
        }
      }
    }
    RowLayout {
      Layout.fillWidth: true
      Field {
        id: settingsSearch
        Layout.fillWidth: true
        placeholderText: "Buscar ajustes…"
      }
      ActionButton {
        text: "Restablecer sección…"
        visible: root.pages[root.tab] !== "Profiles"
        enabled: root.configurationFocused && Bridge.canReset
        onClicked: {
          root.resetSection = true;
          root.confirmReset = true;
        }
      }
    }
    Flow {
      Layout.fillWidth: true
      enabled: !Bridge.restoring
      spacing: 10
      Repeater {
        model: root.sections
        ActionButton {
          required property string modelData
          required property int index
          text: modelData
          selected: root.tab === index
          onClicked: root.tab = index
        }
      }
    }
    ColumnLayout {
      visible: settingsSearch.text.trim().length > 0
      Layout.fillWidth: true
      Repeater {
        model: settingsSearch.text.trim() ? ConfigIndex.search(settingsSearch.text) : []
        ActionButton {
          required property var modelData
          text: root.sections[root.pages.indexOf(modelData[0])] + " / " + modelData[1]
          onClicked: {
            root.tab = root.pages.indexOf(modelData[0]);
            settingsSearch.text = "";
          }
        }
      }
      Label {
        visible: ConfigIndex.search(settingsSearch.text).length === 0
        text: "Sin ajustes coincidentes"
        color: Theme.muted
      }
    }
    Rule {}
    ScrollView {
      id: scroll
      visible: settingsSearch.text.trim().length === 0
      Layout.fillWidth: true
      Layout.fillHeight: true
      enabled: !Bridge.restoring
      clip: true
      contentWidth: availableWidth
      ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
      ScrollBar.vertical: SlimScrollBar {}
      Loader {
        id: pageLoader
        width: scroll.availableWidth
        source: Qt.resolvedUrl("settings/" + root.pages[root.tab] + "Settings.qml")
      }
    }
    Label {
      visible: Bridge.message !== ""
      text: (Bridge.messageIsError ? "Error: " : "") + Bridge.message
      wrapMode: Text.WordWrap
      Layout.fillWidth: true
      font.pixelSize: 11
    }
    Label {
      visible: Bridge.preview
      text: "Vista previa · Ajustes aislados"
      color: Theme.muted
      font.pixelSize: 10
    }
  }
}
