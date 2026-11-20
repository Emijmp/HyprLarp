import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SAVED = {"id": 1, "token": "stored", "app": "Stored app", "appId": "stored-app",
  "summary": "Saved notification", "body": "Saved body", "icon": "", "time": 1000,
  "urgency": 1, "read": False, "timeout": 0}


@unittest.skipUnless(shutil.which("quickshell"), "Quickshell is unavailable")
class NotificationHistoryTests(unittest.TestCase):
  def run_history(self, checks, *, before_load="", after_load="", delay=.4, wait_for_write=True):
    with tempfile.TemporaryDirectory(prefix="hyprlarp-notification-history-") as folder:
      app = Path(folder)
      (app / "backend").mkdir()
      (app / "backend/service.py").write_text(
        "import sys, time\n"
        + "sys.path.insert(0, " + repr(str(ROOT)) + ")\n"
        + "from backend import service\n"
        + "original = service.Service.load_history\n"
        + "def delayed(self):\n"
        + "  time.sleep(" + repr(delay) + ")\n"
        + "  return original(self)\n"
        + "service.Service.load_history = delayed\n"
        # Observe completed writes in the fixture instead of assuming a disk
        # write has finished after a fixed delay. The production protocol does
        # not acknowledge its fire-and-forget history persistence action.
        + "action = service.Service.action\n"
        + "def acknowledge(self, request):\n"
        + "  result = action(self, request)\n"
        + "  if request.get('action') == 'history':\n"
        + "    self.emit('done', {'action': 'history'})\n"
        + "  return result\n"
        + "service.Service.action = acknowledge\n"
        + "service.main()\n")
      state = app / "settings"
      state.mkdir()
      saved = state / "notifications.json"
      saved.write_text(json.dumps([SAVED]))
      (app / "shell.qml").write_text('''//@ pragma Env HYPRLARP_PREVIEW=1
import QtQuick
import Quickshell
import "''' + (ROOT / "core").as_uri() + '''" as Core
ShellRoot {
  id: root
  property bool started: false
  property bool applied: false
  property int historyWrites: 0
  function verify(value, message) {
    if (!value) { console.error(message); Qt.quit(); throw new Error(message); }
  }
  property var incoming: ({id: 2, appName: "New app", desktopEntry: "new-app", summary: "New notification",
    body: "New body", appIcon: "", actions: [], hints: {}, urgency: 1, expireTimeout: 6000,
    tracked: false, transient: false, closed: {connect: function(handler) {}, disconnect: function(handler) {}}})
  Connections {
    target: Core.Bridge
    function onActionFinished(action) {
      if (action === "history") root.historyWrites++;
    }
  }
  Timer {
    interval: 20; repeat: true; running: true
    onTriggered: {
      if (!Core.Bridge.ready) return;
      if (!root.started) {
        root.started = true;
        ''' + before_load + '''
        return;
      }
      if (!Core.Bridge.notificationHistoryReady) return;
      if (!root.applied) {
        root.applied = true;
        ''' + after_load + '''
        return;
      }
      if (''' + ("true" if wait_for_write else "false") + ''' && root.historyWrites === 0) return;
      ''' + checks + '''
      console.log("NOTIFICATION HISTORY CHECK COMPLETE"); stop(); Qt.quit();
    }
  }
}''')
      runtime = app / "runtime"
      runtime.mkdir(mode=0o700)
      environment = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "QT_QUICK_BACKEND": "software",
        "XDG_RUNTIME_DIR": str(runtime), "HYPRLARP_STATE_DIR": str(state), "HYPRLARP_PREVIEW": "1"}
      environment.pop("WAYLAND_DISPLAY", None)
      result = subprocess.run(["quickshell", "--path", str(app / "shell.qml"), "--no-color"],
        env=environment, text=True, capture_output=True, timeout=5)
      output = result.stdout + result.stderr
      self.assertEqual(result.returncode, 0, output)
      self.assertIn("NOTIFICATION HISTORY CHECK COMPLETE", output)
      self.assertNotIn("TypeError:", output)
      self.assertNotIn("ReferenceError:", output)
      return json.loads(saved.read_text())

  def test_marking_read_before_load_preserves_saved_and_new_notifications(self):
    stored = self.run_history('''
      root.verify(Core.Notices.history.length === 2, "saved and new notifications must survive");
      root.verify(Core.Notices.history[0].summary === "New notification" && !Core.Notices.history[0].read,
        "notifications received after marking read remain unread");
      root.verify(Core.Notices.history[1].token === "stored" && Core.Notices.history[1].read,
        "marking read must apply to the delayed saved history");
    ''', before_load="Core.Notices.markRead(); Core.Notices.receive(root.incoming);")
    self.assertEqual([item["summary"] for item in stored], ["New notification", "Saved notification"])
    self.assertEqual([item["read"] for item in stored], [False, True])

  def test_clearing_before_load_keeps_only_later_notifications(self):
    stored = self.run_history('''
      root.verify(Core.Notices.history.length === 1 && Core.Notices.history[0].summary === "New notification",
        "cleared saved notifications must not return when loading finishes");
    ''', before_load="Core.Notices.clear(); Core.Notices.receive(root.incoming);")
    self.assertEqual([item["summary"] for item in stored], ["New notification"])

  def test_late_instantiation_loads_an_already_received_history(self):
    stored = self.run_history('''
      root.verify(Core.Notices.history.length === 1 && Core.Notices.history[0].token === "stored",
        "a late notification singleton must still load saved history");
    ''', delay=0, wait_for_write=False)
    self.assertEqual(stored, [SAVED])

  def test_backend_reload_does_not_restore_removed_notifications(self):
    stored = self.run_history('''
      root.verify(Core.Notices.history.length === 0, "reloading an older disk snapshot must keep local removals");
    ''', before_load="Core.Notices.markRead();", after_load='''
      Core.Notices.clear();
      Core.Bridge.consume(JSON.stringify({type: "history", data: [
        {id: 1, token: "stored", app: "Stored app", appId: "stored-app", summary: "Saved notification",
          body: "Saved body", icon: "", time: 1000, urgency: 1, read: false, timeout: 0}]}));
    ''')
    self.assertEqual(stored, [])


if __name__ == "__main__":
  unittest.main()
