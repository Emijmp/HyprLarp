import QtQuick
import QtQuick.Layouts
import "../core"
import "../components"

Item {
  id: root
  required property string moduleName
  property bool vertical: false
  property var screen: null
  property var configuration: Bridge.settings
  property var guide: BarLayout
  readonly property var definition: ModuleCatalog.byId[moduleName] || {}
  readonly property bool active: ModuleCatalog.active(moduleName)
  readonly property bool available: ModuleCatalog.commandAvailable(moduleName)
  objectName: "bar-module-" + moduleName
  activeFocusOnTab: moduleName !== "workspaces"
  Keys.onReturnPressed: ModuleCatalog.activate(moduleName, screen)
  Keys.onSpacePressed: ModuleCatalog.activate(moduleName, screen)
  Accessible.name: (moduleName === "launcher" ? "HyprLarp · " : "") + (ModuleCatalog.labels[moduleName] || moduleName) + (caption && moduleName !== "launcher" ? " · " + caption : "")
  Accessible.description: definition.description || ""
  Accessible.role: Accessible.Button
  Accessible.onPressAction: ModuleCatalog.activate(moduleName, screen)
  readonly property int borderSize: configuration.moduleBorderWidth ?? 1
  readonly property int paddingX: (configuration.modulePaddingX ?? 6) + borderSize
  readonly property int paddingY: (configuration.modulePaddingY ?? 2) + borderSize
  readonly property string caption: {
    if (moduleName === "clock")
      return Clock.timeText;
    if (configuration.barShowLabels === false)
      return "";
    switch (moduleName) {
    case "launcher":
      return "HyprLarp";
    case "calendar":
      return Clock.dateText;
    case "brightness":
      return Bridge.system.brightnessAvailable ? Math.round(Bridge.system.brightness) + "%" : "—";
    case "energy":
      return Bridge.power.available ? ({
          "power-saver": "Ahorro",
          balanced: "Equilibrado",
          performance: "Rendimiento"
        })[Bridge.power.profile] || "—" : "—";
    case "night-light":
      return Bridge.nightLight.active ? String(Bridge.nightLight.temperature) + " K" : "";
    case "usb":
      return String((Bridge.usb.devices || []).length);
    case "settings":
      return "Ajustes";
    case "themes":
      return Theme.palette.name;
    case "media":
      return Media.player ? Media.title : "";
    case "resources":
      return Bridge.system.cpu == null ? "—" : Math.round(Bridge.system.cpu) + "%";
    case "battery":
      return Bridge.system.battery && Bridge.system.battery.available && Bridge.system.battery.percent !== null ? Bridge.system.battery.percent + "%" : "—";
    default:
      return "";
    }
  }
  readonly property var workspaceEntries: moduleName === "workspaces" ? Compositor.entriesFor(screen, configuration.barWorkspaceCount ?? 5, configuration.barWorkspaceDisplay || "current") : []
  readonly property int workspaceCell: Math.max(Theme.largeTargets ? 44 : 20, guide.fontSize + 4)
  readonly property real workspaceWidth: workspaceEntries.reduce((total, workspace) => total + cellWidth(workspace), 0) + Math.max(0, workspaceEntries.length - 1) * 4
  readonly property real naturalWidth: (moduleName === "clock" ? 0 : guide.iconSize) + (caption !== "" ? Math.ceil(captionMetrics.advanceWidth) + 2 + (moduleName === "clock" ? 0 : 6) : 0) + (moduleName === "notifications" && Notices.unread > 0 ? Math.ceil(badgeMetrics.advanceWidth) + 8 : 0)
  opacity: Theme.opacityFor(moduleName, configuration)
  implicitWidth: Math.max(Theme.largeTargets ? 44 : 0, 2 * paddingX + (vertical ? Math.max(guide.iconSize, workspaceCell) : moduleName === "workspaces" ? workspaceWidth : Math.min(moduleName === "media" ? 200 : 400, naturalWidth)))
  readonly property string verticalClock: moduleName === "clock" && vertical ? Clock.timeText.replace(/[: ]/g, "\n") : ""
  implicitHeight: 2 * paddingY + (vertical && moduleName === "workspaces" ? workspaceEntries.length * workspaceCell + Math.max(0, workspaceEntries.length - 1) * 5 : vertical && moduleName === "clock" ? verticalClock.split("\n").length * (guide.fontSize + 4) : Math.max(guide.iconSize, guide.fontSize + 4))
  function cellWidth(workspace) {
    return Math.max(workspaceCell, Math.ceil(Math.min(workspace.label.length, 12) * guide.fontSize * 0.65) + 8);
  }
  TextMetrics {
    id: captionMetrics
    text: root.caption
    font.family: root.moduleName === "clock" ? Theme.mono : Theme.font
    font.pixelSize: guide.fontSize
  }
  TextMetrics {
    id: badgeMetrics
    text: root.moduleName === "notifications" ? String(Notices.unread) : ""
    font.family: Theme.mono
    font.pixelSize: guide.fontSize
  }
  ModuleFrame {
    id: body
    width: root.vertical ? root.width : Math.min(root.width, root.implicitWidth)
    height: root.vertical ? Math.min(root.height, root.implicitHeight) : root.height
    configuration: root.configuration
    active: root.active || root.activeFocus
    hovered: hover.containsMouse
  }
  Row {
    id: contents
    anchors.centerIn: body
    width: root.vertical ? guide.iconSize : Math.min(root.naturalWidth, body.width - 2 * root.paddingX)
    height: Math.max(guide.iconSize, guide.fontSize + 4)
    spacing: 6
    visible: root.moduleName !== "workspaces" && !(root.vertical && root.moduleName === "clock")
    Icon {
      name: ModuleCatalog.iconFor(root.moduleName)
      color: Theme.text
      width: guide.iconSize
      height: guide.iconSize
      y: (parent.height - height) / 2
      visible: root.moduleName !== "clock" || root.vertical
    }
    Label {
      visible: !root.vertical && root.caption !== ""
      text: root.caption
      elide: root.moduleName === "media" ? Text.ElideRight : Text.ElideNone
      width: Math.max(0, Math.min(Math.ceil(captionMetrics.advanceWidth) + 2, contents.width - (root.moduleName === "clock" ? 0 : guide.iconSize + 6)))
      height: parent.height
      font.pixelSize: guide.fontSize
      font.family: root.moduleName === "clock" ? Theme.mono : Theme.font
    }
    Label {
      visible: !root.vertical && root.moduleName === "notifications" && Notices.unread > 0
      text: Notices.unread
      width: Math.ceil(badgeMetrics.advanceWidth) + 2
      height: parent.height
      font.pixelSize: guide.fontSize
      font.family: Theme.mono
    }
  }
  Label {
    visible: root.vertical && root.moduleName === "clock"
    anchors.centerIn: body
    text: root.verticalClock
    font.family: Theme.mono
    font.pixelSize: guide.fontSize
    horizontalAlignment: Text.AlignHCenter
  }
  MouseArea {
    id: hover
    anchors.fill: body
    enabled: root.moduleName !== "workspaces"
    hoverEnabled: true
    cursorShape: Qt.PointingHandCursor
    acceptedButtons: Qt.LeftButton | Qt.MiddleButton | Qt.RightButton
    onClicked: mouse => {
      if (mouse.button === Qt.RightButton) {
        BarEditor.target = root.screen ? root.screen.name : "";
        ShellState.openSettings("Modules");
      } else if (mouse.button === Qt.MiddleButton && root.moduleName === "media") {
        Media.playPause();
      } else if (mouse.button === Qt.MiddleButton && root.moduleName === "volume") {
        Audio.setMuted(!Audio.muted);
      } else if (mouse.button === Qt.MiddleButton && root.moduleName === "microphone") {
        Audio.setNodeMuted(Audio.source, !Audio.microphoneMuted);
      } else {
        ModuleCatalog.activate(root.moduleName, root.screen);
      }
    }
    onWheel: wheel => {
      if (root.moduleName === "volume" && Audio.available)
        Audio.setVolume(Audio.volume + (wheel.angleDelta.y > 0 ? 0.05 : -0.05));
      else if (root.moduleName === "microphone" && Audio.microphoneAvailable)
        Audio.setNodeVolume(Audio.source, Audio.source.audio.volume + (wheel.angleDelta.y > 0 ? 0.05 : -0.05));
      else if (root.moduleName === "brightness" && Bridge.system.brightnessAvailable) {
        brightnessWheel.value = Math.max(1, Math.min(100, (brightnessWheel.running ? brightnessWheel.value : Bridge.system.brightness) + (wheel.angleDelta.y > 0 ? 5 : -5)));
        brightnessWheel.restart();
      } else
        wheel.accepted = false;
    }
  }
  Hint {
    visible: hover.containsMouse
    text: (root.moduleName === "launcher" ? "HyprLarp · " : "") + (ModuleCatalog.labels[root.moduleName] || root.moduleName) + " · " + (root.definition.description || "") + (!root.available ? " · No disponible" : "")
  }
  Timer {
    id: brightnessWheel
    property real value: 0
    interval: 100
    onTriggered: Bridge.perform("brightness", {
      value: value
    })
  }
  Component {
    id: workspaceItem
    WorkspaceCell {
      required property var modelData
      entry: modelData
      screen: root.screen
      fontSize: root.guide.fontSize
      workspaceCount: root.configuration.barWorkspaceCount ?? 5
      width: root.vertical ? Math.max(0, body.width - 2 * root.paddingX) : root.cellWidth(modelData)
      height: root.workspaceCell
    }
  }
  FocusRing {
    control: root
  }

  Row {
    anchors.left: body.left
    anchors.leftMargin: root.paddingX
    anchors.verticalCenter: body.verticalCenter
    spacing: 4
    visible: root.moduleName === "workspaces" && !root.vertical
    Repeater {
      model: root.moduleName === "workspaces" && !root.vertical ? root.workspaceEntries : []
      delegate: workspaceItem
    }
  }
  Column {
    anchors.top: body.top
    anchors.topMargin: root.paddingY
    anchors.horizontalCenter: body.horizontalCenter
    spacing: 5
    visible: root.moduleName === "workspaces" && root.vertical
    Repeater {
      model: root.moduleName === "workspaces" && root.vertical ? root.workspaceEntries : []
      delegate: workspaceItem
    }
  }
}
