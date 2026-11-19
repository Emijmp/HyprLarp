import copy
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from backend import greeter, lockscreen
from backend.service import DEFAULTS, PALETTES, Service, Store
from backend.theme_context import effective_name, resolve, safe_accent
from tools.install_greeter import SYNC_FILES


class ContextThemeTests(unittest.TestCase):
  def setUp(self):
    self.settings = copy.deepcopy(DEFAULTS)
    self.settings.update(theme='amoled', accent='#abcdef', themeScheduleEnabled=True,
      themeDay='paper', themeNight='amoled', themeDayStart='07:00', themeNightStart='19:00')

  def test_day_night_and_midnight_boundaries_match_shell_and_do_not_mutate_preferences(self):
    before = copy.deepcopy(self.settings)
    for hour, minute, expected in [(6, 59, 'amoled'), (7, 0, 'paper'), (18, 59, 'paper'), (19, 0, 'amoled')]:
      self.assertEqual(effective_name(self.settings, now=datetime(2026, 11, 18, hour, minute)), expected)
    self.settings.update(themeDayStart='22:00', themeNightStart='06:00')
    for hour, expected in [(21, 'amoled'), (22, 'paper'), (0, 'paper'), (5, 'paper'), (6, 'amoled')]:
      self.assertEqual(effective_name(self.settings, now=datetime(2026, 11, 18, hour)), expected)
    self.settings.update(themeDayStart='07:00', themeNightStart='19:00')
    name, palette, accent = resolve(self.settings, PALETTES, now=datetime(2026, 11, 18, 8))
    self.assertEqual((name, accent), ('paper', PALETTES['paper']['accent']))
    palette['accent'] = '#000000'
    self.assertNotEqual(PALETTES['paper']['accent'], '#000000')
    self.assertEqual(self.settings, before)
    self.assertEqual(resolve(self.settings, PALETTES, now=datetime(2026, 11, 18, 20))[2], '#abcdef')

  def test_lock_render_and_tinted_assets_use_the_current_scheduled_palette(self):
    before = copy.deepcopy(self.settings)
    for hour, theme, accent in [(8, 'paper', PALETTES['paper']['accent']), (20, 'amoled', '#abcdef')]:
      now = datetime(2026, 11, 18, hour)
      rendered = lockscreen.render(self.settings, PALETTES, now=now)
      self.assertIn('$surface = rgb(' + PALETTES[theme]['surface'][1:] + ')', rendered)
      self.assertIn('$accent = rgb(' + accent[1:] + ')', rendered)
      with tempfile.TemporaryDirectory() as temporary, patch.object(lockscreen.shutil, 'which', return_value=None):
        _, assets = lockscreen.prepare(self.settings, Path(temporary), now=now)
        svg = (lockscreen.ROOT / 'assets/hyprlarp.svg').read_bytes().replace(b'#ffffff', accent.encode())
        self.assertEqual(assets['logoHash'], hashlib.sha256(svg).hexdigest())
    self.assertEqual(self.settings, before)

  def test_greeter_payload_reports_effective_theme_and_keeps_the_settings_file(self):
    with tempfile.TemporaryDirectory() as temporary:
      folder = Path(temporary)
      settings_file = folder / 'settings.json'
      settings_file.write_text(json.dumps(self.settings))
      before = settings_file.read_bytes()
      for hour, theme in [(8, 'paper'), (20, 'amoled')]:
        now = datetime(2026, 11, 18, hour)
        look = greeter.appearance(self.settings, PALETTES, now=now)
        self.assertEqual(look['palette']['surface'], PALETTES[theme]['surface'])
        expected = PALETTES['paper']['accent'] if theme == 'paper' else '#abcdef'
        self.assertEqual(look['palette']['primary'], expected)
        _, information = greeter.payload(settings_file, folder / 'waypaper.ini', now=now)
        self.assertEqual(information['theme'], theme)
      self.assertEqual(settings_file.read_bytes(), before)

  def test_high_contrast_still_takes_precedence_and_disabled_schedule_uses_manual_theme(self):
    now = datetime(2026, 11, 18, 8)
    settings = {**self.settings, 'accessibilityHighContrast': True}
    self.assertEqual(greeter.appearance(settings, PALETTES, now=now)['palette']['primary'], '#000000')
    self.assertIn('$accent = rgb(000000)', lockscreen.render(settings, PALETTES, now=now))
    self.assertEqual(effective_name({**settings, 'themeScheduleEnabled': False}, now=now), 'amoled')

  @unittest.skipUnless(shutil.which('node'), 'Node required to compare the shell color algorithm')
  def test_native_and_shell_accent_contrast_algorithms_match(self):
    samples = [[palette['accent'], [palette[role] for role in ('surface', 'raised', 'moduleSurface')]] for palette in PALETTES.values()]
    samples += [['#101010', ['#000000', '#181818']], ['#fdfdfd', ['#ffffff', '#dddddd']],
      ['#111111', ['#eeeeee', '#101010']], ['invalid', ['#000000']], ['#222222', ['#757575']]]
    script = "const fs=require('fs'),vm=require('vm'); const ensure=vm.runInNewContext(fs.readFileSync(process.argv[1],'utf8')+';ensureContrast'); process.stdout.write(JSON.stringify(JSON.parse(process.argv[2]).map(([color,backgrounds])=>ensure(color,backgrounds,4.5))));"
    result = subprocess.run(['node', '-e', script, str(greeter.ROOT / 'core/accessibility.js'), json.dumps(samples)], capture_output=True, text=True, timeout=5)
    self.assertEqual(result.returncode, 0, result.stderr)
    self.assertEqual([safe_accent(color, backgrounds) for color, backgrounds in samples], json.loads(result.stdout))
    self.assertEqual(safe_accent('#222222', ['#757575']), '#020202')

  def test_installer_standalone_files_can_export_without_the_repository(self):
    with tempfile.TemporaryDirectory() as temporary:
      folder = Path(temporary)
      for name in SYNC_FILES:
        destination = folder / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(greeter.ROOT / name, destination)
      settings = folder / 'settings.json'
      settings.write_text(json.dumps(self.settings))
      result = subprocess.run([sys.executable, str(folder / 'backend/greeter.py'), 'export',
        '--settings', str(settings), '--output', str(folder / 'export')], cwd=folder,
        capture_output=True, text=True, timeout=5)
      self.assertEqual(result.returncode, 0, result.stderr)
      self.assertIn(json.loads(result.stdout)['theme'], ['paper', 'amoled'])
      self.assertTrue((folder / 'export/sync.toml').is_file())

  def test_existing_sync_unit_is_started_only_for_actual_native_context_changes(self):
    with tempfile.TemporaryDirectory() as temporary:
      folder = Path(temporary)
      store = Store(folder / 'settings')
      store.update({key: value for key, value in self.settings.items() if key != 'version'})
      service = Service(store)
      self.addCleanup(service.executor.shutdown, wait=False, cancel_futures=True)
      events = []
      service.emit = lambda kind, data: events.append((kind, data))
      with patch.dict(os.environ, {'XDG_CONFIG_HOME': str(folder)}), patch('backend.service.command') as command, \
          patch('backend.theme_context.datetime') as clock, patch.object(service, 'queue_refresh', side_effect=lambda name, function, latest=False: function()):
        clock.now.return_value = datetime(2026, 11, 18, 8)
        service.action({'action': 'theme-context-changed', 'data': {}})
        command.assert_not_called()
        unit = folder / 'systemd/user/hyprlarp-greeter-sync.service'
        unit.parent.mkdir(parents=True)
        unit.write_text('[Service]\nType=oneshot\n')
        for _ in range(3):
          service.action({'action': 'theme-context-changed', 'data': {}})
        command.assert_called_once_with(['systemctl', '--user', 'start', '--no-block', 'hyprlarp-greeter-sync.service'], timeout=3)
        clock.now.return_value = datetime(2026, 11, 18, 20)
        service.action({'action': 'theme-context-changed', 'data': {}})
        self.assertEqual(command.call_count, 2)
        service.action({'action': 'theme-context-changed', 'data': {'theme': 'paper'}})
        self.assertEqual(command.call_count, 2)
        self.assertTrue(any(kind == 'action-error' for kind, _ in events))
        for attr in ['preview', 'settings_only']:
          setattr(service, attr, True)
          service.synced_context_theme = None
          service.action({'action': 'theme-context-changed', 'data': {}})
          self.assertEqual(command.call_count, 2)
          setattr(service, attr, False)
      self.assertEqual(store.settings, self.settings)


if __name__ == '__main__':
  unittest.main()
