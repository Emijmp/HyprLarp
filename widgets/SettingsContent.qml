import QtQuick
import QtQuick.Controls
import QtQuick.Window
import QtQuick.Layouts
import "../core"
import "../components"
import "../core/configuration.js" as ConfigIndex
import "../core/focus.js" as Focus

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
  Accessible.role: Accessible.Pane
  Accessible.name: "Configuración de HyprLarp"
  Connections {
    target: root.Window.window
    function onActiveFocusItemChanged() {
      const item = root.Window.window.activeFocusItem;
      if (!item || !Focus.contains(root.currentPage, item))
        return;
      Qt.callLater(() => {
        const y = item.mapToItem(root.currentPage, 0, 0).y;
        const top = scroll.contentItem.contentY;
        if (y < top || y + item.height > top + scroll.availableHeight)
          scroll.contentItem.contentY = Math.max(0, Math.min(y - 12, scroll.contentItem.contentHeight - scroll.availableHeight));
      });
    }
  }
  property var requestedSetting: null
  property string revealedSetting: ""
  readonly property var searchResults: ConfigIndex.search(settingsSearch.text)
  function findSetting(item, name) {
    if (!item || item.visible === false)
      return null;
    const wanted = ConfigIndex.normalize(name);
    if (item.objectName === name || ConfigIndex.normalize(item.title || item.text || "") === wanted)
      return item;
    for (const child of item.children || []) {
      const found = findSetting(child, name);
      if (found)
        return found;
    }
    if (item.item)
      return findSetting(item.item, name);
    return null;
  }
  function activateSearchResult(entry) {
    if (!entry)
      return;
    requestedSetting = entry;
    tab = pages.indexOf(entry[0]);
    settingsSearch.text = "";
    revealTimer.restart();
  }
  function revealRequested() {
    if (!requestedSetting || !currentPage)
      return;
    if (requestedSetting[4] && currentPage.mode !== undefined)
      currentPage.mode = requestedSetting[4];
    Qt.callLater(() => {
      const target = root.findSetting(root.currentPage, root.requestedSetting?.[3] || root.requestedSetting?.[1] || "");
      const offset = target ? target.mapToItem(root.currentPage, 0, 0).y : 0;
      scroll.contentItem.contentY = Math.max(0, Math.min(offset - 12, scroll.contentItem.contentHeight - scroll.availableHeight));
      if (target)
        target.forceActiveFocus();
      root.revealedSetting = root.requestedSetting?.[1] || "";
      root.requestedSetting = null;
      revealNotice.restart();
    });
  }
  property bool confirmReset: false
  property bool resetSection: false
  readonly property string contextId: "config-" + Date.now() + "-" + Math.random()
  readonly property bool configurationFocused: visible && Window.active
  onConfigurationFocusedChanged: Bridge.configurationWindow(contextId, configurationFocused)
  Component.onCompleted: Bridge.configurationWindow(contextId, configurationFocused)
  Component.onDestruction: Bridge.configurationWindow(contextId, null)
  readonly property var sections: ["Apariencia", "Barra", "Módulos", "Fondos", "Atajos", "General", "Perfiles", "Pantallas"]
  readonly property var pages: ["Appearance", "Bar", "Modules", "Wallpapers", "Shortcuts", "General", "Profiles", "Displays"]
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
    sequence: "Ctrl+F"
    context: Qt.WindowShortcut
    enabled: root.configurationFocused
    onActivated: {
      settingsSearch.forceActiveFocus();
      settingsSearch.selectAll();
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
    if (settingsSearch.text)
      settingsSearch.text = "";
    else if (root.confirmReset)
      root.confirmReset = false;
    else
      event.accepted = false;
  }
  ColumnLayout {
    anchors.fill: parent
    anchors.margins: 22
    spacing: 16
    GridLayout {
      Layout.fillWidth: true
      columns: root.width < Theme.px(720) ? 1 : 2
      RowLayout {
        Layout.fillWidth: true
        Icon {
          name: "hyprlarp"
          Layout.preferredWidth: 28
          Layout.preferredHeight: 28
        }
        Label {
          text: "HyprLarp / Configuración"
          font.pixelSize: Theme.fontPx(15)
          Layout.fillWidth: true
          wrapMode: Text.WordWrap
        }
        Label {
          text: !Bridge.connected ? "Sin conexión" : Bridge.restoring ? "Aplicando…" : Bridge.hasPendingSettings || Bridge.saving ? "Guardando…" : "Guardado"
          font.pixelSize: Theme.fontPx(11)
          color: Theme.muted
        }
      }
      Flow {
        Layout.fillWidth: true
        spacing: 6
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
          font.pixelSize: Theme.fontPx(13)
          Layout.fillWidth: true
        }
        Label {
          text: root.resetSection ? "Esta sección volverá a sus valores iniciales. En Barra y Módulos se respeta el monitor seleccionado. Podrás deshacerlo." : "Volverás a AMOLED Black y a los ajustes iniciales de barra, módulos, colores y atajos. Podrás deshacerlo. Los historiales de notificaciones y portapapeles se conservan."
          color: Theme.muted
          font.pixelSize: Theme.fontPx(11)
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
    GridLayout {
      Layout.fillWidth: true
      columns: root.width < Theme.px(620) ? 1 : 2
      Field {
        id: settingsSearch
        objectName: "settings-search"
        Layout.fillWidth: true
        placeholderText: "Buscar ajustes…"
        Accessible.name: "Buscar ajustes"
        Accessible.searchEdit: true
        onTextChanged: searchList.currentIndex = 0
        onAccepted: root.activateSearchResult(root.searchResults[searchList.currentIndex])
        Keys.onDownPressed: searchList.currentIndex = Math.min(root.searchResults.length - 1, searchList.currentIndex + 1)
        Keys.onUpPressed: searchList.currentIndex = Math.max(0, searchList.currentIndex - 1)
      }
      ActionButton {
        text: "Restablecer sección…"
        visible: !["Profiles", "Displays"].includes(root.pages[root.tab])
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
    ListView {
      id: searchList
      visible: settingsSearch.text.trim().length > 0
      Layout.fillWidth: true
      Layout.fillHeight: true
      clip: true
      spacing: 4
      model: root.searchResults
      ScrollBar.vertical: SlimScrollBar {}
      delegate: ActionButton {
        required property var modelData
        required property int index
        width: searchList.width
        selected: searchList.currentIndex === index
        text: root.sections[root.pages.indexOf(modelData[0])] + " / " + modelData[1]
        onClicked: root.activateSearchResult(modelData)
      }
    }
    Label {
      visible: settingsSearch.text.trim().length > 0 && root.searchResults.length === 0
      text: "Sin ajustes coincidentes"
      color: Theme.muted
    }
    Label {
      visible: root.revealedSetting !== "" && settingsSearch.text.trim().length === 0
      text: root.revealedSetting
      color: Theme.accent
      font.pixelSize: Theme.fontPx(11)
    }
    DisplayConfirmation {}
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
      Column {
        width: scroll.availableWidth
        GuardedLoader {
          id: pageLoader
          moduleId: "page:" + root.pages[root.tab]
          width: parent.width
          source: Qt.resolvedUrl("settings/" + root.pages[root.tab] + "Settings.qml")
          onLoaded: if (root.requestedSetting)
            revealTimer.restart()
        }
        ModuleFailure {
          width: parent.width
          visible: pageLoader.status === Loader.Error || Resilience.blocked(moduleId)
          moduleId: "page:" + root.pages[root.tab]
        }
      }
    }
    StatusMessage {
      visible: Bridge.message !== ""
      text: (Bridge.messageIsError ? "Error: " : "") + Bridge.message
      error: Bridge.messageIsError
    }
    Label {
      visible: Bridge.preview
      text: "Vista previa · Ajustes aislados"
      color: Theme.muted
      font.pixelSize: Theme.fontPx(10)
    }
  }
  Timer {
    id: revealTimer
    interval: 60
    onTriggered: root.revealRequested()
  }
  Timer {
    id: revealNotice
    interval: 4000
    onTriggered: root.revealedSetting = ""
  }
}
