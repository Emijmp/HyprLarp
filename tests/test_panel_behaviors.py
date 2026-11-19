import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('quickshell'), 'Quickshell is unavailable')
class PanelBehaviorTests(unittest.TestCase):
  def run_qml(self, contents, *, clipboard_native_branch=False):
    with tempfile.TemporaryDirectory(prefix='hyprlarp-panels-') as folder:
      app = Path(folder)
      (app / 'backend').symlink_to(ROOT / 'backend', target_is_directory=True)
      imports = '\n'.join('import "' + (ROOT / name).as_uri() + '" as ' + alias
        for name, alias in [('core', 'Core'), ('widgets', 'Widgets'), ('panels', 'Panels')])
      if clipboard_native_branch:
        # Exercise thumbnail failure handling without enabling native backend
        # actions: the real preview backend safely rejects each request.
        clipboard = (ROOT / 'panels/ClipboardPanel.qml').read_text()
        clipboard = clipboard.replace('"../core"', '"' + (ROOT / 'core').as_uri() + '"')
        clipboard = clipboard.replace('"../components"', '"' + (ROOT / 'components').as_uri() + '"')
        clipboard = clipboard.replace(' && !Bridge.preview', '')
        (app / 'TestClipboard.qml').write_text(clipboard)
        imports += '\nimport "." as Local'
      fixture = '''//@ pragma UseQApplication
//@ pragma Env QT_QUICK_CONTROLS_STYLE=Basic
//@ pragma Env HYPRLARP_PREVIEW=1
import QtQuick
import QtTest
import Quickshell
''' + imports + '\n' + contents
      (app / 'shell.qml').write_text(fixture)
      runtime = app / 'runtime'
      runtime.mkdir(mode=0o700)
      environment = {**os.environ, 'QT_QPA_PLATFORM': 'offscreen', 'QT_QUICK_BACKEND': 'software',
        'XDG_RUNTIME_DIR': str(runtime), 'HYPRLARP_STATE_DIR': str(app / 'settings'), 'HYPRLARP_PREVIEW': '1'}
      environment.pop('WAYLAND_DISPLAY', None)
      try:
        result = subprocess.run(['quickshell', '--path', str(app / 'shell.qml'), '--no-color'],
          env=environment, text=True, capture_output=True, timeout=5)
      except subprocess.TimeoutExpired as error:
        self.fail((error.stdout or b'').decode() + (error.stderr or b'').decode())
      output = result.stdout + result.stderr
      output = output[-16000:]
      self.assertEqual(result.returncode, 0, output)
      self.assertIn('PANEL CHECK COMPLETE', output)
      self.assertNotIn('ReferenceError:', output)
      self.assertNotIn('TypeError:', output)

  def test_blank_panel_click_stays_open_and_outside_click_closes(self):
    self.run_qml('''ShellRoot {
      id: root
      property int step: 0
      function verify(value, label) { if (!value) { console.error(label); Qt.quit(); throw new Error(label); } }
      function find(item, name) {
        if (item.objectName === name) return item;
        for (const child of item.children || []) { const found = find(child, name); if (found) return found; }
        return null;
      }
      FloatingWindow {
        implicitWidth: 980; implicitHeight: 820
        TestEvent { id: pointer }
        Widgets.PanelOverlay { id: overlay; anchors.fill: parent }
      }
      Timer {
        interval: 100; repeat: true; running: true
        onTriggered: {
          if (!Core.Bridge.ready) return;
          if (root.step++ === 0) { Core.ShellState.open("session"); return; }
          pointer.mouseClick(overlay.surface, 2, 2, Qt.LeftButton, Qt.NoModifier, 0);
          root.verify(Core.ShellState.panel === "session", "clicking empty panel background unexpectedly dismisses it");
          const close = root.find(overlay.surface, "panel-close");
          pointer.mouseClick(close, close.width / 2, close.height / 2, Qt.LeftButton, Qt.NoModifier, 0);
          root.verify(Core.ShellState.panel === "", "panel controls still receive their clicks");
          Core.ShellState.open("session");
          pointer.mouseClick(overlay, 1, overlay.height - 1, Qt.LeftButton, Qt.NoModifier, 0);
          root.verify(Core.ShellState.panel === "", "outside click must still dismiss the panel");
          console.log("PANEL CHECK COMPLETE"); stop(); Qt.quit();
        }
      }
    }''')

  def test_compact_performance_hides_process_and_panel_load_rows(self):
    self.run_qml('''ShellRoot {
      id: root
      property int step: 0
      function rows(item, prefix) {
        let count = 0;
        if (item.text && String(item.text).startsWith(prefix) && item.visible) count++;
        for (const child of item.children || []) count += rows(child, prefix);
        return count;
      }
      function verify(value, label) { if (!value) { console.error(label); Qt.quit(); throw new Error(label); } }
      FloatingWindow {
        implicitWidth: 600; implicitHeight: 820
        Panels.PerformancePanel { id: panel; width: parent.width }
      }
      Timer {
        interval: 100; repeat: true; running: true
        onTriggered: {
          if (!Core.Bridge.ready) return;
          if (root.step++ === 0) {
            Core.Bridge.performance = {mode: "preview", current: {parts: [{role: "backend", pid: 123, cpuPercent: 3, rssMiB: 40}]},
              history: [], panelLoads: [{name: "control", milliseconds: 8}], samples: [], cpuTickMs: 10};
            return;
          }
          root.verify(rows(panel, "CPU 3.00%") === 1 && rows(panel, "Carga · ") === 1, "expanded performance rows are present");
          panel.compact = true;
          root.verify(rows(panel, "CPU 3.00%") === 0 && rows(panel, "Carga · ") === 0, "compact performance must hide repeated process and load rows");
          console.log("PANEL CHECK COMPLETE"); stop(); Qt.quit();
        }
      }
    }''')

  def test_filtered_performance_comparison_survives_unrelated_history_updates(self):
    self.run_qml('''ShellRoot {
      id: root
      property int step: 0
      property string selected: ""
      function verify(value, label) { if (!value) { console.error(label); Qt.quit(); throw new Error(label); } }
      function report(id, label, at) {
        return {id: id, label: label, createdAt: at, revision: "123456789abc", context: {mode: "preview", fingerprint: "same"},
          startupMs: null, summary: {seconds: 15, samples: 7, cpuPercent: 1, rssMiB: 50, peakRssMiB: 55, pssMiB: 40}};
      }
      function update(history) { Core.Bridge.performance = {mode: "preview", current: {}, history: history, panelLoads: [], samples: [], cpuTickMs: 10}; }
      FloatingWindow {
        implicitWidth: 600; implicitHeight: 820
        Panels.PerformancePanel { id: panel; width: parent.width }
      }
      Timer {
        interval: 100; repeat: true; running: true
        onTriggered: {
          if (!Core.Bridge.ready) return;
          switch (root.step++) {
          case 0:
            root.update([root.report("a", "Coincide A", 1000), root.report("b", "Coincide B", 2000)]);
            panel.historyQuery = "Coincide";
            return;
          case 1:
            root.verify(panel.first && panel.second && panel.first.id !== panel.second.id, "two filtered reports are selected");
            root.selected = panel.secondId;
            root.update([root.report("a", "Coincide A", 1000), root.report("b", "Coincide B", 2000), root.report("c", "Otra prueba", 3000)]);
            return;
          case 2:
            root.verify(panel.filteredHistory.length === 2 && panel.secondId === root.selected && panel.second, "a new report outside the filter preserves the visible comparison");
            root.update([root.report("a", "Coincide A", 1000), root.report("c", "Otra prueba", 3000)]);
            return;
          default:
            root.verify(panel.filteredHistory.length === 1 && panel.second && panel.secondId === "a", "deleting a selected report chooses a filtered fallback");
            console.log("PANEL CHECK COMPLETE"); stop(); Qt.quit();
          }
        }
      }
    }''')

  def test_bad_cached_clipboard_image_does_not_trigger_an_endless_retry(self):
    self.run_qml('''ShellRoot {
      id: root
      property int requests: 0
      property bool started: false
      FloatingWindow {
        implicitWidth: 700; implicitHeight: 600
        Loader { id: clipboard; width: parent.width; active: root.started; sourceComponent: Component { Local.TestClipboard {} } }
      }
      Connections {
        target: Core.Bridge
        function onActionFailed(action, message) {
          if (action !== "clipboard-thumbnail") return;
          root.requests++;
          Core.Bridge.clipboardThumbnails = {"1": "data:image/png;base64,bm90LWEtcG5n"};
        }
      }
      Timer {
        interval: 100; running: true; repeat: true
        onTriggered: {
          if (!Core.Bridge.ready || root.started) return;
          Core.Bridge.clipboard = [{id: "1", raw: "1\\t[[ binary data ]]", text: "Image", image: true}];
          root.started = true; check.restart(); stop();
        }
      }
      Timer {
        id: check; interval: 700
        onTriggered: {
          if (root.requests !== 1) { console.error("bad thumbnail caused " + root.requests + " requests instead of one"); Qt.quit(); throw new Error("bad thumbnail retry"); }
          console.log("PANEL CHECK COMPLETE"); Qt.quit();
        }
      }
    }''', clipboard_native_branch=True)

  def test_performance_fault_indicator_uses_the_available_alert_color(self):
    self.run_qml('''ShellRoot {
      id: root
      property int step: 0
      function find(item, name) {
        if (item.objectName === name) return item;
        for (const child of item.children || []) { const found = find(child, name); if (found) return found; }
        return null;
      }
      function verify(value, label) { if (!value) { console.error(label); Qt.quit(); throw new Error(label); } }
      FloatingWindow {
        implicitWidth: 600; implicitHeight: 820
        Panels.PerformancePanel { id: panel; width: parent.width }
      }
      Timer {
        interval: 100; repeat: true; running: true
        onTriggered: {
          if (!Core.Bridge.ready) return;
          switch (root.step++) {
          case 0:
            Core.Bridge.faults = [{id: "backend:metrics", events: [Date.now() / 1000], blocked: false}];
            return;
          case 1:
            root.verify(panel.recentFaults === 1, "a just-reported fault is counted immediately");
            root.verify(root.find(panel, "performance-stability").color.toString() === Core.Theme.danger.toString(), "fault indicator uses the theme alert color");
            Core.Bridge.faults = [{id: "backend:metrics", events: [(Date.now() - 360000) / 1000], blocked: false}];
            return;
          default:
            root.verify(panel.recentFaults === 0, "old faults are excluded");
            console.log("PANEL CHECK COMPLETE"); stop(); Qt.quit();
          }
        }
      }
    }''')
