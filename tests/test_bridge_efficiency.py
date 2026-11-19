"""An optimistic save needs one UI update while backend corrections still apply."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which("quickshell"), "Quickshell unavailable")
class BridgeEfficiencyTests(unittest.TestCase):
  def test_save_acknowledgments_and_untracked_idle_do_not_invalidate_bindings(self):
    with tempfile.TemporaryDirectory(prefix="hyprlarp-bridge-efficiency-") as folder:
      app = Path(folder)
      (app / "backend").symlink_to(ROOT / "backend", target_is_directory=True)
      contents = '''//@ pragma UseQApplication
import QtQuick
import Quickshell
import "CORE" as Core
ShellRoot {
  id: root
  property int step: 0
  property int updates: 0
  property int busyUpdates: 0
  property double deadline: Date.now() + 5000
  function verify(ok, message) {
    if (!ok) { console.error(message); Qt.quit(); throw new Error(message); }
  }
  Connections {
    target: Core.Bridge
    function onSettingsChanged() { root.updates++; }
    function onBusyActionsChanged() { root.busyUpdates++; }
  }
  Timer {
    interval: 50; repeat: true; running: true
    onTriggered: {
      root.verify(Date.now() < root.deadline, "bridge efficiency timeout");
      if (!Core.Bridge.ready || !Core.Bridge.connected || Core.Bridge.awaitingInitial) return;
      if (root.step === 0) {
        root.updates = 0; root.busyUpdates = 0;
        Core.Bridge.consume(JSON.stringify({type: "settings", data: Core.Bridge.settings}));
        root.verify(root.updates === 0, "identical snapshots invalidate settings");
        Core.Bridge.consume(JSON.stringify({type: "idle", data: {action: "refresh"}}));
        root.verify(root.busyUpdates === 0, "untracked idle invalidates busy state");
        Core.Bridge.configure("barSpacing", Core.Bridge.settings.barSpacing + 1);
        Core.Bridge.flush(true);
        root.verify(root.updates === 1, "optimistic settings must appear immediately");
        root.step = 1; return;
      }
      if (Core.Bridge.saving || Core.Bridge.hasPendingSettings) return;
      root.verify(root.updates === 1, "save acknowledgment duplicates the optimistic UI update");
      const corrected = Object.assign({}, Core.Bridge.settings, {barSpacing: Core.Bridge.settings.barSpacing + 1});
      Core.Bridge.consume(JSON.stringify({type: "settings", data: corrected}));
      root.verify(root.updates === 2 && Core.Bridge.settings.barSpacing === corrected.barSpacing, "backend corrections must still update the interface");
      Core.Bridge.busyActions = {refresh: 2}; root.busyUpdates = 0;
      const idle = JSON.stringify({type: "idle", data: {action: "refresh"}});
      Core.Bridge.consume(idle); Core.Bridge.consume(idle); Core.Bridge.consume(idle);
      root.verify(root.busyUpdates === 2 && !Core.Bridge.isBusy("refresh"), "tracked actions must settle exactly once each");
      console.log("BRIDGE EFFICIENCY COMPLETE"); stop(); Qt.quit();
    }
  }
}'''.replace("CORE", (ROOT / "core").as_uri())
      (app / "shell.qml").write_text(contents)
      environment = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "QT_QUICK_BACKEND": "software",
        "HYPRLARP_PREVIEW": "1", "HYPRLARP_STATE_DIR": str(app / "settings"), "XDG_RUNTIME_DIR": folder}
      environment.pop("WAYLAND_DISPLAY", None)
      result = subprocess.run(["quickshell", "--path", str(app / "shell.qml"), "--no-color"],
        env=environment, text=True, capture_output=True, timeout=8)
      output = result.stdout + result.stderr
      self.assertEqual(result.returncode, 0, output)
      self.assertIn("BRIDGE EFFICIENCY COMPLETE", output)
      for error in ("TypeError:", "ReferenceError:", "Failed to load", "Binding loop"):
        self.assertNotIn(error, output)
