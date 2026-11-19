import copy
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from backend.service import DEFAULTS, PALETTES, ROOT, Store, render_lock_config, validate_setting
from backend.layouts import section_updates
from backend.greeter import appearance, accessibility, sync_layout
from greeter.model import read_accessibility
from backend.revisions import fingerprint


class AccessibilityTests(unittest.TestCase):
  def test_existing_configuration_history_survives_new_accessibility_defaults(self):
    with tempfile.TemporaryDirectory() as temporary:
      directory = Path(temporary)
      store = Store(directory)
      store.update({'font': 'Sans Serif'})
      keys = {key for key in DEFAULTS if key.startswith('accessibility')}
      settings = {key: value for key, value in store.settings.items() if key not in keys}
      history = json.loads(store.revisions.path.read_text())
      history['head'] = fingerprint(settings)
      for revision in history['revisions']:
        for key in keys: revision['settings'].pop(key, None)
      store.file.write_text(json.dumps(settings))
      store.revisions.path.write_text(json.dumps(history))
      restored = Store(directory)
      self.assertEqual(restored.history_state()['undo'], 1)
      self.assertEqual(restored.undo()['font'], DEFAULTS['font'])
      self.assertTrue(restored.revisions.listing(restored.settings))

  def test_preferences_are_validated_persisted_and_undoable(self):
    with tempfile.TemporaryDirectory() as temporary:
      store = Store(Path(temporary))
      preferences = {'accessibilityTextScale': 1.75, 'accessibilityHighContrast': True,
        'accessibilityLargeTargets': True, 'accessibilityReducedMotion': True}
      store.update(preferences)
      loaded = Store(Path(temporary))
      for key, value in preferences.items(): self.assertEqual(loaded.settings[key], value)
      store.update(section_updates('General', DEFAULTS, store.settings))
      for key in preferences: self.assertEqual(store.settings[key], DEFAULTS[key])
      restored = store.undo()
      for key, value in preferences.items(): self.assertEqual(restored[key], value)
      for value in [0, .5, 2.1, True, None, float('nan'), '2']:
        with self.subTest(value=value), self.assertRaises(ValueError): validate_setting('accessibilityTextScale', value)

  def test_high_contrast_is_exported_without_overwriting_the_selected_palette(self):
    settings = copy.deepcopy(DEFAULTS)
    settings.update(theme='gruvbox', accent='#00ff00', accessibilityHighContrast=True)
    before = copy.deepcopy(settings)
    payload = appearance(settings, PALETTES)
    self.assertEqual(payload['palette']['surface'], '#000000')
    self.assertEqual(payload['palette']['primary'], '#ffffff')
    self.assertEqual(settings, before)
    settings.update(theme='custom', customPalette={**settings['customPalette'], 'background': '#ffffff', 'surface': '#eeeeee'})
    payload = appearance(settings, PALETTES)
    self.assertEqual(payload['palette']['surface'], '#ffffff')
    self.assertEqual(payload['palette']['on_surface'], '#000000')

  def test_greeter_preferences_are_small_validated_metadata_and_ignore_symlinks(self):
    with tempfile.TemporaryDirectory() as temporary:
      preferences = Path(temporary) / 'layout.json'
      options = accessibility({**DEFAULTS, 'accessibilityTextScale': 2, 'accessibilityLargeTargets': True})
      sync_layout('centered', preferences, accessibility_options=options)
      self.assertEqual(read_accessibility(preferences), options)
      self.assertLess(preferences.stat().st_size, 1024)
      linked = Path(temporary) / 'link'
      linked.symlink_to(preferences)
      self.assertEqual(read_accessibility(linked)['textScale'], 1)
      for value in [True, 0, 3, '2']:
        preferences.write_text(json.dumps({'accessibility': {'textScale': value}}))
        self.assertEqual(read_accessibility(preferences)['textScale'], 1)

  def test_native_lock_follows_contrast_and_reduced_motion_at_large_text(self):
    settings = {**DEFAULTS, 'greeterLayout': 'centered', 'animations': True,
      'accessibilityReducedMotion': True, 'accessibilityHighContrast': True, 'accessibilityTextScale': 2}
    config = render_lock_config(settings, outputs=[{'name': 'eDP-1', 'width': 1920, 'height': 1080, 'scale': 1.25}])
    self.assertIn('$SURFACE', config.upper())
    self.assertNotIn('enabled = true', config)
    self.assertIn('position = 0, 0', config)
    self.assertIn('font_size =', config)

  @unittest.skipUnless(shutil.which('node'), 'Node unavailable')
  def test_color_contrast_and_focus_navigation_model(self):
    result = subprocess.run(['node', str(Path(__file__).with_suffix('.js'))], capture_output=True, text=True)
    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
