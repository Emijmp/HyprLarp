import copy
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from backend.gaps import render, expression
from backend.layouts import section_updates
from backend.service import DEFAULTS, ROOT, Service, Store, lua_string, validate_setting


class WindowGapTests(unittest.TestCase):
  def setUp(self):
    self.temp = tempfile.TemporaryDirectory()
    self.addCleanup(self.temp.cleanup)
    self.root = Path(self.temp.name)
    self.service = Service(Store(self.root / 'state'))
    self.addCleanup(self.service.executor.shutdown, wait=True)
    self.events = []
    self.service.emit = lambda kind, data: self.events.append((kind, data))

  def enable(self):
    self.service.store.update({'windowGapsEnabled': True, 'windowGapsIn': 6,
      'windowGapsOut': {'top': 10, 'right': 20, 'bottom': 30, 'left': 40}})

  def test_gap_inputs_reject_injection_nonfinite_numbers_booleans_and_invalid_edges(self):
    for key, value in [('windowGapsIn', True), ('windowGapsIn', 65), ('windowGapsIn', float('nan')),
      ('windowGapsEnabled', 'true'), ('windowGapsLinked', 1), ('windowGapsOut', {'top': 8}),
      ('windowGapsOut', dict(top=8, right=8, bottom=8, left='8; exit()')),
      ('windowGapsOut', dict(top=8, right=8, bottom=8, left=129))]:
      with self.subTest(key=key, value=value), self.assertRaises(ValueError):
        validate_setting(key, value)

  def test_default_disabled_mode_does_not_change_the_compositor(self):
    with patch('backend.service.command') as command:
      self.assertTrue(self.service.window_gaps.sync())
    command.assert_not_called()
    self.assertIn('enabled=0', self.service.window_gaps.path.read_text())

  def test_gap_preferences_persist_undo_redo_and_reset_with_appearance(self):
    self.enable()
    store = self.service.store
    self.assertEqual(Store(store.directory).settings['windowGapsOut']['left'], 40)
    store.undo()
    self.assertFalse(store.settings['windowGapsEnabled'])
    store.redo()
    before = copy.deepcopy(store.settings)
    store.update(section_updates('Appearance', DEFAULTS, store.settings))
    self.assertFalse(store.settings['windowGapsEnabled'])
    self.assertEqual(store.settings['windowGapsOut']['left'], 8)
    store.undo()
    self.assertEqual(store.settings, before)

  def test_apply_writes_private_data_and_changes_only_the_gap_options(self):
    self.enable()
    with patch('backend.service.command', return_value='ok') as command:
      self.assertTrue(self.service.window_gaps.sync())
    command.assert_called_once_with(['hyprctl', 'eval', expression(self.service.store.settings)], timeout=3)
    self.assertEqual(self.service.window_gaps.path.read_text(), render(self.service.store.settings))
    self.assertEqual(stat.S_IMODE(self.service.window_gaps.path.stat().st_mode), 0o600)
    self.assertNotIn('border_size', command.call_args.args[0][2])

  def test_disabling_writes_disabled_data_before_reloading_original_configuration(self):
    self.enable()
    with patch('backend.service.command', return_value='ok'):
      self.service.window_gaps.sync()
    self.service.store.update({'windowGapsEnabled': False})
    def reload(argv, **options):
      self.assertEqual(argv, ['hyprctl', 'reload'])
      self.assertIn('enabled=0', self.service.window_gaps.path.read_text())
      return 'ok'
    with patch('backend.service.command', side_effect=reload) as command:
      self.assertTrue(self.service.window_gaps.sync())
      self.service.window_gaps.sync()
    command.assert_called_once()

  def test_preview_and_standalone_startup_only_write_data(self):
    self.enable()
    with patch('backend.service.command') as command:
      self.service.preview = True
      self.service.window_gaps.sync()
      self.service.preview = False
      self.service.settings_only = True
      self.service.window_gaps.sync(native=False)
    command.assert_not_called()
    self.assertIn('enabled=1', self.service.window_gaps.path.read_text())

  def test_apply_failure_reports_error_and_keeps_saved_preferences_for_retry(self):
    self.enable()
    original = copy.deepcopy(self.service.store.settings)
    with patch('backend.service.command', side_effect=RuntimeError('socket unavailable')):
      self.assertFalse(self.service.window_gaps.sync())
    self.assertEqual(self.service.store.settings, original)
    self.assertEqual(self.events[-1][1]['error'], 'socket unavailable')
    with patch('backend.service.command', return_value='ok'):
      self.assertTrue(self.service.window_gaps.sync())
    self.assertEqual(self.events[-1][1]['error'], '')

  def test_manual_retry_requires_the_focused_settings_window(self):
    with patch.object(self.service.window_gaps, 'sync') as sync:
      self.service.action({'action': 'apply-window-gaps', 'source': 'shell'})
      sync.assert_not_called()
      self.service.configuration_focused = True
      sync.return_value = True
      self.service.action({'action': 'apply-window-gaps', 'source': 'config'})
      sync.assert_called_once()


