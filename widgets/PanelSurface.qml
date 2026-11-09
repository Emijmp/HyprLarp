import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../core"
import "../components"

Rectangle {
  id: root
  property string panel: ShellState.panel
  property real availableHeight: 800
  readonly property var titles: ({
      control: "Centro de control",
      audio: "Audio",
      brightness: "Brillo",
      energy: "Energía",
      "night-light": "Modo nocturno",
      usb: "Dispositivos USB",
      launcher: "Aplicaciones",
      wifi: "Wi-Fi",
      bluetooth: "Bluetooth",
      notifications: "Notificaciones",
      clipboard: "Portapapeles",
      media: "Multimedia",
      calendar: "Calendario",
      session: "Sesión",
      resources: "Recursos",
      battery: "Batería",
      wallpapers: "Fondos",
      capture: "Capturas"
    })
  readonly property var sources: ({
      control: "Control",
      audio: "Audio",
      brightness: "Brightness",
      energy: "Energy",
      "night-light": "NightLight",
      usb: "Usb",
      launcher: "Launcher",
      wifi: "Network",
      bluetooth: "Bluetooth",
      notifications: "Notifications",
      clipboard: "Clipboard",
      media: "Media",
      calendar: "Calendar",
      session: "Session",
      resources: "Resources",
      battery: "Battery",
      wallpapers: "Wallpapers",
      capture: "Capture"
    })
  implicitWidth: panel === "usb" ? 420 : panel === "launcher" ? 480 : panel === "wallpapers" ? 500 : 360
  implicitHeight: Math.min(availableHeight, scroll.contentHeight + 74 + (message.visible ? message.implicitHeight + 12 : 0))
  radius: Theme.radiusFor("panel")
  color: Theme.alpha(Theme.surface, Bridge.settings.panelOpacity ?? 1)
  border.width: 1
  border.color: Theme.border
  clip: true
  EdgeDetail {
    anchors.fill: parent
    inset: Math.max(4, Theme.radiusFor("panel") + 2)
    z: 2
  }
  focus: true
  Keys.forwardTo: root.panel === "session" && panelLoader.item ? [panelLoader.item] : []
  function reveal(item) {
    const flickable = scroll.contentItem;
    if (!item || !flickable || flickable.contentY === undefined)
      return;
    const point = item.mapToItem(panelLoader, 0, 0);
    flickable.contentY = Math.max(0, Math.min(point.y - 8, scroll.contentHeight - flickable.height));
  }
  Keys.onEscapePressed: ShellState.close()
  ColumnLayout {
    anchors.fill: parent
    anchors.margins: 14
    spacing: 12
    RowLayout {
      Layout.fillWidth: true
      Icon {
        visible: Theme.detail("headerIcons")
        name: ModuleCatalog.byId[root.panel] ? ModuleCatalog.byId[root.panel].icon : "grid"
        color: Theme.text
        Layout.preferredWidth: 16
        Layout.preferredHeight: 16
      }
      Label {
        text: root.titles[root.panel] || "Panel"
        font.pixelSize: 13
        font.weight: Font.Medium
        Layout.fillWidth: true
      }
      ActionButton {
        icon: "close"
        hint: "Cerrar"
        implicitWidth: 24
        implicitHeight: 24
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
      contentHeight: panelLoader.item ? panelLoader.item.implicitHeight : 0
      ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
      ScrollBar.vertical: SlimScrollBar {}
      Loader {
        id: panelLoader
        width: scroll.availableWidth
        source: root.panel && root.sources[root.panel] ? Qt.resolvedUrl("../panels/" + root.sources[root.panel] + "Panel.qml") : ""
        onLoaded: {
          if (root.panel === "launcher" || root.panel === "clipboard")
            item.focusSearch();
          else
            root.forceActiveFocus();
        }
      }
      Connections {
        target: panelLoader.item
        ignoreUnknownSignals: true
        function onRevealRequested(item) {
          Qt.callLater(() => root.reveal(item));
        }
      }
    }
    Label {
      id: message
      visible: Bridge.message !== ""
      text: (Bridge.messageIsError ? "Error: " : "") + Bridge.message
      color: Theme.text
      wrapMode: Text.WordWrap
      Layout.fillWidth: true
      font.pixelSize: 11
    }
  }
}
