import QtQuick
import Quickshell
import Quickshell.Io
import "../core"
import "../widgets"

Scope {
  id: root
  property int step: 0
  property int pausedCount: 0
  property double pausedAt: 0
  property bool recordingSeen: false
  property bool finished: false
  function verify(condition, message) {
    if (!condition)
      throw new Error("Performance regression: " + message);
  }
  function find(item, name) {
    if (!item)
      return null;
    if (item.objectName === name)
      return item;
    for (const child of item.children || []) {
      const found = find(child, name);
      if (found)
        return found;
    }
    return item.item ? find(item.item, name) : null;
  }
  IpcHandler {
    target: "performanceTest"
    function status(): string {
      return JSON.stringify({
        finished: root.finished,
        step: root.step,
        state: Bridge.performance
      });
    }
    function quit(): void {
      Qt.quit();
    }
  }
  FloatingWindow {
    implicitWidth: 860
    implicitHeight: 820
    color: Theme.surface
    PanelSurface {
      id: surface
      anchors.fill: parent
      availableHeight: parent.height
      panel: "performance"
    }
  }
  Component.onCompleted: ShellState.open("performance")
  Timer {
    interval: 100
    repeat: true
    running: true
    onTriggered: {
      if (!Bridge.ready || !Bridge.connected)
        return;
      const state = Bridge.performance;
      switch (root.step) {
      case 0:
        if (!state.current?.processes)
          return;
        root.verify(state.current.rssMiB > 0, "real memory reading");
        root.verify(state.revision?.length === 12, "package revision");
        Bridge.perform("performance-pause", {
          paused: true
        });
        root.step++;
        break;
      case 1:
        if (!state.paused)
          return;
        root.verify(root.find(surface, "performance-pause").text === "Reanudar", "pause label follows the backend");
        root.verify(root.find(surface, "performance-note").text.includes(state.cpuTickMs.toFixed(0) + " ms"), "CPU counter resolution is visible");
        root.pausedCount = state.samples.length;
        root.pausedAt = Date.now();
        root.step++;
        break;
      case 2:
        if (Date.now() - root.pausedAt < 2400)
          return;
        root.verify(state.samples.length === root.pausedCount, "paused collector stopped");
        Bridge.perform("performance-refresh");
        root.step++;
        break;
      case 3:
        if (state.samples.length <= root.pausedCount)
          return;
        root.verify(state.paused, "manual sample does not resume polling");
        Bridge.perform("performance-pause", {
          paused: false
        });
        root.step++;
        break;
      case 4:
        if (state.paused)
          return;
        Bridge.perform("performance-record", {
          label: "Primera medición",
          seconds: 5
        });
        root.recordingSeen = false;
        root.step++;
        break;
      case 5:
        if (state.recording) {
          root.recordingSeen = true;
          return;
        }
        if (!root.recordingSeen || state.history.length !== 1)
          return;
        root.verify(state.history[0].summary.samples >= 2 && state.history[0].summary.seconds >= 5, "completed measured window");
        Bridge.perform("performance-record", {
          label: "Segunda medición",
          seconds: 5
        });
        root.recordingSeen = false;
        root.step++;
        break;
      case 6:
        if (state.recording) {
          root.recordingSeen = true;
          return;
        }
        if (!root.recordingSeen || state.history.length !== 2)
          return;
        const view = root.find(surface, "performance-panel");
        root.verify(view && view.first && view.second && view.comparison.compatible, "comparison selectors and context");
        root.verify(view.first.id !== view.second.id, "two different measurements selected");
        root.verify(!state.error, state.error || "no collector error");
        root.step++;
        const prefix = Quickshell.env("HYPRLARP_PERFORMANCE_CAPTURE");
        if (prefix) {
          surface.grabToImage(result => {
            root.verify(result.saveToFile(prefix + "-live.png"), "live screenshot");
            surface.reveal(root.find(surface, "performance-history"));
            capture.restart();
          });
        } else
          root.finish();
        stop();
        break;
      }
    }
  }
  function finish() {
    finished = true;
    console.log("PERFORMANCE COMPLETE");
    if (Quickshell.env("HYPRLARP_PERFORMANCE_HOLD") !== "1")
      Qt.quit();
  }
  Timer {
    id: capture
    interval: 200
    onTriggered: surface.grabToImage(result => {
      root.verify(result.saveToFile(Quickshell.env("HYPRLARP_PERFORMANCE_CAPTURE") + "-history.png"), "history screenshot");
      root.finish();
    })
  }
}
