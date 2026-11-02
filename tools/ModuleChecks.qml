import QtQuick
import Quickshell
import "../core"

Scope {
  id: root
  required property var view
  readonly property var settingsEntries: ModuleCatalog.definitions.filter(entry => entry.kind === "settings")
  readonly property var sessionEntries: ModuleCatalog.definitions.filter(entry => entry.kind === "session")
  property int step: 0
  property string expectedPage: ""
  property string expectedSession: ""
  property real deadline: Date.now() + 8000
  signal completed
  function verify(condition, message) {
    if (!condition)
      throw new Error("Module regression: " + message);
  }
  Timer {
    interval: 120
    repeat: true
    running: true
    onTriggered: {
      root.verify(Date.now() < root.deadline, "module navigation timed out");
      if (root.expectedPage) {
        root.verify(ShellState.settingsOpen && ShellState.settingsPage === root.expectedPage, "configuration route opens requested page");
        root.verify(root.view.pages[root.view.tab] === root.expectedPage, "already open settings follow module navigation");
      }
      if (root.expectedSession) {
        root.verify(ShellState.panel === "session" && ShellState.sessionRequest === root.expectedSession, "session route opens confirmation");
        root.verify(!Bridge.isBusy("session"), "session module does not execute without confirmation");
      }
      if (root.step < root.settingsEntries.length) {
        const entry = root.settingsEntries[root.step];
        root.expectedPage = entry.target;
        ModuleCatalog.activate(entry.id);
        if (entry.target === "Modules" && root.view.currentPage)
          root.view.currentPage.mode = "add";
      } else if (root.step < root.settingsEntries.length + root.sessionEntries.length) {
        root.expectedPage = "";
        ShellState.settingsOpen = false;
        const entry = root.sessionEntries[root.step - root.settingsEntries.length];
        root.expectedSession = entry.target;
        ModuleCatalog.activate(entry.id);
      } else {
        root.expectedSession = "";
        ShellState.close();
        const dnd = Bridge.settings.doNotDisturb, paused = Bridge.settings.clipboardPaused, presenting = Presentation.active;
        ModuleCatalog.activate("do-not-disturb");
        root.verify(Bridge.settings.doNotDisturb !== dnd && ModuleCatalog.active("do-not-disturb") === !dnd, "DND toggle updates state");
        ModuleCatalog.activate("do-not-disturb");
        ModuleCatalog.activate("clipboard-pause");
        root.verify(Bridge.settings.clipboardPaused !== paused, "clipboard capture toggle updates state");
        ModuleCatalog.activate("clipboard-pause");
        ModuleCatalog.activate("presentation");
        root.verify(Presentation.active !== presenting, "presentation starts from its inactive module");
        ModuleCatalog.activate("presentation");
        root.verify(Bridge.settings.doNotDisturb === dnd && Bridge.settings.clipboardPaused === paused && Presentation.active === presenting, "toggles restore original state");
        for (const name of ["presentation", "media", "battery"]) {
          const configuration = Object.assign({}, Bridge.settings, {
            barZones: {
              start: [name],
              center: [],
              end: []
            },
            disabledModules: []
          });
          root.verify(BarLayout.modules(configuration, "start").includes(name), "selected module remains reachable: " + name);
        }
        const decoration = Bridge.settings.decoration;
        Bridge.set("decoration", "minimal");
        root.verify(!Theme.decorated, "minimal appearance disables decorative marks");
        Bridge.set("decoration", "subtle");
        root.verify(Theme.decorated, "subtle appearance enables decorative marks");
        Bridge.set("decoration", decoration);
        stop();
        console.log("SMOKE module navigation COMPLETE");
        root.completed();
      }
      root.step++;
    }
  }
}
