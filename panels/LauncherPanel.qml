import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
import Quickshell.Wayland
import "../core"
import "../components"
import "../core/launcher.js" as Launcher

ColumnLayout {
  id: root
  spacing: 12
  property string filter: "all"
  property string query: ""
  property int queryNumber: 0
  readonly property string tokenPrefix: Date.now() + "-" + Math.random() + "-"
  property string queryToken: ""
  readonly property var applications: ["all", "favorites", "recent"].includes(filter) && !["=", "?", "/", ">", "~"].some(prefix => query.startsWith(prefix)) ? Applications.search(query, filter) : []
  readonly property var windows: !Bridge.preview && ["all", "windows"].includes(filter) && (query || filter === "windows") ? ToplevelManager.toplevels.values.filter(window => Launcher.matches(query, window.title + " " + window.appId)).map(window => ({
        kind: "window",
        id: window.appId + window.title,
        name: window.title || window.appId,
        genericName: "Ventana abierta · " + window.appId,
        icon: window.appId,
        window: window
      })) : []
  readonly property var actions: ["all", "actions"].includes(filter) && (query || filter === "actions") ? Launcher.actions(ModuleCatalog.definitions, query) : []
  readonly property var remote: Bridge.launcherResults.token === queryToken ? Bridge.launcherResults.results : []
  readonly property var results: {
    if (["=", "?", "/", "~"].some(prefix => query.startsWith(prefix)) || filter === "files")
      return remote;
    if (query.startsWith(">") || filter === "actions")
      return actions;
    return applications.map(app => ({
          kind: "app",
          id: app.id,
          name: app.name,
          genericName: app.genericName || "Aplicación",
          icon: app.icon || "",
          app: app
        })).concat(windows, actions.slice(0, 8), remote);
  }
  function updateQuery() {
    if (!search)
      return;
    query = search.text.trim();
    apps.currentIndex = 0;
    const shouldSearch = filter === "files" || (filter === "all" && !query.startsWith(">") && (query.length >= 2 || query.startsWith("=")));
    queryToken = shouldSearch ? tokenPrefix + (++queryNumber) : "";
    Bridge.send("launcher-query", {
      query: filter === "files" && !query.startsWith("/") && !query.startsWith("~/") ? "? " + query : query,
      token: queryToken
    });
  }
  onFilterChanged: updateQuery()
  function focusSearch() {
    search.forceActiveFocus();
  }
  function launch(entry) {
    if (!entry)
      return;
    if (entry.kind === "app") {
      Applications.launched(entry.app);
      entry.app.execute();
    } else if (entry.kind === "window") {
      if (ToplevelManager.toplevels.values.includes(entry.window))
        entry.window.activate();
    } else if (entry.kind === "action") {
      ModuleCatalog.activate(entry.id, ShellState.activeScreen);
      return;
    } else if (entry.kind === "file") {
      Bridge.perform("launcher-open", {
        path: entry.path
      });
    } else if (entry.kind === "calculation") {
      if (!Bridge.preview)
        Quickshell.clipboardText = entry.value;
      Bridge.toast(Bridge.preview ? entry.value : "Resultado copiado: " + entry.value, false);
    }
    if (entry.kind !== "calculation" || !Bridge.preview)
      ShellState.close();
  }
  Component.onCompleted: search.forceActiveFocus()
  Component.onDestruction: {
    apps.model = null;
    Applications.releaseSearch();
    Bridge.send("launcher-query", {
      token: ""
    });
  }
  Timer {
    id: searchDelay
    interval: 130
    onTriggered: root.updateQuery()
  }
  Field {
    id: search
    objectName: "launcherSearch"
    Layout.fillWidth: true
    placeholderText: "Aplicaciones, ventanas, archivos…  = calcular  > acciones"
    onTextChanged: searchDelay.restart()
    Keys.onDownPressed: apps.currentIndex = Math.min(apps.count - 1, apps.currentIndex + 1)
    Keys.onUpPressed: apps.currentIndex = Math.max(0, apps.currentIndex - 1)
    onAccepted: {
      if (searchDelay.running) {
        searchDelay.stop();
        root.updateQuery();
      }
      root.launch(root.results[apps.currentIndex]);
    }
  }
  Flow {
    Layout.fillWidth: true
    spacing: 6
    Repeater {
      model: ["all", "favorites", "recent", "windows", "files", "actions"]
      ActionButton {
        required property string modelData
        text: ({
            all: "Todo",
            favorites: "Favoritas",
            recent: "Recientes",
            windows: "Ventanas",
            files: "Archivos",
            actions: "Acciones"
          })[modelData]
        selected: root.filter === modelData
        onClicked: {
          root.filter = modelData;
          apps.currentIndex = 0;
        }
      }
    }
  }
  ListView {
    id: apps
    Layout.fillWidth: true
    Layout.preferredHeight: 350
    clip: true
    model: root.results
    currentIndex: 0
    highlightMoveDuration: 0
    boundsBehavior: Flickable.StopAtBounds
    cacheBuffer: 0
    reuseItems: true
    ScrollBar.vertical: SlimScrollBar {}
    delegate: Rectangle {
      id: entry
      required property var modelData
      required property int index
      width: apps.width - 8
      height: Theme.controlHeight(42)
      activeFocusOnTab: true
      Keys.onReturnPressed: root.launch(modelData)
      Keys.onSpacePressed: root.launch(modelData)
      color: apps.currentIndex === index || hover.containsMouse ? Theme.raised : "transparent"
      Accessible.role: Accessible.ListItem
      Accessible.name: modelData.name + " · " + modelData.genericName
      Accessible.selected: apps.currentIndex === index
      Accessible.onPressAction: root.launch(modelData)
      FocusRing {
        control: entry
      }
      Rectangle {
        visible: apps.currentIndex === entry.index
        width: 1
        height: parent.height
        color: Theme.border
      }
      RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 10
        anchors.rightMargin: 42
        spacing: 10
        Image {
          visible: !!Bridge.settings.showAppIcons
          readonly property string appIcon: entry.modelData.icon || ""
          property bool failed: false
          onAppIconChanged: failed = false
          onStatusChanged: if (status === Image.Error)
            failed = true
          source: !visible ? "" : failed ? Applications.fallbackIcon : Applications.icon(appIcon)
          asynchronous: true
          Layout.preferredWidth: 24
          Layout.preferredHeight: 24
          sourceSize.width: 24
          sourceSize.height: 24
        }
        ColumnLayout {
          Layout.fillWidth: true
          spacing: 2
          Label {
            text: entry.modelData.name
            Layout.fillWidth: true
            font.pixelSize: Theme.fontPx(12)
          }
          Label {
            text: entry.modelData.genericName || ""
            visible: text !== ""
            color: Theme.muted
            font.pixelSize: Theme.fontPx(10)
            Layout.fillWidth: true
          }
        }
      }
      MouseArea {
        id: hover
        anchors.fill: parent
        anchors.rightMargin: 38
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: root.launch(entry.modelData)
      }
      ActionButton {
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        visible: entry.modelData.kind === "app" && entry.y + entry.height / 2 >= apps.contentY + 7 && entry.y + entry.height / 2 <= apps.contentY + apps.height - 7
        icon: "star"
        selected: entry.modelData.kind === "app" && Applications.favorite(entry.modelData.app)
        hint: "Alternar favorita"
        onClicked: Applications.toggleFavorite(entry.modelData.app)
      }
    }
  }
  EmptyState {
    visible: root.results.length === 0
    title: "Sin resultados"
  }
  Label {
    text: Bridge.launcherResults.token === root.queryToken && Bridge.launcherResults.error ? Bridge.launcherResults.error : Bridge.launcherResults.token === root.queryToken && Bridge.launcherResults.truncated ? "Resultados limitados · escribe una ruta para buscar en otra carpeta" : "↑ ↓ seleccionar · Enter abrir/copiar · = 2*(3+4) · > acciones · ? archivos"
    font.pixelSize: Theme.fontPx(10)
    color: Theme.muted
    Layout.fillWidth: true
    wrapMode: Text.WordWrap
  }
}
