import QtQuick
import QtQuick.Controls
import QtQuick.Window
import QtQuick.Layouts
import Quickshell
import "../core"
import "../components"
import "../core/focus.js" as Focus

Rectangle {
  id: root
  property string panel: ShellState.panel
  property real availableHeight: 800
  readonly property string panelStyle: Bridge.settings.panelStyle || "standard"
  readonly property var titles: ({
      control: "Centro de control",
      audio: "Audio",
      brightness: "Brillo",
      energy: "Energía",
      "night-light": "Modo nocturno",
      usb: "Dispositivos USB",
      launcher: "Aplicaciones",
      navigation: "Barra y bandeja",
      wifi: "Wi-Fi",
      bluetooth: "Bluetooth",
      notifications: "Notificaciones",
      clipboard: "Portapapeles",
      media: "Multimedia",
      calendar: "Calendario",
      session: "Sesión",
      resources: "Recursos",
      performance: "Rendimiento de HyprLarp",
      battery: "Batería",
      wallpapers: "Fondos",
      capture: "Capturas",
      displays: "Proyectar"
    })
  readonly property var sources: ({
      control: "Control",
      audio: "Audio",
      brightness: "Brightness",
      energy: "Energy",
      "night-light": "NightLight",
      usb: "Usb",
      launcher: "Launcher",
      navigation: "Navigation",
      wifi: "Network",
      bluetooth: "Bluetooth",
      notifications: "Notifications",
      clipboard: "Clipboard",
      media: "Media",
      calendar: "Calendar",
      session: "Session",
      resources: "Resources",
      performance: "Performance",
      battery: "Battery",
      wallpapers: "Wallpapers",
      capture: "Capture",
      displays: "Displays"
    })
  implicitWidth: Theme.px(panel === "performance" ? 520 : ["usb", "displays"].includes(panel) ? 420 : panel === "launcher" ? 480 : panel === "wallpapers" ? 500 : 360)
  implicitHeight: Math.min(availableHeight, scroll.contentHeight + header.implicitHeight + 53 + (message.visible ? message.implicitHeight + 12 : 0))
  radius: panelStyle === "flat" || Bridge.settings.panelLayout === "sidebar" ? 0 : Theme.radiusFor("panel")
  color: Theme.alpha(Theme.surface, panelStyle === "glass" ? Math.min(Bridge.settings.panelOpacity ?? 1, 0.86) : Bridge.settings.panelOpacity ?? 1)
  border.width: panelStyle === "flat" ? 0 : 1
  border.color: Theme.border
  clip: true
  MouseArea {
    anchors.fill: parent
    // Empty space inside a panel belongs to that panel. Controls above this
    // area still receive their clicks; only the overlay backdrop dismisses it.
    acceptedButtons: Qt.AllButtons
  }
  EdgeDetail {
    anchors.fill: parent
    inset: Math.max(4, Theme.radiusFor("panel") + 2)
    z: 2
  }
  focus: true
  Accessible.role: Accessible.Pane
  Accessible.name: titles[panel] || "Panel"
  Connections {
    target: root.Window.window
    function onActiveFocusItemChanged() {
      const item = root.Window.window.activeFocusItem;
      if (Focus.contains(panelLoader.item, item))
        Qt.callLater(() => root.reveal(item));
    }
  }
  Keys.forwardTo: root.panel === "session" && panelLoader.item ? [panelLoader.item] : []
  function reveal(item) {
    const flickable = scroll.contentItem;
    if (!item || !flickable || flickable.contentY === undefined)
      return;
    const point = item.mapToItem(panelLoader, 0, 0);
    if (point.y >= flickable.contentY && point.y + item.height <= flickable.contentY + flickable.height)
      return;
    flickable.contentY = Math.max(0, Math.min(point.y - 8, scroll.contentHeight - flickable.height));
  }
  Keys.onEscapePressed: ShellState.close()
  ColumnLayout {
    anchors.fill: parent
    anchors.margins: 14
    spacing: 12
    RowLayout {
      id: header
      Layout.fillWidth: true
      Icon {
        visible: root.panel === "launcher" || Theme.detail("headerIcons")
        name: ModuleCatalog.byId[root.panel] ? ModuleCatalog.byId[root.panel].icon : "grid"
        color: Theme.text
        Layout.preferredWidth: root.panel === "launcher" ? 26 : 16
        Layout.preferredHeight: root.panel === "launcher" ? 26 : 16
      }
      Label {
        text: root.panel === "launcher" ? "HyprLarp / Buscar" : root.titles[root.panel] || "Panel"
        font.pixelSize: Theme.fontPx(13)
        font.weight: Font.Medium
        Layout.fillWidth: true
      }
      ActionButton {
        objectName: "panel-close"
        icon: "close"
        hint: "Cerrar"
        implicitWidth: 24
        implicitHeight: Theme.controlHeight(24)
        onClicked: ShellState.close()
      }
    }
    Rule {}
    ScrollView {
      id: scroll
      Layout.fillWidth: true
      Layout.fillHeight: true
      clip: true
      contentWidth: availableWidth
      contentHeight: failure.visible ? failure.implicitHeight : panelLoader.item ? panelLoader.item.implicitHeight : 0
      ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
      ScrollBar.vertical: SlimScrollBar {}
      GuardedLoader {
        id: panelLoader
        moduleId: "panel:" + root.panel
        asynchronous: true
        property double loadStarted: 0
        onSourceChanged: loadStarted = Date.now()
        width: scroll.availableWidth
        source: root.panel && root.sources[root.panel] ? Qt.resolvedUrl("../panels/" + root.sources[root.panel] + "Panel.qml") : ""
        onLoaded: {
          const elapsed = Date.now() - ShellState.panelRequestedAt;
          if (Bridge.ready && root.panel && ShellState.panelRequestedAt && elapsed >= 0 && elapsed <= 60000)
            Bridge.send("performance-panel-loaded", {
              name: root.panel,
              milliseconds: elapsed
            });
          if (Quickshell.env("HYPRLARP_BENCHMARK") === "1")
            console.log("BENCHMARK_PANEL " + root.panel + " " + (ShellState.panelRequestedAt || loadStarted) + " " + Date.now());
          if (root.panel === "launcher" || root.panel === "clipboard")
            item.focusSearch();
          else {
            const first = Focus.first(item);
            if (first)
              first.forceActiveFocus();
            else
              root.forceActiveFocus();
          }
        }
      }
      ModuleFailure {
        id: failure
        width: scroll.availableWidth
        visible: panelLoader.status === Loader.Error || Resilience.blocked(moduleId)
        moduleId: "panel:" + root.panel
      }
      Connections {
        target: panelLoader.item
        ignoreUnknownSignals: true
        function onRevealRequested(item) {
          Qt.callLater(() => root.reveal(item));
        }
      }
    }
    StatusMessage {
      id: message
      visible: Bridge.message !== ""
      text: (Bridge.messageIsError ? "Error: " : "") + Bridge.message
      error: Bridge.messageIsError
    }
  }
}
