pragma Singleton
import QtQuick
import Quickshell

Singleton {
  id: root
  property string panel: Bridge.preview ? (Quickshell.env("HYPRLARP_START_PANEL") ?? "control") : ""
  property double panelRequestedAt: 0
  property bool settingsOpen: Bridge.settingsOnly && Quickshell.env("HYPRLARP_WELCOME_ONLY") !== "1"
  property bool welcomeOpen: Quickshell.env("HYPRLARP_WELCOME_ONLY") === "1"
  property bool welcomeOffered: false
  property var activeScreen: null
  readonly property bool vertical: ["left", "right"].indexOf(Bridge.settings.barPosition) !== -1
  property string settingsPage: "Appearance"
  property bool wallpaperDirectoryRequested: false
  property string sessionRequest: ""
  signal settingsRequested(string page)
  signal sessionRequested(string command)
  function openWelcome() {
    Bridge.flush(true);
    welcomeOffered = true;
    panel = "";
    welcomeOpen = true;
  }
  function offerWelcome() {
    if (Bridge.ready && Bridge.connected && !Bridge.preview && !Bridge.settingsOnly && Bridge.onboarding.needed && !welcomeOffered)
      openWelcome();
  }
  function browseWallpaperDirectory() {
    wallpaperDirectoryRequested = true;
    openSettings("Wallpapers");
  }
  function openSettings(page) {
    settingsPage = page || "Appearance";
    settingsOpen = true;
    panel = "";
    settingsRequested(settingsPage);
  }
  function openSession(command, screen) {
    sessionRequest = command;
    open("session", screen);
    sessionRequested(command);
  }
  function open(name, screen) {
    if (name === "settings") {
      openSettings(settingsPage);
      return;
    }
    if (screen)
      activeScreen = screen;
    else
      activeScreen = Quickshell.screens.find(s => s.name === Compositor.focusedScreenName) || activeScreen || Quickshell.screens[0];
    panel = name;
  }
  function toggle(name, screen) {
    if (name === "osd") {
      openSettings("General");
      return;
    }
    if (name === "presentation") {
      Presentation.toggle();
      return;
    }
    if (panel === name)
      close();
    else
      open(name, screen);
  }
  function close() {
    panel = "";
  }
  function syncPanel() {
    Bridge.send("panel", {
      name: Resilience.blocked("panel:" + panel) ? "" : panel
    });
  }
  onPanelChanged: {
    panelRequestedAt = Date.now();
    if (panel !== "session")
      sessionRequest = "";
    if (panel !== "clipboard")
      Bridge.clipboardThumbnails = {};
    if (Bridge.ready)
      syncPanel();
  }
  Connections {
    target: Bridge
    function onReadyChanged() {
      if (Bridge.ready) {
        root.syncPanel();
        Qt.callLater(root.offerWelcome);
      }
    }
    function onOnboardingChanged() {
      Qt.callLater(root.offerWelcome);
    }
    function onConnectedChanged() {
      Qt.callLater(root.offerWelcome);
    }
  }
  property int captureRemaining: 0
  property var captureOptions: ({
      mode: "region",
      annotate: false,
      freeze: false
    })
  function cancelCapture() {
    countdown.stop();
    captureTimer.stop();
    captureRemaining = 0;
  }
  function capture(mode, delay, annotate, frozen) {
    cancelCapture();
    close();
    captureOptions = {
      mode: mode,
      annotate: annotate === true,
      freeze: frozen === true
    };
    captureRemaining = Math.max(0, Math.min(10, Number(delay) || 0));
    if (captureRemaining)
      countdown.start();
    else
      captureTimer.restart();
  }
  Timer {
    id: countdown
    interval: 1000
    repeat: true
    onTriggered: {
      root.captureRemaining--;
      if (root.captureRemaining <= 0) {
        stop();
        captureTimer.restart();
      }
    }
  }
  Timer {
    id: captureTimer
    interval: 250
    onTriggered: Bridge.perform("screenshot", root.captureOptions)
  }
}
