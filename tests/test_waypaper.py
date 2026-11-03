import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from backend.layouts import section_updates
from backend.service import DEFAULTS, Service, Store, validate_setting


class ExternalWallpaperTests(unittest.TestCase):
  def setUp(self):
    self.temp = tempfile.TemporaryDirectory()
    self.addCleanup(self.temp.cleanup)
    self.root = Path(self.temp.name)
    self.service = Service(Store(self.root / 'state'))
    self.addCleanup(self.service.executor.shutdown, wait=True)
    self.events = []
    self.service.emit = lambda kind, data: self.events.append((kind, data))

  def test_external_mode_is_optional_and_validated(self):
    self.assertEqual(DEFAULTS['wallpaperProvider'], 'internal')
    self.assertFalse(DEFAULTS['waypaperRestoreOnStartup'])
    for value in ['waypaper; reboot', 'invalid', [], None, True]:
      with self.subTest(value=value), self.assertRaises(ValueError):
        validate_setting('wallpaperProvider', value)
    with self.assertRaises(ValueError):
      validate_setting('waypaperRestoreOnStartup', 'yes')

  def test_switching_provider_preserves_image_and_supports_undo_and_section_reset(self):
    image = self.root / 'imagen # ñ.svg'
    image.write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
    store = self.service.store
    store.update({'wallpaper': str(image), 'wallpaperDirectory': str(self.root)})
    original = copy.deepcopy(store.settings)
    store.update({'wallpaperProvider': 'external', 'waypaperRestoreOnStartup': True})
    self.assertEqual(store.settings['wallpaper'], str(image))
    self.assertEqual(Store(store.directory).settings['wallpaperProvider'], 'external')
    store.undo()
    self.assertEqual(store.settings, original)
    store.redo()
    store.update(section_updates('Wallpapers', DEFAULTS, store.settings))
    self.assertEqual(store.settings['wallpaperProvider'], 'internal')
    self.assertFalse(store.settings['waypaperRestoreOnStartup'])
    store.undo()
    self.assertEqual(store.settings['wallpaper'], str(image))
    self.assertEqual(store.settings['wallpaperProvider'], 'external')

  def test_external_mode_skips_image_catalogue_and_directory_helpers(self):
    self.service.store.update({'wallpaperProvider': 'external'})
    with patch('backend.service.catalogue') as catalogue, patch('backend.service.optional') as command:
      self.service.refresh_wallpapers()
    catalogue.assert_not_called()
    command.assert_not_called()
    self.assertIn(('wallpapers', []), self.events)

  def test_manual_restore_uses_only_fixed_argv(self):
    self.service.store.update({'wallpaperProvider': 'external'})
    with patch('backend.service.command', return_value='') as command:
      self.service.action({'action': 'waypaper-restore', 'data': {'command': 'untrusted'}})
    command.assert_called_once_with(['waypaper', '--restore'], timeout=15)
    self.assertFalse([data for kind, data in self.events if kind == 'error'])

  def test_internal_and_preview_modes_never_restore(self):
    with patch('backend.service.command') as command:
      self.service.action({'action': 'waypaper-restore'})
      self.service.store.update({'wallpaperProvider': 'external', 'waypaperRestoreOnStartup': True})
      self.service.preview = True
      self.service.action({'action': 'waypaper-restore'})
      self.service.start_external_wallpaper()
    command.assert_not_called()
    self.assertEqual(sum(kind == 'error' for kind, _ in self.events), 2)

  def test_automatic_restore_is_opt_in_and_excluded_from_settings_only(self):
    self.service.queue_refresh = Mock()
    self.service.start_external_wallpaper()
    self.service.store.update({'wallpaperProvider': 'external'})
    self.service.start_external_wallpaper()
    self.service.queue_refresh.assert_not_called()
    self.service.store.update({'waypaperRestoreOnStartup': True})
    self.service.settings_only = True
    self.service.start_external_wallpaper()
    self.service.queue_refresh.assert_not_called()
    self.service.settings_only = False
    self.service.start_external_wallpaper()
    self.service.queue_refresh.assert_called_once_with('waypaper-restore', self.service.restore_waypaper)

  def test_standalone_settings_allow_explicit_restore(self):
    self.service.store.update({'wallpaperProvider': 'external'})
    self.service.settings_only = True
    with patch('backend.service.command', return_value='') as command:
      self.service.action({'action': 'waypaper-restore'})
    command.assert_called_once_with(['waypaper', '--restore'], timeout=15)

  def test_waypaper_launch_is_independent_and_never_receives_arbitrary_arguments(self):
    with patch('backend.service.shutil.which', return_value='/usr/bin/waypaper'), patch('backend.service.subprocess.Popen') as launch:
      self.service.action({'action': 'open-tool', 'data': {'name': 'waypaper', 'command': 'untrusted'}})
    self.assertEqual(launch.call_args.args, (['waypaper'],))
    self.assertTrue(launch.call_args.kwargs['start_new_session'])

  def test_restore_failure_is_reported_without_changing_provider_or_image(self):
    self.service.store.update({'wallpaperProvider': 'external'})
    before = copy.deepcopy(self.service.store.settings)
    with patch('backend.service.command', side_effect=RuntimeError('Waypaper could not restore')):
      self.service.action({'action': 'waypaper-restore'})
    self.assertEqual(self.service.store.settings, before)
    self.assertIn(('error', 'Waypaper could not restore'), self.events)
