import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PanelPreviewTests(unittest.TestCase):
  @unittest.skipUnless(shutil.which('quickshell'), 'Quickshell is unavailable')
  def test_real_apply_undo_reset_rejection_and_scaled_previews(self):
    with tempfile.TemporaryDirectory(prefix='hyprlarp-visual-') as folder:
      wallpaper = Path(folder) / 'fondo # % ñ.svg'
      wallpaper.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="200" height="120"><rect width="200" height="120" fill="#101010"/><circle cx="100" cy="60" r="40" fill="#aa9922"/></svg>')
      environment = {**os.environ, 'QT_QPA_PLATFORM': 'offscreen', 'QT_QUICK_BACKEND': 'software',
        'XDG_RUNTIME_DIR': folder, 'HYPRLARP_STATE_DIR': str(Path(folder) / 'settings'), 'HYPRLARP_PREVIEW': '1',
        'HYPRLARP_VISUAL_WALLPAPER': str(wallpaper)}
      environment.pop('WAYLAND_DISPLAY', None)
      result = subprocess.run(['quickshell', '--path', str(ROOT / 'visual-check.qml'), '--no-color'],
        env=environment, text=True, capture_output=True, timeout=35)
      output = result.stdout + result.stderr
      self.assertEqual(result.returncode, 0, output)
      self.assertIn('VISUAL COMPLETE', output)
      for marker in ['WARN scene:', 'ReferenceError:', 'TypeError:', 'Unable to assign', 'Binding loop']:
        self.assertNotIn(marker, output)


if __name__ == '__main__':
  unittest.main()
