"""Bounded shared rendering work without changing appearance or module behavior."""

from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class UiOptimizationTests(unittest.TestCase):
  @unittest.skipUnless(shutil.which('quickshell'), 'Quickshell unavailable')
  def test_svg_cache_is_shared_between_actual_icon_instances(self):
    with tempfile.TemporaryDirectory(prefix='hyprlarp-icon-sharing-') as temporary:
      app = Path(temporary)
      (app / 'backend').symlink_to(ROOT / 'backend', target_is_directory=True)
      fixture = '''//@ pragma UseQApplication
//@ pragma Env QT_QUICK_CONTROLS_STYLE=Basic
//@ pragma Env HYPRLARP_PREVIEW=1
import QtQuick
import Quickshell
import "CORE" as Core
import "COMPONENTS" as Components
import "ICONS" as Icons
ShellRoot {
  id: root
  property int step: 0
  property var afterFirst: null
  function verify(condition, message) {
    if (!condition) { console.error(message); Qt.quit(); throw new Error(message); }
  }
  FloatingWindow {
    implicitWidth: 200; implicitHeight: 100
    Components.Icon { id: first; name: "close"; color: "#ffffff"; width: 24; height: 24 }
    Components.Icon { id: second; name: "close"; color: "#ffffff"; width: 24; height: 24; x: 30 }
  }
  Timer {
    interval: 100; repeat: true; running: true
    onTriggered: {
      if (!Core.Bridge.ready) return;
      if (root.step === 0) {
        verify(!!Icons.iconSourceCache.close, "Icon instances populate the shared script cache");
        first.color = "#123456";
      } else if (root.step === 1) {
        root.afterFirst = Icons.iconSourceCache.close;
        verify(root.afterFirst.color === "#123456", "a tint change is visible through another import of icons.js");
        second.color = "#123456";
      } else {
        verify(Icons.iconSourceCache.close === root.afterFirst, "the second Icon reuses the first Icon's cache entry");
        verify(Object.keys(Icons.iconSourceCache).length === 1, "one icon name retains one tint across both instances");
        console.log("SHARED ICON COMPLETE"); stop(); Qt.quit();
      }
      root.step++;
    }
  }
}
'''.replace('CORE', (ROOT / 'core').as_uri()).replace('COMPONENTS', (ROOT / 'components').as_uri()).replace('ICONS', (ROOT / 'components/icons.js').as_uri())
      (app / 'shell.qml').write_text(fixture)
      environment = {**os.environ, 'QT_QPA_PLATFORM': 'offscreen', 'QT_QUICK_BACKEND': 'software',
        'XDG_RUNTIME_DIR': temporary, 'HYPRLARP_STATE_DIR': str(app / 'settings'), 'HYPRLARP_PREVIEW': '1'}
      environment.pop('WAYLAND_DISPLAY', None)
      result = subprocess.run(['quickshell', '--path', str(app / 'shell.qml'), '--no-color'],
        env=environment, text=True, capture_output=True, timeout=7)
      output = result.stdout + result.stderr
      self.assertEqual(result.returncode, 0, output)
      self.assertIn('SHARED ICON COMPLETE', output)
      self.assertFalse(any(message in output for message in ['TypeError:', 'ReferenceError:', 'Failed to load']))

  @unittest.skipUnless(shutil.which('node'), 'Node unavailable')
  def test_contrast_and_repeated_icon_rendering_stay_bounded(self):
    result = subprocess.run(['node', str(ROOT / 'tests/test_ui_optimization.js')],
      text=True, capture_output=True, timeout=10)
    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

  @unittest.skipUnless(shutil.which('quickshell'), 'Quickshell unavailable')
  def test_fault_index_and_conditional_bar_metrics_remain_reactive(self):
    with tempfile.TemporaryDirectory(prefix='hyprlarp-ui-work-') as temporary:
      app = Path(temporary)
      (app / 'backend').symlink_to(ROOT / 'backend', target_is_directory=True)
      fixture = '''//@ pragma UseQApplication
//@ pragma Env QT_QUICK_CONTROLS_STYLE=Basic
//@ pragma Env HYPRLARP_PREVIEW=1
import QtQuick
import Quickshell
import "CORE" as Core
import "WIDGETS" as Widgets
ShellRoot {
  function verify(condition, message) {
    if (!condition) { console.error(message); Qt.quit(); throw new Error(message); }
  }
  FloatingWindow {
    implicitWidth: 400; implicitHeight: 200
    Widgets.BarModule { id: launcher; moduleName: "launcher"; guide: Core.BarLayout; width: 100; height: 34 }
    Widgets.BarModule { id: clock; moduleName: "clock"; guide: Core.BarLayout; width: 100; height: 80; y: 40 }
  }
  Timer {
    interval: 150; repeat: true; running: true
    onTriggered: {
      if (!Core.Bridge.ready) return;
      verify(launcher.verticalClock === "" && clock.verticalClock === "", "hidden clocks do not format unused text");
      clock.vertical = true;
      verify(clock.verticalClock === Core.Clock.timeText.replace(/[: ]/g, "\\n"), "vertical clocks retain the current time");
      Core.Bridge.faults = [{id: "bar:clock", blocked: true}, {id: "bar:launcher", blocked: false}];
      verify(Core.Resilience.blocked("bar:clock") && !Core.Resilience.blocked("bar:launcher"), "fault index reflects the current blocked modules");
      Core.Bridge.faults = [{id: "bar:clock", blocked: false}, {id: "bar:launcher", blocked: true}];
      verify(!Core.Resilience.blocked("bar:clock") && Core.Resilience.blocked("bar:launcher"), "reset and newly blocked modules invalidate the index");
      console.log("UI WORK COMPLETE"); stop(); Qt.quit();
    }
  }
}
'''.replace('CORE', (ROOT / 'core').as_uri()).replace('WIDGETS', (ROOT / 'widgets').as_uri())
      (app / 'shell.qml').write_text(fixture)
      environment = {**os.environ, 'QT_QPA_PLATFORM': 'offscreen', 'QT_QUICK_BACKEND': 'software',
        'XDG_RUNTIME_DIR': temporary, 'HYPRLARP_STATE_DIR': str(app / 'settings'), 'HYPRLARP_PREVIEW': '1'}
      environment.pop('WAYLAND_DISPLAY', None)
      result = subprocess.run(['quickshell', '--path', str(app / 'shell.qml'), '--no-color'],
        env=environment, text=True, capture_output=True, timeout=7)
      output = result.stdout + result.stderr
      self.assertEqual(result.returncode, 0, output)
      self.assertIn('UI WORK COMPLETE', output)
      self.assertFalse(any(message in output for message in ['TypeError:', 'ReferenceError:', 'Failed to load']))


if __name__ == '__main__':
  unittest.main()
