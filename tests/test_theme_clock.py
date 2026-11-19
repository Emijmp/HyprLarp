"""Exercise shared panel bounds and the real Theme component's clock binding."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ThemeClockAndPanelTests(unittest.TestCase):
  @unittest.skipUnless(shutil.which('node'), 'Node is required for JS geometry checks')
  def test_panel_bounds_include_vertical_bars_at_large_text_and_small_screens(self):
    result = subprocess.run(['node', str(ROOT / 'tests/test_panel_geometry.js')], capture_output=True, text=True, timeout=5)
    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

  @unittest.skipUnless(shutil.which('quickshell') or shutil.which('qs'), 'Quickshell is required for clock binding checks')
  def test_theme_changes_when_clock_source_changes_without_overriding_local_minute(self):
    with tempfile.TemporaryDirectory(prefix='hyprlarp-clock-binding-') as temporary:
      folder = Path(temporary)
      fixture = folder / 'fixture'
      fixture.mkdir()
      shutil.copy2(ROOT / 'core/Theme.qml', fixture / 'Theme.qml')
      shutil.copy2(ROOT / 'core/accessibility.js', fixture / 'accessibility.js')
      (fixture / 'qmldir').write_text('module ThemeFixture\nsingleton Theme 1.0 Theme.qml\nsingleton Bridge 1.0 Bridge.qml\nsingleton Clock 1.0 Clock.qml\n')
      (fixture / 'Clock.qml').write_text('pragma Singleton\nimport QtQuick\nQtObject { property date date: new Date(2026, 0, 1, 6, 59, 59) }\n')
      defaults = json.loads((ROOT / 'config/defaults.json').read_text())
      defaults.update(themeScheduleEnabled=True, themeDay='paper', themeNight='amoled')
      palettes = json.loads((ROOT / 'config/palettes.json').read_text())
      (fixture / 'Bridge.qml').write_text('pragma Singleton\nimport QtQuick\nQtObject {\nproperty var settings: ' + json.dumps(defaults) + '\nproperty var palettes: ' + json.dumps(palettes) + '\nfunction configureMany(values) {}\nfunction configure(key, value) {}\n}\n')
      (folder / 'shell.qml').write_text('''import QtQuick
import Quickshell
import "fixture"
ShellRoot {
  id: testRoot
  property int step: 0
  function verify(condition, message) {
    if (!condition) { console.error("CLOCK_BINDING_FAILED " + message); Qt.quit(1); }
  }
  Timer {
    interval: 25
    running: true
    repeat: true
    onTriggered: {
      switch (testRoot.step++) {
      case 0:
        testRoot.verify(Theme.scheduledTheme === "amoled", "night before day boundary");
        Clock.date = new Date(2026, 0, 1, 7, 0, 0);
        break;
      case 1:
        testRoot.verify(Theme.localMinute === 420 && Theme.scheduledTheme === "paper", "clock notification switches to day");
        Clock.date = new Date(2026, 0, 1, 19, 0, 0);
        break;
      case 2:
        testRoot.verify(Theme.localMinute === 1140 && Theme.scheduledTheme === "amoled", "clock notification switches to night");
        Clock.date = new Date(2026, 0, 2, 0, 1, 0);
        break;
      case 3:
        testRoot.verify(Theme.localMinute === 1 && Theme.scheduledTheme === "amoled", "midnight follows clock");
        testRoot.verify(Theme.px(4) === 4 && Theme.fontPx(4) >= 12, "font minimum does not alter geometry");
        console.log("CLOCK_BINDING_COMPLETE");
        Qt.quit();
      }
    }
  }
}
''')
      environment = {**os.environ, 'QT_QPA_PLATFORM': 'offscreen', 'QT_QUICK_BACKEND': 'software', 'XDG_RUNTIME_DIR': str(folder)}
      environment.pop('WAYLAND_DISPLAY', None)
      result = subprocess.run([shutil.which('quickshell') or shutil.which('qs'), '--path', str(folder / 'shell.qml'), '--no-color'], env=environment, capture_output=True, text=True, timeout=10)
      output = result.stdout + result.stderr
      self.assertEqual(result.returncode, 0, output)
      self.assertIn('CLOCK_BINDING_COMPLETE', output)
      for marker in ['CLOCK_BINDING_FAILED', 'ReferenceError:', 'TypeError:', 'WARN scene:']:
        self.assertNotIn(marker, output)
