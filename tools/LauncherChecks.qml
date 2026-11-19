import QtQuick
import Quickshell
import "../core"
import "../panels" as Panels

Scope {
  id: root
  property int step: 0
  property double deadline: Date.now() + 12000
  signal completed
  function verify(condition, message) {
    if (!condition) {
      Qt.exit(1);
      throw new Error("Launcher regression: " + message);
    }
  }
  FloatingWindow {
    id: window
    implicitWidth: 720
    implicitHeight: 620
    Panels.LauncherPanel {
      id: launcher
      anchors.fill: parent
      anchors.margins: 16
    }
  }
  Timer {
    interval: 150
    running: true
    repeat: true
    onTriggered: {
      root.verify(Date.now() < root.deadline, "results must arrive within the timeout");
      const field = launcher.children.find(child => child.objectName === "launcherSearch");
      root.verify(!!field, "search field exists");
      if (root.step === 0) {
        field.text = "= sqrt(81)+2";
        root.step++;
      } else if (root.step === 1 && launcher.query === "= sqrt(81)+2" && Bridge.launcherResults.token === launcher.queryToken && launcher.results.length) {
        root.verify(launcher.results[0].kind === "calculation" && launcher.results[0].value === "11", "calculator result crosses the backend bridge");
        launcher.filter = "actions";
        field.text = "> configuración";
        root.step++;
      } else if (root.step === 2 && launcher.query === "> configuración" && launcher.results.length) {
        root.verify(launcher.results.every(entry => entry.kind === "action"), "actions are separated from executable application entries");
        launcher.filter = "files";
        field.text = Quickshell.env("HYPRLARP_TEST_FILE_QUERY");
        root.step++;
      } else if (root.step === 3 && launcher.results.some(entry => entry.kind === "file")) {
        root.verify(launcher.results.some(entry => entry.path === Quickshell.env("HYPRLARP_TEST_FILE_PATH")), "paths with spaces, percent and Unicode stay intact");
        launcher.filter = "favorites";
        field.text = "";
        root.step++;
      } else if (root.step === 4 && launcher.query === "") {
        root.verify(launcher.results.every(entry => entry.kind === "app"), "favorites contain only applications");
        stop();
        window.visible = false;
        console.log("SMOKE unified launcher COMPLETE");
        root.completed();
      }
    }
  }
}
