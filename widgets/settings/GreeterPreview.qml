import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import "../../core"
import "../../core/paths.js" as Paths
import "../../greeter" as Login

Rectangle {
  id: root
  objectName: "greeterPreview"
  Layout.fillWidth: true
  Layout.maximumWidth: Math.min(720, 360 * sceneWidth / sceneHeight)
  implicitHeight: Math.round(width * sceneHeight / sceneWidth)
  color: Theme.background
  clip: true

  readonly property var previewScreen: Quickshell.screens.find(screen => screen.name === Compositor.focusedScreenName) || Quickshell.screens[0]
  readonly property int sceneWidth: previewScreen?.width || 1280
  readonly property int sceneHeight: previewScreen?.height || 720
  readonly property string layout: Bridge.settings.greeterLayout || "sidebar"
  readonly property string stateHome: Quickshell.env("XDG_STATE_HOME") || Quickshell.env("HOME") + "/.local/state"
  property var synced: ({})
  readonly property string wallpaper: {
    if (!Bridge.externalWallpaper)
      return Paths.fileUrl(Bridge.settings.wallpaper);
    const path = synced.wallpaper || "";
    if (!path)
      return "";
    const image = /\.(png|jpe?g|webp|bmp|jxl)$/i.test(path) ? path : (Quickshell.env("XDG_RUNTIME_DIR") + "/noctalia-greeter-sync/wallpaper.png");
    return Paths.fileUrl(image) + "?revision=" + encodeURIComponent(synced.updated || "");
  }
  readonly property var appearance: ({
      background: String(Theme.background),
      surface: String(Theme.surface),
      raised: String(Theme.raised),
      border: String(Theme.border),
      text: String(Theme.text),
      muted: String(Theme.muted),
      accent: String(Theme.accent),
      onAccent: root.contrastText(Theme.accent),
      danger: String(Theme.danger),
      font: Theme.font,
      radius: Theme.radiusFor("panel"),
      layout: root.layout,
      wallpaper: root.wallpaper,
      fill: "crop",
      textScale: Bridge.settings.accessibilityTextScale || 1,
      largeTargets: !!Bridge.settings.accessibilityLargeTargets,
      reducedMotion: !!Bridge.settings.accessibilityReducedMotion
    })

  function contrastText(color) {
    const channels = [color.r, color.g, color.b].map(value => value <= 0.04045 ? value / 12.92 : Math.pow((value + 0.055) / 1.055, 2.4));
    return channels[0] * 0.2126 + channels[1] * 0.7152 + channels[2] * 0.0722 > 0.179 ? "#000000" : "#ffffff";
  }

  Accessible.role: Accessible.Graphic
  Accessible.name: "Vista previa del inicio de sesión: " + (root.layout === "centered" ? "Centrado" : "Barra lateral")

  FileView {
    path: Bridge.externalWallpaper ? root.stateHome + "/hyprlarp-greeter/last-sync.json" : ""
    preload: Bridge.externalWallpaper
    watchChanges: Bridge.externalWallpaper
    printErrors: false
    onFileChanged: reload()
    onLoadFailed: root.synced = ({})
    onLoaded: {
      try {
        const data = JSON.parse(text());
        root.synced = data && typeof data.wallpaper === "string" ? data : ({});
      } catch (error) {
        root.synced = ({});
      }
    }
  }

  // This model has no authentication or power service behind it.
  QtObject {
    id: illustrationController
    readonly property var model: ({
        appearance: root.appearance,
        hostname: Bridge.system.hostname || "HyprLarp",
        sessions: [
          {
            name: "Hyprland"
          }
        ]
      })
    readonly property bool preview: true
    readonly property bool ready: true
    readonly property bool busy: false
    readonly property bool authenticating: false
    readonly property bool awaitingResponse: false
    readonly property bool echoResponse: false
    readonly property string prompt: "Contraseña"
    readonly property string message: ""
    readonly property bool messageIsError: false
    property string userName: Bridge.system.user || Quickshell.env("USER") || "usuario"
    property int sessionIndex: 0
    property string powerConfirmation: ""
    signal clearInput
    signal modelUpdated
    function submit(response) {
    }
    function cancel() {
    }
    function power(action) {
    }
  }

  Login.GreeterView {
    width: root.sceneWidth
    height: root.sceneHeight
    scale: root.width / width
    transformOrigin: Item.TopLeft
    controller: illustrationController
    interactive: false
    layer.enabled: true
    layer.smooth: true
    layer.textureSize: Qt.size(Math.ceil(root.width * 2), Math.ceil(root.height * 2))
  }

  MouseArea {
    anchors.fill: parent
    acceptedButtons: Qt.AllButtons
    onWheel: event => event.accepted = false
  }

  Rectangle {
    anchors.fill: parent
    color: "transparent"
    border.width: 1
    border.color: Theme.border
  }
}