@unittest.skipUnless(shutil.which('Hyprland'), 'Native Hyprland Lua verifier is optional')
class NativeWindowGapTests(unittest.TestCase):
  def test_installed_spacing_wins_after_loading_the_base_look(self):
    with tempfile.TemporaryDirectory(prefix='hyprlarp-gap-install-') as temporary:
      folder = Path(temporary)
      prefix = folder / 'prefix'
      config = prefix / 'config/hyprlarp'
      Store(config).update({'windowGapsEnabled': True, 'windowGapsIn': 6,
        'windowGapsOut': {'top': 10, 'right': 20, 'bottom': 30, 'left': 40}})
      import sys
      subprocess.run([sys.executable, str(ROOT / 'tools/install.py'), '--prefix', str(prefix)], check=True, capture_output=True, timeout=15)
      script = folder / 'verify.lua'
      script.write_text('dofile(' + lua_string(str(config / 'bindings-prelude.lua')) + ')\n'
        + 'dofile(' + lua_string(str(config / 'hyprlarp.lua')) + ')\n'
        + 'dofile(' + lua_string(str(prefix / 'share/hyprlarp/config/hyprland-look.lua')) + ')\n'
        + 'local out=hl.get_config("general.gaps_out")\nassert(out.top==10 and out.right==20 and out.bottom==30 and out.left==40)\n'
        + 'assert(hl.get_config("general.gaps_in").top==6)\n')
      result = subprocess.run(['Hyprland', '--verify-config', '--config', str(script)], capture_output=True, text=True, timeout=10)
      self.assertEqual(result.returncode, 0, result.stdout[-1800:] + result.stderr[-1500:])

  def verify(self, content, assertions):
    with tempfile.TemporaryDirectory(prefix='hyprlarp-gaps-') as temporary:
      root = Path(temporary)
      data = root / 'window gaps # % ñ.conf'
      data.write_text(content)
      lua = root / 'verify.lua'
      lua.write_text('local loader=dofile(' + lua_string(str(ROOT / 'config/window-gaps-loader.lua')) + ')\n'
        + 'hl.config({general={gaps_in=2,gaps_out=3}})\nlocal valid=loader(' + lua_string(str(data)) + ')\n' + assertions)
      result = subprocess.run(['Hyprland', '--verify-config', '--config', str(lua)], capture_output=True, text=True, timeout=10)
      self.assertEqual(result.returncode, 0, result.stdout[-1600:] + result.stderr[-1500:])
      self.assertIn('config ok', result.stdout)

  def test_data_loader_applies_all_four_edges_and_inner_gaps(self):
    settings = copy.deepcopy(DEFAULTS)
    settings.update({'windowGapsEnabled': True, 'windowGapsIn': 6,
      'windowGapsOut': {'top': 10, 'right': 20, 'bottom': 30, 'left': 40}})
    self.verify(render(settings), '''assert(valid)
local out=hl.get_config("general.gaps_out")
assert(out.top==10 and out.right==20 and out.bottom==30 and out.left==40)
assert(hl.get_config("general.gaps_in").top==6)
''')

  def test_disabled_data_keeps_existing_configuration(self):
    self.verify(render(DEFAULTS), 'assert(valid)\nassert(hl.get_config("general.gaps_out").top==3)\n')

  def test_invalid_or_executable_data_is_ignored(self):
    for content in ['enabled=1\ninner=4\ntop=129\nright=8\nbottom=8\nleft=8\n',
      'enabled=1\ninner=4\ntop=8\nright=8\nbottom=8\nleft=8\nleft=9\n',
      'error("This data must not execute")', 'x' * 1025]:
      with self.subTest(content=content[:60]):
        self.verify(content, 'assert(not valid)\nassert(hl.get_config("general.gaps_out").top==3)\n')
