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
  function finishStandaloneSettings() {
    if (quitAfterSaving && (!Bridge.connected || (!Bridge.saving && !Bridge.queuedSettingsOperation && !Bridge.hasPendingSettings)))
      Qt.quit();
  }
  Connections {
    target: Bridge
    function onSettingsSettled() {
      root.finishStandaloneSettings();
    }
    function onConnectedChanged() {
      root.finishStandaloneSettings();
    }
  }
  IpcHandler {
    target: "shell"
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
}
