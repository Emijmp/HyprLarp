//@ pragma UseQApplication
//@ pragma Env QT_QUICK_CONTROLS_STYLE=Basic
import QtQuick
import Quickshell
import Quickshell.Io
import "core"
import "widgets"

ShellRoot {
  id: root
  property bool notificationsReady: Notices.unread >= 0
  property bool nativeConnectionsReady: Connectivity.active
  property bool systemEffectsReady: Osd.visible || NightLight.desired
  property bool quitAfterSaving: false
  property string syncedContextTheme: ""
  function syncContextTheme() {
    if (!Bridge.ready || !Bridge.connected || Bridge.preview || Bridge.settingsOnly || Bridge.saving || Bridge.hasPendingSettings || Bridge.awaitingInitial)
      return;
    if (!Bridge.settings.themeScheduleEnabled) {
      syncedContextTheme = "";
      return;
    }
    if (syncedContextTheme === Theme.scheduledTheme)
      return;
    syncedContextTheme = Theme.scheduledTheme;
    Bridge.send("theme-context-changed");
  }
  Connections {
    target: Theme
    function onScheduledThemeChanged() {
      Qt.callLater(root.syncContextTheme);
    }
  }
  function finishStandaloneSettings() {
    if (quitAfterSaving && (!Bridge.connected || (!Bridge.saving && !Bridge.queuedSettingsOperation && !Bridge.hasPendingSettings)))
      Qt.quit();
  }
  Connections {
    target: Bridge
    function onSettingsSettled() {
      root.finishStandaloneSettings();
      root.syncContextTheme();
    }
    function onConnectedChanged() {
      root.finishStandaloneSettings();
      if (!Bridge.connected)
        root.syncedContextTheme = "";
      Qt.callLater(root.syncContextTheme);
    }
    function onReadyChanged() {
      Qt.callLater(root.syncContextTheme);
    }
  }
  IpcHandler {
    target: "shell"
    function health(): string {
      return JSON.stringify({
        ready: Bridge.ready,
        connected: Bridge.connected,
        backendPid: Bridge.backendPid,
        panel: ShellState.panel,
        blockedModules: Bridge.faults.filter(item => item.blocked).map(item => item.id),
        appearance: {
          theme: Theme.scheduledTheme,
          accent: String(Theme.accent),
          panelLayout: Bridge.settings.panelLayout || "floating",
          panelStyle: Bridge.settings.panelStyle || "standard",
          blurEnabled: Theme.blurEnabled,
          performanceMode: Bridge.settings.performanceMode || "balanced"
        }
      });
    }
    function toggle(name: string): void {
      ShellState.toggle(name);
    }
    function settings(): void {
      ShellState.open("settings");
    }
    function close(): void {
      ShellState.close();
    }
    function capture(mode: string): void {
      ShellState.capture(mode);
    }
    function captureFrozen(mode: string): void {
      ShellState.capture(mode, 0, false, true);
    }
    function lock(): void {
      Bridge.perform("session", {
        command: "lock"
      });
    }
  }
  LazyLoader {
    active: Bridge.ready && Bridge.preview
    component: FloatingWindow {
      title: "HyprLarp · Vista previa"
      implicitWidth: 1440
      implicitHeight: 900
      minimumSize: Qt.size(900, 650)
      color: Theme.background
      Preview {
        anchors.fill: parent
      }
    }
  }
  LazyLoader {
    active: Bridge.ready && !Bridge.preview && !Bridge.settingsOnly
    source: !Bridge.preview && !Bridge.settingsOnly ? Qt.resolvedUrl("widgets/Desktop.qml") : ""
  }

  LazyLoader {
    active: Bridge.ready && !Bridge.preview && Osd.visible && Quickshell.screens.length > 0
    source: !Bridge.preview ? Qt.resolvedUrl("widgets/OsdWindow.qml") : ""
  }
  LazyLoader {
    active: Bridge.preview && Quickshell.env("HYPRLARP_SMOKE_TEST") === "1" && Bridge.ready
    source: Bridge.preview && Quickshell.env("HYPRLARP_SMOKE_TEST") === "1" ? Qt.resolvedUrl("tools/Smoke.qml") : ""
  }
  LazyLoader {
    active: Bridge.ready && ShellState.settingsOpen
    component: FloatingWindow {
      id: settingsWindow
      title: "HyprLarp · Configuración"
      implicitWidth: 900
      implicitHeight: 720
      minimumSize: Qt.size(760, 600)
      color: "transparent"
      onVisibleChanged: if (!visible) {
        Bridge.flush(true);
        ShellState.settingsOpen = false;
        if (Bridge.settingsOnly) {
          root.quitAfterSaving = true;
          root.finishStandaloneSettings();
        }
      }
      SettingsContent {
        anchors.fill: parent
      }
    }
  }
  LazyLoader {
    active: Bridge.captureDraft !== null
    component: FloatingWindow {
      title: "HyprLarp · Editar captura"
      implicitWidth: 1100
      implicitHeight: 760
      minimumSize: Qt.size(800, 580)
      color: Theme.surface
      onVisibleChanged: if (!visible && Bridge.captureDraft) {
        if (!Bridge.preview)
          Bridge.perform("capture-discard", {
            token: Bridge.captureDraft.token
          });
        Bridge.captureDraft = null;
      }
      CaptureEditor {
        anchors.fill: parent
        draft: Bridge.captureDraft || {
          token: "",
          url: "",
          width: 1,
          height: 1
        }
      }
    }
  }
  LazyLoader {
    active: Bridge.ready && Bridge.settingsOnly && ShellState.panel === "performance"
    component: FloatingWindow {
      title: "HyprLarp · Rendimiento"
      implicitWidth: 560
      implicitHeight: 760
      minimumSize: Qt.size(420, 420)
      color: Theme.surface
      onVisibleChanged: if (!visible)
        ShellState.close()
      PanelSurface {
        anchors.fill: parent
        panel: "performance"
        availableHeight: parent.height
      }
    }
  }
}
