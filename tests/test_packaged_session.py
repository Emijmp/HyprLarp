"""System-package setup owns user integration, never the immutable payload."""

import contextlib
import copy
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

from backend.service import DEFAULTS
from tools import session_setup as api
from tools.deployment import Locations, MARKER, digest


class PackagedSessionTests(unittest.TestCase):
  def setUp(self):
    self.temporary = tempfile.TemporaryDirectory(prefix='hyprlarp-packaged-session-')
    self.addCleanup(self.temporary.cleanup)
    self.base = Path(self.temporary.name)
    self.root = self.base / 'system/usr/share/hyprlarp'
    self.root.mkdir(parents=True)
    (self.root / 'VERSION').write_text('0.1.0\n')
    (self.root / 'immutable.txt').write_text('package-owned code\n')
    self.metadata()
    self.prefix = self.base / 'user'
    self.locations = Locations.create(self.prefix)
    self.targets = {**self.locations.managed(), 'settings': self.locations.config / 'settings.json'}
    self.marker = self.locations.config / api.SESSION_MARKER

  def metadata(self):
    document = {'type': 'hyprlarp-package', 'version': 1,
      'release': (self.root / 'VERSION').read_text().strip(),
      'files': {name: digest(self.root / name) for name in ['VERSION', 'immutable.txt']}}
    (self.root / api.PACKAGE_MARKER).write_text(json.dumps(document))

  def setup(self, **options):
    with contextlib.redirect_stdout(io.StringIO()):
      return api.setup(self.root, prefix=self.prefix, **options)

  def teardown(self, **options):
    with contextlib.redirect_stdout(io.StringIO()):
      return api.teardown(self.root, prefix=self.prefix, **options)

  @staticmethod
  def state(paths):
    return {path: (path.read_bytes(), stat.S_IMODE(path.stat().st_mode), path.stat().st_ino)
      for path in paths if path.is_file()}

  def assert_unchanged(self, before):
    for path, expected in before.items():
      with self.subTest(path=path):
        self.assertEqual(self.state([path])[path], expected)

  def legacy(self):
    # Import through the same public module used by the source installer.
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
    from install import install
    with contextlib.redirect_stdout(io.StringIO()):
      install(self.locations)
    return json.loads((self.locations.app / MARKER).read_text())

  def test_fresh_setup_writes_only_user_integration_and_offers_first_run(self):
    immutable = self.state(self.root.iterdir())
    document = self.setup()
    self.assertTrue(document['first_run'])
    self.assertTrue(api.ready(self.root, prefix=self.prefix))
    self.assertFalse(self.locations.app.exists())
    self.assertFalse(self.locations.executable.exists())
    self.assertEqual(json.loads(self.targets['settings'].read_text()), DEFAULTS)
    self.assertIn(str(self.root), self.targets['prelude'].read_text())
    self.assertIn(str(self.root.parents[1] / 'bin/hyprlarp'), self.targets['service'].read_text())
    self.assertEqual(self.marker.stat().st_mode & 0o777, 0o600)
    self.assert_unchanged(immutable)

  def test_repeated_setup_is_idempotent_including_file_inodes(self):
    self.setup()
    before = self.state([*self.targets.values(), self.marker])
    self.setup()
    self.assert_unchanged(before)

  def test_existing_settings_and_active_files_preserve_bytes_mode_and_inode(self):
    self.locations.config.mkdir(parents=True)
    settings = copy.deepcopy(DEFAULTS)
    settings['shortcuts']['lock'] = 'SUPER SHIFT, L'
    self.targets['settings'].write_text(json.dumps(settings, indent=4) + '\n\n')
    for role in ['bindings', 'gaps', 'idle']:
      self.targets[role].write_text('personal active ' + role + '\n')
      self.targets[role].chmod(0o640)
    history = self.locations.config / 'settings-history.json'
    history.write_text('private history\n')
    before = self.state([self.targets[role] for role in api.ACTIVE] + [history])
    document = self.setup()
    self.assertFalse(document['first_run'])
    self.assertFalse(api.ACTIVE & set(document['owned']))
    self.assert_unchanged(before)

  def test_user_configuration_is_not_copied_into_the_global_package(self):
    for path in self.root.iterdir():
      path.chmod(0o444)
    self.root.chmod(0o555)
    before = self.state(self.root.iterdir())
    self.setup()
    self.teardown()
    self.assert_unchanged(before)

  def test_dry_run_creates_no_user_directories_or_locks(self):
    document = self.setup(dry_run=True)
    self.assertTrue(document['first_run'])
    self.assertFalse(self.prefix.exists())
    self.teardown(dry_run=True)
    self.assertFalse(self.prefix.exists())

  def test_prefix_operations_never_control_systemd_or_the_compositor(self):
    with patch.object(api.recovery, 'run', side_effect=AssertionError('No systemd expected')), \
        patch.object(api.recovery, 'running_pids', side_effect=AssertionError('No compositor expected')), \
        patch.object(api.recovery, 'stop', side_effect=AssertionError('No native runtime expected')):
      self.setup()
      self.teardown()

  def test_native_detach_only_stops_the_packaged_binding_manager(self):
    native = Locations(self.locations.app, self.locations.config, self.locations.executable,
      self.locations.data, '')
    with patch.object(api.recovery, 'current_session', return_value={'HYPRLAND_INSTANCE_SIGNATURE': 'verified-session'}), \
        patch.object(api.recovery, 'run') as run, patch.object(api, 'idle_processes') as idle:
      api._detach_runtime(self.root, native)
    arguments = run.call_args.args[0]
    self.assertEqual(arguments[:4], ['hyprctl', '--instance', 'verified-session', 'eval'])
    self.assertIn(str(self.root / 'config/bindings-runtime.lua'), arguments[4])
    self.assertIn('HyprLarpBinds.runtimePath ==', arguments[4])
    idle.assert_not_called()

  def test_detach_without_a_verified_session_never_targets_another_compositor(self):
    native = Locations(self.locations.app, self.locations.config, self.locations.executable,
      self.locations.data, '')
    with patch.object(api.recovery, 'current_session', side_effect=RuntimeError('no session')), \
        patch.object(api.recovery, 'run') as run:
      api._detach_runtime(self.root, native)
    run.assert_not_called()

  def test_upgrade_keeps_pending_preferences_and_updates_only_owned_integrations(self):
    self.setup()
    settings = json.loads(self.targets['settings'].read_text())
    settings['shortcuts']['lock'] = 'SUPER SHIFT, L'
    self.targets['settings'].write_text(json.dumps(settings, indent=4))
    before = self.state([self.targets[role] for role in api.ACTIVE])
    (self.root / 'VERSION').write_text('0.2.0\n')
    self.metadata()
    self.assertFalse(api.ready(self.root, prefix=self.prefix))
    render = api.contents
    def candidate(*args, **options):
      result = render(*args, **options)
      result['service'] += b'# updated package unit\n'
      return result
    with patch.object(api, 'contents', side_effect=candidate):
      self.setup()
    self.assert_unchanged(before)
    self.assertEqual(json.loads(self.marker.read_text())['release'], '0.2.0')
    self.assertIn('# updated package unit', self.targets['service'].read_text())
    self.assertIn('SUPER, L', self.targets['bindings'].read_text())

  def test_foreign_integrations_and_shadowing_launcher_are_preserved_unowned(self):
    for role in ['prelude', 'session', 'service', 'launcher']:
      target = self.targets[role]
      target.parent.mkdir(parents=True, exist_ok=True)
      target.write_text('personal ' + role)
      target.chmod(0o750)
    before = self.state(self.targets.values())
    document = self.setup()
    self.assertFalse({'prelude', 'session', 'service', 'launcher'} & set(document['owned']))
    self.teardown()
    self.assert_unchanged(before)

  def test_modified_owned_files_and_admin_permission_changes_survive_detachment(self):
    self.setup()
    self.targets['session'].write_text(self.targets['session'].read_text() + '\n-- custom integration\n')
    self.targets['prelude'].chmod(0o640)
    before = self.state([self.targets['session'], self.targets['prelude']])
    self.setup()
    self.teardown()
    self.assert_unchanged(before)
    self.assertFalse(self.marker.exists())

  def test_legacy_migration_preserves_active_files_and_restores_original_integrations(self):
    self.legacy()
    before = self.state([*self.targets.values(), self.locations.app / MARKER])
    document = self.setup()
    for role in api.ACTIVE:
      self.assert_unchanged({self.targets[role]: before[self.targets[role]]})
    self.assertTrue(self.locations.app.is_dir())
    self.assertIn(str(self.root.parents[1] / 'bin/hyprlarp'), self.targets['launcher'].read_text())
    self.assertIn('launcher', document['owned'])
    self.teardown()
    # Restoration is byte/mode exact; an original file restored on detach has
    # a new inode, while untouched active files keep their original inodes.
    for path, (data, mode, inode) in before.items():
      self.assertEqual(path.read_bytes(), data)
      self.assertEqual(path.stat().st_mode & 0o7777, mode)
    for role in api.ACTIVE:
      self.assertEqual(self.targets[role].stat().st_ino, before[self.targets[role]][2])

  def test_first_baseline_survives_multiple_package_updates(self):
    self.legacy()
    originals = {role: self.targets[role].read_bytes() for role in ['prelude', 'session', 'service', 'launcher']}
    first = self.setup()['baseline']
    for release in ['0.2.0', '0.3.0']:
      (self.root / 'VERSION').write_text(release + '\n')
      self.metadata()
      self.assertEqual(self.setup()['baseline'], first)
    self.teardown()
    for role, data in originals.items():
      self.assertEqual(self.targets[role].read_bytes(), data)

  def test_failed_first_write_transaction_removes_all_partial_integration(self):
    write = api.atomic_bytes
    def failure(path, data):
      write(path, data)
      if path == self.marker:
        raise OSError('failed after marker write')
    with patch.object(api, 'atomic_bytes', side_effect=failure):
      with self.assertRaises(OSError):
        self.setup()
    self.assertFalse(any(path.exists() for path in self.targets.values()))
    self.assertFalse(self.marker.exists())
    self.assertFalse(api.ready(self.root, prefix=self.prefix))

  def test_failed_update_restores_old_inodes_and_manifest(self):
    self.setup()
    before = self.state([*self.targets.values(), self.marker])
    render, write = api.contents, api.atomic_bytes
    def candidate(*args, **options):
      result = render(*args, **options)
      result['session'] += b'\n-- candidate\n'
      return result
    def failure(path, data):
      write(path, data)
      if path == self.marker:
        raise OSError('marker failure')
    with patch.object(api, 'contents', side_effect=candidate), patch.object(api, 'atomic_bytes', side_effect=failure):
      with self.assertRaises(OSError):
        self.setup()
    self.assert_unchanged(before)

  def test_failed_native_activation_restores_legacy_runtime_and_configuration(self):
    self.legacy()
    before = self.state(self.targets.values())
    native = Locations(self.locations.app, self.locations.config, self.locations.executable,
      self.locations.data, '')
    # The local fixture's ownership prefix must match its native interpretation.
    legacy_marker = native.app / MARKER
    document = json.loads(legacy_marker.read_text());document['prefix'] = ''
    legacy_marker.write_text(json.dumps(document))
    original_signature = os.environ.get('HYPRLAND_INSTANCE_SIGNATURE')
    with patch.object(api.Locations, 'create', return_value=native), \
        patch.object(api, '_active_root', return_value=native.app), \
        patch.object(api.recovery, 'current_session', return_value={'HYPRLAND_INSTANCE_SIGNATURE': 'fixture'}), \
        patch.object(api.recovery, 'stop') as stop, \
        patch.object(api.recovery, 'run'), \
        patch.object(api.recovery, 'start', side_effect=[RuntimeError('unhealthy'), None]) as start:
      with self.assertRaisesRegex(RuntimeError, 'unhealthy'):
        self.setup()
    self.assert_unchanged(before)
    self.assertFalse(self.marker.exists())
    self.assertEqual(start.call_args_list[0].args[0], self.root)
    self.assertEqual(start.call_args_list[1].args[0], native.app)
    self.assertEqual(stop.call_count, 2)
    self.assertEqual(os.environ.get('HYPRLAND_INSTANCE_SIGNATURE'), original_signature)

  def test_auto_setup_inside_its_own_service_never_stops_itself(self):
    native = Locations(self.locations.app, self.locations.config, self.locations.executable,
      self.locations.data, '')
    with patch.dict(os.environ, {'HYPRLARP_SUPERVISOR': '1'}), \
        patch.object(api.recovery, 'running_pids', return_value=[]), \
        patch.object(api.recovery, 'run', return_value=subprocess.CompletedProcess([], 0, str(os.getpid()), '')), \
        patch.object(api.recovery, 'service_running', side_effect=AssertionError('Do not inspect or stop self unit')):
      self.assertIsNone(api._active_root(self.root, native, 'quickshell'))

  def test_runtime_rollback_can_restart_a_verified_older_unit_template(self):
    self.setup()
    old = api.recovery.render_unit(self.root.parents[1] / 'bin/hyprlarp', self.root)
    self.targets['service'].write_text(old + '# previous version template\n')
    with patch.object(api.recovery, 'run') as run, patch.object(api.recovery, 'start') as start, \
        patch.object(api.recovery, 'wait_ready') as ready:
      api._restore_runtime(self.root, self.locations, 'quickshell', self.root.parents[1] / 'bin/hyprlarp')
    start.assert_not_called()
    ready.assert_called_once_with(self.root, 'quickshell')
    self.assertIn(['systemctl', '--user', 'start', api.recovery.UNIT], [call.args[0] for call in run.call_args_list])
    self.assertEqual(self.targets['service'].read_text(), old + '# previous version template\n')

  def test_stop_failure_does_not_change_configuration_or_session_environment(self):
    self.setup()
    before = self.state([*self.targets.values(), self.marker])
    signature = os.environ.get('HYPRLAND_INSTANCE_SIGNATURE')
    with patch.object(api, '_active_root', return_value=self.root), \
        patch.object(api.recovery, 'current_session', return_value={'HYPRLAND_INSTANCE_SIGNATURE': 'temporary-fixture'}), \
        patch.object(api.recovery, 'stop', side_effect=RuntimeError('still closing')):
      with self.assertRaisesRegex(RuntimeError, 'still closing'):
        self.setup()
    self.assert_unchanged(before)
    self.assertEqual(os.environ.get('HYPRLAND_INSTANCE_SIGNATURE'), signature)

  def test_future_or_traversal_session_state_is_not_overwritten_or_purged(self):
    self.setup()
    original = json.loads(self.marker.read_text())
    for mutation in ['future', 'traversal']:
      document = copy.deepcopy(original)
      if mutation == 'future':
        document['version'] = 2
      else:
        document['owned']['../../sentinel'] = '0' * 64
      content = json.dumps(document)
      self.marker.write_text(content)
      self.assertFalse(api.ready(self.root, prefix=self.prefix))
      with self.assertRaises(ValueError):self.setup()
      with self.assertRaises(ValueError):self.teardown(purge=True)
      self.assertEqual(self.marker.read_text(), content)
      self.assertTrue(self.targets['settings'].is_file())

  def test_symlinks_and_special_files_are_rejected_before_setup(self):
    self.locations.config.mkdir(parents=True)
    unrelated = self.base / 'unrelated'
    unrelated.write_text('do not change')
    self.targets['bindings'].symlink_to(unrelated)
    with self.assertRaises(ValueError):self.setup()
    self.assertEqual(unrelated.read_text(), 'do not change')
    self.assertFalse(self.marker.exists())
    self.targets['bindings'].unlink()
    os.mkfifo(self.targets['bindings'])
    with self.assertRaises(ValueError):self.setup()
    self.assertFalse(self.marker.exists())

  def test_invalid_package_metadata_does_not_create_user_state(self):
    document = json.loads((self.root / api.PACKAGE_MARKER).read_text())
    document['files']['VERSION'] = '0' * 64
    (self.root / api.PACKAGE_MARKER).write_text(json.dumps(document))
    with self.assertRaises(ValueError):self.setup()
    self.assertFalse(self.prefix.exists())

  def test_teardown_keeps_settings_history_and_the_immutable_payload(self):
    self.setup()
    history = self.locations.config / 'settings-history.json'
    history.write_text('personal history')
    before = self.state([self.targets['settings'], history, *self.root.iterdir()])
    self.teardown()
    self.assert_unchanged(before)
    self.assertFalse(self.marker.exists())
    self.assertFalse(any(path.exists() for role, path in self.targets.items() if role in api.ROLES - {'settings'}))

  def test_purge_is_explicit_and_requires_valid_session_ownership(self):
    with self.assertRaises(ValueError):self.teardown(purge=True)
    self.setup()
    self.teardown(purge=True)
    self.assertFalse(self.locations.config.exists())
    self.assertTrue((self.root / api.PACKAGE_MARKER).is_file())
