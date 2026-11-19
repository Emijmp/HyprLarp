//@ pragma UseQApplication
//@ pragma Env QT_QUICK_CONTROLS_STYLE=Basic
import QtQuick
import Quickshell
import Quickshell.Io
import "core"
import "components"

ShellRoot {
  FloatingWindow {
    implicitWidth: 400
    implicitHeight: 250
    GuardedLoader {
      id: bad
      moduleId: "panel:calendar"
      active: Bridge.ready && !Resilience.blocked(moduleId)
      source: Quickshell.env("HYPRLARP_TEST_BROKEN_COMPONENT")
    }
    GuardedLoader {
      id: good
      moduleId: "panel:audio"
      sourceComponent: Component {
        Item {
          property bool usable: true
        }
      }
    }
  }
  IpcHandler {
    target: "resilienceTest"
    function status(): string {
      return JSON.stringify({
        ready: Bridge.ready,
        blocked: Resilience.blocked("panel:calendar"),
        faults: Bridge.faults,
        badStatus: bad.status,
        goodReady: good.item?.usable || false
      });
    }
    function retry(): void {
      Resilience.retry("panel:calendar");
    }
    function fix(): void {
      bad.source = Quickshell.env("HYPRLARP_TEST_GOOD_COMPONENT");
      Resilience.retry("panel:calendar");
    }
    function quit(): void {
      Qt.quit();
    }
  }
}
