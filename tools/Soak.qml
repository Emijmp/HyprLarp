import QtQuick
import Quickshell
import Quickshell.Io
import "../core"
import "../widgets"

Scope {
  id: root
  property int step: 0
  property int rounds: 0
  property string page: ""
  readonly property var scenes: ["", "control", "launcher", "calendar", "notifications", "clipboard", "media", "audio", "brightness", "resources", "performance", "battery", "wifi", "bluetooth", "energy", "night-light", "usb", "wallpapers", "capture", "displays", "session", "navigation", "settings:Appearance", "settings:Bar", "settings:Modules", "settings:Wallpapers", "settings:Shortcuts", "settings:General", "settings:Profiles", "settings:Displays", "welcome"]
  readonly property var themes: Object.keys(Theme.palettes).filter(name => name !== "custom")
  IpcHandler {
    target: "soak"
    function health(): string {
      return JSON.stringify({
        ready: Bridge.ready && !Bridge.awaitingInitial,
        connected: Bridge.connected,
        backendPid: Bridge.backendPid,
        step: root.step,
        rounds: root.rounds,
        scene: root.page,
        theme: Theme.scheduledTheme,
        blocked: Bridge.faults.filter(item => item.blocked).map(item => item.id)
      });
    }
    function quit(): void {
      Qt.quit();
    }
  }
  FloatingWindow {
    implicitWidth: 1100
    implicitHeight: 850
    color: Theme.surface
    Loader {
      anchors.fill: parent
      sourceComponent: root.page === "welcome" ? welcome : root.page.startsWith("settings:") ? settings : desktop
    }
    Component {
      id: desktop
      Preview {}
    }
    Component {
      id: settings
      SettingsContent {}
    }
    Component {
      id: welcome
      WelcomeContent {}
    }
  }
  Timer {
    interval: Math.max(100, Number(Quickshell.env("HYPRLARP_SOAK_CYCLE_MS") || "2000"))
    repeat: true
    running: true
    onTriggered: {
      if (!Bridge.ready || !Bridge.connected || Bridge.awaitingInitial || Bridge.saving || Bridge.hasPendingSettings)
        return;
      root.page = root.scenes[root.step % root.scenes.length];
      if (root.page.startsWith("settings:")) {
        ShellState.close();
        ShellState.settingsPage = root.page.slice(9);
      } else if (root.page !== "welcome")
        ShellState.open(root.page);
      root.step++;
      if (root.step % root.scenes.length === 0) {
        root.rounds++;
        Bridge.setMany({
          theme: root.themes[root.rounds % root.themes.length],
          themeScheduleEnabled: false,
          panelLayout: ["floating", "centered", "sidebar"][root.rounds % 3],
          panelStyle: ["standard", "glass", "flat"][root.rounds % 3],
          accessibilityTextScale: root.rounds % 2 ? 1 : 1.5
        });
        Bridge.flush(true);
      }
    }
  }
}
