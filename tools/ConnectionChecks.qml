import QtQuick
import QtQuick.Layouts
import Quickshell
import "../core"
import "../widgets"
import "../components"

Scope {
  id: root
  property int step: 0
  property real deadline: Date.now() + 9000
  property var originalSettings: ({})
  property var originalNetwork: Bridge.network
  property var prompt: null
  readonly property var network: networkLoader.item
  readonly property var selector: selectorLoader.item
  readonly property string directory: Quickshell.env("HYPRLARP_TEST_WALLPAPERS")
  readonly property string imageUrl: Quickshell.env("HYPRLARP_TEST_WALLPAPER_URL")
  readonly property string imagePath: directory + "/imagen # % ñ.svg"
  signal completed
  function verify(condition, message) {
    if (!condition)
      throw new Error("Connection regression: " + message);
  }
  FloatingWindow {
    id: window
    title: "Connections and wallpapers checks"
    implicitWidth: 1000
    implicitHeight: 800
    color: Theme.background
    RowLayout {
      anchors.fill: parent
      anchors.margins: 16
      ColumnLayout {
        Layout.fillWidth: true
        Loader {
          id: networkLoader
          source: Qt.resolvedUrl("../panels/NetworkPanel.qml")
          Layout.fillWidth: true
        }
        BluetoothPrompt {
          id: pairing
          request: root.prompt
          Layout.fillWidth: true
        }
        Wallpaper {
          id: wallpaper
          Layout.fillWidth: true
          Layout.preferredHeight: 60
        }
      }
      Loader {
        id: selectorLoader
        source: Qt.resolvedUrl("../panels/WallpapersPanel.qml")
        Layout.fillWidth: true
      }
    }
  }
  Timer {
    interval: 100
    running: true
    repeat: true
    onTriggered: {
      root.verify(Date.now() < root.deadline, "checks timed out");
      if (Bridge.saving || Bridge.hasPendingSettings)
        return;
      if (!root.network || !root.selector)
        return;
      switch (root.step) {
      case 0:
        root.originalSettings = {
          wallpaper: Bridge.settings.wallpaper,
          wallpaperDirectory: Bridge.settings.wallpaperDirectory
        };
        selector.chooseDirectory(root.imageUrl.slice(0, root.imageUrl.lastIndexOf("/")));
        break;
      case 1:
        if (!Bridge.wallpapers.some(image => image.path === root.imagePath))
          return;
        root.verify(Bridge.settings.wallpaperDirectory === root.directory, "folder dialog URL becomes a local directory");
        root.verify(Bridge.wallpaperState.directory === root.directory, "catalogue follows the selected directory");
        selector.edit("wallpaper", root.imagePath);
        Bridge.flush();
        break;
      case 2:
        if (wallpaper.children[0].status !== Image.Ready)
          return;
        root.verify(Bridge.confirmedSettings.wallpaper === root.imagePath, "chosen wallpaper persists and renders with special characters");
        Bridge.network = {
          available: true,
          enabled: true,
          networks: [
            {
              ssid: "Studio",
              interface: "wlan1",
              security: "WPA2",
              signal: 75,
              connected: false
            }
          ]
        };
        network.choose(Bridge.network.networks[0]);
        root.verify(network.selectedNetwork.interface === "wlan1", "Wi-Fi keeps the chosen interface");
        Bridge.actionFailed("wifi-connect", "Error de autenticación de prueba");
        root.verify(network.connectionError.includes("autenticación"), "Wi-Fi keeps its connection error visible");
        root.prompt = {
          token: "fixture",
          kind: "confirm",
          name: "Dispositivo de prueba",
          code: "000123"
        };
        break;
      case 3:
        root.verify(pairing.visible && !pairing.needsInput, "Bluetooth confirmation is shown");
        root.prompt = {
          token: "fixture",
          kind: "passkey",
          name: "Dispositivo de prueba",
          code: ""
        };
        break;
      case 4:
        root.verify(pairing.needsInput, "Bluetooth can request a passkey");
        root.prompt = null;
        Bridge.network = root.originalNetwork;
        Bridge.setMany(root.originalSettings);
        Bridge.flush();
        break;
      case 5:
        window.visible = false;
        stop();
        console.log("SMOKE connections COMPLETE");
        root.completed();
        break;
      }
      root.step++;
    }
  }
}
