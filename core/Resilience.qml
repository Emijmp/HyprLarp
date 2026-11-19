pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io

Singleton {
  signal retryRequested(string moduleId)
  function blocked(id) {
    return Bridge.faults.some(item => item.id === id && item.blocked);
  }
  function report(id, message) {
    Bridge.send("fault-report", {
      id: id,
      message: message
    });
  }
  function retry(id) {
    if (blocked(id) || id.startsWith("backend:"))
      Bridge.send("fault-reset", {
        id: id
      });
    retryRequested(id);
  }
  function recover() {
    if (Bridge.preview) {
      Bridge.toast("La vista previa no cambia el modo de la sesión", false);
      return;
    }
    recoveryProcess.running = true;
  }
  Process {
    id: recoveryProcess
    command: [Quickshell.env("HYPRLARP_EXECUTABLE") || Quickshell.shellPath("bin/hyprlarp"), "recover"]
  }
}
