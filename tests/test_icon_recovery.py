import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which("quickshell"), "Quickshell is unavailable")
class IconRecoveryTests(unittest.TestCase):
  def test_unanswered_icons_retry_after_backend_restart_and_keep_cached_results(self):
    with tempfile.TemporaryDirectory(prefix="hyprlarp-icon-recovery-") as folder:
      app = Path(folder)
      requests = app / "requests.jsonl"
      (app / "backend").mkdir()
      (app / "backend/service.py").write_text(
        "import json, os, sys\n"
        + "from pathlib import Path\n"
        + "sys.path.insert(0, " + repr(str(ROOT)) + ")\n"
        + "from backend import service\n"
        + "requests = Path(" + repr(str(requests)) + ")\n"
        + "original = service.Service.action\n"
        + "def interrupted(self, request):\n"
        + "  if request.get('action') == 'app-icons':\n"
        + "    first = not requests.exists()\n"
        + "    with requests.open('a') as log:\n"
        + "      log.write(json.dumps(request['data']['names']) + '\\n')\n"
        + "    if first:\n"
        + "      os._exit(23)\n"
        + "  return original(self, request)\n"
        + "service.Service.action = interrupted\n"
        + "service.main()\n")
      icon = ROOT / "assets/application.svg"
      cached = str(app / "cached.svg")
      shutil.copyfile(icon, cached)
      data = app / "data"
      (data / "applications").mkdir(parents=True)
      (data / "applications/cached.desktop").write_text(
        "[Desktop Entry]\nType=Application\nName=Cached fixture\nExec=true\nIcon=" + cached + "\n")
      (app / "shell.qml").write_text('''//@ pragma Env HYPRLARP_PREVIEW=1
import QtQuick
import Quickshell
import "''' + (ROOT / "core").as_uri() + '''" as Core
ShellRoot {
  id: root
  property bool started: false
  property bool interrupted: false
  readonly property string recovered: started ? Core.Applications.icon(''' + json.dumps(str(icon)) + ''') : ""
  readonly property string cached: started ? Core.Applications.icon(''' + json.dumps(cached) + ''') : ""
  Connections {
    target: Core.Bridge
    function onConnectedChanged() {
      if (root.started && !Core.Bridge.connected) root.interrupted = true;
    }
  }
  Timer {
    interval: 20; repeat: true; running: true
    onTriggered: {
      if (!Core.Bridge.ready || !Core.Bridge.notificationHistoryReady) return;
      if (!root.started) {
        if (!Core.Applications.index.some(entry => entry.app.icon === ''' + json.dumps(cached) + ''')) return;
        Core.Bridge.appIcons = {''' + json.dumps(cached) + ''': "file:///already-cached.svg"};
        root.started = true;
        return;
      }
      if (!root.interrupted || root.recovered !== ''' + json.dumps(icon.as_uri()) + ''') return;
      if (root.cached !== "file:///already-cached.svg") { Qt.quit(); throw new Error("cached icon changed during recovery"); }
      console.log("ICON RECOVERY CHECK COMPLETE"); stop(); Qt.quit();
    }
  }
}''')
      runtime = app / "runtime"
      runtime.mkdir(mode=0o700)
      state = app / "settings"
      state.mkdir()
      (state / "settings.json").write_text(json.dumps({"showAppIcons": True}))
      environment = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "QT_QUICK_BACKEND": "software",
        "XDG_RUNTIME_DIR": str(runtime), "XDG_DATA_HOME": str(data), "HYPRLARP_STATE_DIR": str(state), "HYPRLARP_PREVIEW": "1"}
      environment.pop("WAYLAND_DISPLAY", None)
      try:
        result = subprocess.run(["quickshell", "--path", str(app / "shell.qml"), "--no-color"],
          env=environment, text=True, capture_output=True, timeout=6)
      except subprocess.TimeoutExpired as error:
        self.fail((error.stdout or b"").decode() + (error.stderr or b"").decode())
      output = result.stdout + result.stderr
      self.assertEqual(result.returncode, 0, output)
      self.assertIn("ICON RECOVERY CHECK COMPLETE", output)
      self.assertNotIn("TypeError:", output)
      self.assertNotIn("ReferenceError:", output)
      batches = [json.loads(line) for line in requests.read_text().splitlines()]
      self.assertEqual(batches, [[str(icon)], [str(icon)]])
      self.assertTrue(all(len(batch) <= 128 for batch in batches))


if __name__ == "__main__":
  unittest.main()
