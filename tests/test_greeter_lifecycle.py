"""Isolated greeter transactions; never invoke sudo, systemd, or live greetd."""

import copy
import io
import json
import os
from pathlib import Path
import shutil
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from tools import install_greeter as installer
from tools.greeter_lifecycle import Snapshot, fingerprint


class GreeterLifecycleTests(unittest.TestCase):
  def setUp(self):
    temporary = tempfile.TemporaryDirectory(prefix='hyprlarp-greeter-lifecycle-')
    self.addCleanup(temporary.cleanup)
    self.root = Path(temporary.name)
    self.username = 'desktop-user'
    self.account = SimpleNamespace(pw_uid=os.getuid(), pw_gid=os.getgid(), pw_name=self.username)
    system = self.root / 'system'
    values = {'GREETD': system / 'etc/greetd/config.toml', 'BACKUPS': system / 'backups',
      'GREETER_UI': system / 'usr/share/hyprlarp-greeter',
      'GREETER_STATE': system / 'var/lib/noctalia-greeter',
      'PREFERENCES': system / 'var/lib/hyprlarp-greeter/preferences/layout.json',
      'SYSTEM_MANIFEST': system / 'var/lib/hyprlarp-greeter/lifecycle.json',
      'POLKIT_RULE': system / 'etc/polkit/rules.d/noctalia.rules',
      'UI_LAUNCHER': system / 'usr/libexec/hyprlarp-greeter-ui',
      'SESSION_LAUNCHER': system / 'usr/bin/hyprlarp-greeter-session',
      'HELPER': system / 'helper'}
    for name, value in values.items():
      self.addCleanup(patch.stopall)
      patch.object(installer, name, value).start()
    installer.GREETD.parent.mkdir(parents=True)
    self.original_greetd = '[terminal]\nvt = 7\n[default_session]\ncommand = "/usr/bin/original-greeter"\nuser = "greeter"\n'
    installer.GREETD.write_text(self.original_greetd)
    installer.GREETER_STATE.mkdir(parents=True)
    (installer.GREETER_STATE / 'greeter.toml').write_text('[appearance]\nscheme = "Original"\n[session]\nlast = "personal"\n')
    installer.POLKIT_RULE.parent.mkdir(parents=True)
    installer.POLKIT_RULE.write_text(json.dumps(['other-user']))
    installer.HELPER.write_text('fixture')
    self.targets = {'app': self.root / 'user/share/hyprlarp-greeter',
      'launcher': self.root / 'user/bin/hyprlarp-greeter',
      'service': self.root / 'user/config/systemd/user/hyprlarp-greeter-sync.service',
      'path': self.root / 'user/config/systemd/user/hyprlarp-greeter-sync.path'}
    self.config = self.root / 'user/config'
    self.state = self.root / 'user/state/hyprlarp-greeter'
    (self.config / 'hyprlarp').mkdir(parents=True)
    (self.config / 'hyprlarp/settings.json').write_text('{}')
    self.units = {suffix: {'enabled': False, 'active': False, 'present': False, 'runtime': False} for suffix in ['path', 'service']}
    self.commands = []
    patch.object(installer, 'identity', return_value=self.account).start()
    patch.object(installer.pwd, 'getpwnam', return_value=self.account).start()
    patch.object(installer.pwd, 'getpwuid', return_value=self.account).start()
    patch.object(installer.os, 'chown').start()
    patch.object(installer, 'run', side_effect=self.run_command).start()
    patch.object(installer, 'unit_state', side_effect=lambda: copy.deepcopy(self.units)).start()
    patch.object(installer, 'user_locations', return_value=(self.targets, self.config, self.state)).start()
    patch.object(installer, 'privileged', side_effect=self.privileged).start()
    patch.object(installer, 'ensure_privileges').start()
    self.output = patch('sys.stdout', new_callable=io.StringIO).start()

  def run_command(self, args, **kwargs):
    self.commands.append(list(map(str, args)))
    if args[:2] == [str(installer.HELPER), '--supports']:
      return 'secure-sync-v1'
    if args[:2] == [str(installer.HELPER), '--setup-system']:
      installer.GREETER_STATE.mkdir(parents=True, exist_ok=True)
      return ''
    if args[:2] == ['/usr/bin/noctalia-greeter', 'passwordless-sync']:
      users = set(json.loads(installer.POLKIT_RULE.read_text())) if installer.POLKIT_RULE.exists() else set()
      action, username = args[2:4]
      if action == 'enable':
        users.add(username)
      elif action == 'disable':
        users.discard(username)
      else:
        return username + (': enabled by the noctalia-greeter managed rule' if username in users else ': disabled')
      installer.POLKIT_RULE.write_text(json.dumps(sorted(users)))
      return ''
    if args[:2] == ['systemctl', '--user']:
      action = args[2]
      if action == 'daemon-reload':
        for suffix in self.units:
          self.units[suffix]['present'] = self.targets[suffix].exists()
        return ''
      suffix = args[-1].split('.')[-1]
      if suffix not in self.units:
        self.fail('Unexpected systemd command: ' + repr(args))
      value = self.units[suffix]
      if action == 'disable':
        value.update(enabled=False, active=False, runtime=False)
      elif action == 'enable':
        value.update(enabled=True, runtime='--runtime' in args)
        if '--now' in args:
          value['active'] = True
      elif action == 'stop':
        value['active'] = False
      elif action == 'start':
        value['active'] = True
      return ''
    if args == [str(self.targets['launcher']), 'status']:
      return '{"status":"synced"}'
    self.fail('Unexpected external command: ' + repr(args))

  def privileged(self, flag, username, token=None, **kwargs):
    actions = {'--system': installer.system_setup, '--system-uninstall': installer.system_uninstall,
      '--system-commit': installer.system_commit, '--system-rollback': installer.system_rollback}
    return actions[flag](username, token) if token else actions[flag](username)

  def activate(self):
    setup = installer.system_setup(self.username)
    installer.system_commit(self.username, setup['transaction'])
    return setup

  def remove(self):
    result = installer.system_uninstall(self.username)
    if result.get('transaction'):
      installer.system_commit(self.username, result['transaction'])
    return result

  def test_fresh_install_completes_without_preexisting_units_and_uninstalls(self):
    result = installer.install_user()
    self.assertEqual(result['status'], 'installed')
    self.assertTrue(self.targets['app'].is_dir())
    self.assertTrue(self.units['path']['enabled'])
    self.assertIn(self.username, json.loads(installer.POLKIT_RULE.read_text()))
    removed = installer.uninstall_user()
    self.assertEqual(removed['status'], 'uninstalled')
    self.assertFalse(self.targets['app'].exists())
    self.assertFalse(self.targets['launcher'].exists())
    self.assertFalse(self.units['path']['enabled'])
    self.assertNotIn(self.username, json.loads(installer.POLKIT_RULE.read_text()))
    self.assertIn('other-user', json.loads(installer.POLKIT_RULE.read_text()))
    self.assertEqual(installer.tomllib.loads(installer.GREETD.read_text()), installer.tomllib.loads(self.original_greetd))

  def test_system_failure_restores_original_greetd_ui_state_and_polkit(self):
    original = installer.GREETD.read_bytes()
    state = (installer.GREETER_STATE / 'greeter.toml').read_bytes()
    policy = installer.POLKIT_RULE.read_bytes()
    with patch.object(installer, 'prepare_preferences', side_effect=RuntimeError('injected preferences failure')):
      with self.assertRaisesRegex(RuntimeError, 'preferences failure'):
        installer.system_setup(self.username)
    self.assertEqual(installer.GREETD.read_bytes(), original)
    self.assertEqual((installer.GREETER_STATE / 'greeter.toml').read_bytes(), state)
    self.assertEqual(installer.POLKIT_RULE.read_bytes(), policy)
    self.assertFalse(installer.GREETER_UI.exists())
    self.assertFalse(installer.SYSTEM_MANIFEST.exists())

  def test_system_failure_after_policy_enable_restores_previous_grants(self):
    original_run = self.run_command
    old_policy = installer.POLKIT_RULE.read_bytes()
    statuses = 0
    def failing(args, **kwargs):
      nonlocal statuses
      if args[:3] == ['/usr/bin/noctalia-greeter', 'passwordless-sync', 'status']:
        statuses += 1
        if statuses == 2:
          raise RuntimeError('injected status after enable')
      return original_run(args, **kwargs)
    with patch.object(installer, 'run', side_effect=failing), self.assertRaisesRegex(RuntimeError, 'after enable'):
      installer.system_setup(self.username)
    self.assertEqual(installer.POLKIT_RULE.read_bytes(), old_policy)
    self.assertFalse(installer.SYSTEM_MANIFEST.exists())
    self.assertEqual(installer.GREETD.read_text(), self.original_greetd)

  def test_pending_operation_can_recover_before_new_install_without_losing_original_baseline(self):
    first = installer.system_setup(self.username)
    second = installer.system_setup(self.username)
    self.assertNotEqual(first['transaction'], second['transaction'])
    installer.system_commit(self.username, second['transaction'])
    self.remove()
    self.assertEqual(installer.GREETD.read_text(), self.original_greetd)

  def test_user_activation_failure_after_sync_restores_system_and_user_files(self):
    original_run = self.run_command
    original = installer.GREETD.read_bytes()
    def failing(args, **kwargs):
      if args == [str(self.targets['launcher']), 'status']:
        # Initial sync legitimately changes dynamic state before a later failure.
        (installer.GREETER_STATE / 'sync.toml').write_text('[appearance]\nfont_family="Changed by our sync"\n')
        installer.PREFERENCES.write_text('{"layout":"centered"}')
        raise RuntimeError('injected status failure')
      return original_run(args, **kwargs)
    with patch.object(installer, 'run', side_effect=failing), self.assertRaisesRegex(RuntimeError, 'status failure'):
      installer.install_user()
    self.assertEqual(installer.GREETD.read_bytes(), original)
    self.assertFalse(installer.GREETER_UI.exists())
    self.assertFalse((installer.GREETER_STATE / 'sync.toml').exists())
    self.assertFalse(self.targets['app'].exists())
    self.assertFalse(self.units['path']['enabled'])
    self.assertNotIn(self.username, json.loads(installer.POLKIT_RULE.read_text()))

  def test_update_keeps_first_baseline_and_does_not_adopt_unknown_files(self):
    self.activate()
    first = json.loads(installer.SYSTEM_MANIFEST.read_text())['baseline']
    unknown = installer.GREETER_UI / 'admin-notes.txt'
    unknown.write_text('must survive update and uninstall')
    state_unknown = installer.GREETER_STATE / 'admin-state.json'
    state_unknown.write_text('must survive')
    self.activate()
    self.assertEqual(json.loads(installer.SYSTEM_MANIFEST.read_text())['baseline'], first)
    self.remove()
    self.assertEqual(unknown.read_text(), 'must survive update and uninstall')
    self.assertEqual(state_unknown.read_text(), 'must survive')

  def test_reinstall_after_uninstall_takes_new_baseline(self):
    self.activate()
    first = json.loads(installer.SYSTEM_MANIFEST.read_text())['baseline']
    self.remove()
    installer.GREETD.write_text(self.original_greetd.replace('vt = 7', 'vt = 9'))
    self.activate()
    self.assertNotEqual(json.loads(installer.SYSTEM_MANIFEST.read_text())['baseline'], first)
    self.remove()
    self.assertEqual(installer.tomllib.loads(installer.GREETD.read_text())['terminal']['vt'], 9)

  def test_uninstall_preserves_admin_fields_of_default_session_and_other_sections(self):
    self.activate()
    current = installer.tomllib.loads(installer.GREETD.read_text())
    current['default_session'].update(user='administrator-choice', custom='keep')
    current['terminal']['vt'] = 11
    installer.GREETD.write_text(installer.dump_toml(current))
    self.remove()
    actual = installer.tomllib.loads(installer.GREETD.read_text())
    self.assertEqual(actual['default_session']['command'], '/usr/bin/original-greeter')
    self.assertEqual(actual['default_session']['user'], 'administrator-choice')
    self.assertEqual(actual['default_session']['custom'], 'keep')
    self.assertEqual(actual['terminal']['vt'], 11)

  def test_original_config_bytes_restore_and_later_admin_permissions_survive(self):
    installer.GREETD.write_text('# Original comments must return\n' + self.original_greetd)
    before = installer.GREETD.read_bytes()
    self.activate()
    self.remove()
    self.assertEqual(installer.GREETD.read_bytes(), before)
    self.activate()
    installer.GREETD.chmod(0o600)
    self.remove()
    self.assertEqual(installer.GREETD.stat().st_mode & 0o777, 0o600)

  def test_update_preserves_admin_default_session_fields_and_rejects_another_greeter(self):
    self.activate()
    current = installer.tomllib.loads(installer.GREETD.read_text())
    current['default_session'].update(user='administrator-choice', custom='keep')
    installer.GREETD.write_text(installer.dump_toml(current))
    self.activate()
    self.assertEqual(installer.tomllib.loads(installer.GREETD.read_text())['default_session'], current['default_session'])
    current['default_session']['command'] = '/usr/bin/admin-greeter'
    installer.GREETD.write_text(installer.dump_toml(current))
    before = installer.GREETD.read_bytes()
    with self.assertRaisesRegex(ValueError, 'administrador'):
      self.activate()
    self.assertEqual(installer.GREETD.read_bytes(), before)

  def test_uninstall_refuses_custom_command_still_using_our_launcher(self):
    self.activate()
    current = installer.tomllib.loads(installer.GREETD.read_text())
    current['default_session']['command'] = str(installer.SESSION_LAUNCHER) + ' --personal-option'
    installer.GREETD.write_text(installer.dump_toml(current))
    with self.assertRaisesRegex(ValueError, 'personalizado'):
      self.remove()
    self.assertTrue(installer.GREETER_UI.is_dir())
    self.assertTrue(installer.SESSION_LAUNCHER.is_file())

  def test_missing_privileges_leave_files_and_unit_flags_unchanged(self):
    installer.install_user()
    before = self.targets['app'].joinpath('installation.json').read_bytes()
    flags = copy.deepcopy(self.units)
    with patch.object(installer, 'ensure_privileges', side_effect=RuntimeError('sudo credentials required')):
      with self.assertRaisesRegex(RuntimeError, 'credentials required'):
        installer.uninstall_user()
    self.assertEqual(self.units, flags)
    self.assertEqual(before, self.targets['app'].joinpath('installation.json').read_bytes())

  def test_update_rejects_modified_owned_ui_without_losing_changes(self):
    self.activate()
    ui = installer.GREETER_UI / 'greeter/shell.qml'
    ui.write_text('administrator edit')
    with self.assertRaisesRegex(ValueError, 'modificado'):
      installer.system_setup(self.username)
    self.assertEqual(ui.read_text(), 'administrator edit')

  def test_update_rejects_modified_user_bridge_without_applying_system_update(self):
    installer.install_user()
    script = self.targets['app'] / 'backend/greeter.py'
    script.write_text('personal bridge edit')
    manifest = installer.SYSTEM_MANIFEST.read_bytes()
    with self.assertRaisesRegex(ValueError, 'modificado'):
      installer.install_user()
    self.assertEqual(script.read_text(), 'personal bridge edit')
    self.assertEqual(installer.SYSTEM_MANIFEST.read_bytes(), manifest)

  def test_completed_and_stale_rollbacks_cannot_overwrite_later_admin_changes(self):
    setup = self.activate()
    installer.GREETD.write_text('administrator change')
    with self.assertRaisesRegex(ValueError, 'pendiente'):
      installer.system_rollback(self.username, setup['transaction'])
    self.assertEqual(installer.GREETD.read_text(), 'administrator change')

  def test_pending_rollback_refuses_later_static_admin_change(self):
    setup = installer.system_setup(self.username)
    installer.GREETD.write_text('administrator change')
    with self.assertRaisesRegex(ValueError, 'posteriores'):
      installer.system_rollback(self.username, setup['transaction'])
    self.assertEqual(installer.GREETD.read_text(), 'administrator change')

  def test_broken_output_after_commit_cannot_undo_successful_install_or_removal(self):
    normal = print
    def broken(*values, **kwargs):
      if any(isinstance(value, str) and value.startswith('{') and ('"installed"' in value or '"uninstalled"' in value) for value in values):
        raise BrokenPipeError('closed output')
      return normal(*values, **kwargs)
    with patch('builtins.print', side_effect=broken), self.assertRaises(BrokenPipeError):
      installer.install_user()
    self.assertTrue(self.targets['app'].is_dir())
    self.assertTrue(json.loads(installer.SYSTEM_MANIFEST.read_text())['installed'])
    self.assertFalse(json.loads(installer.SYSTEM_MANIFEST.read_text())['pending'])
    with patch('builtins.print', side_effect=broken), self.assertRaises(BrokenPipeError):
      installer.uninstall_user()
    self.assertFalse(self.targets['app'].exists())
    self.assertFalse(json.loads(installer.SYSTEM_MANIFEST.read_text())['installed'])
    self.assertFalse(json.loads(installer.SYSTEM_MANIFEST.read_text())['pending'])

  def test_dry_run_uninstall_does_not_write_or_require_privileges(self):
    installer.install_user()
    before = self.targets['app'].joinpath('installation.json').read_bytes()
    with patch.object(installer, 'privileged', side_effect=AssertionError('must not elevate')):
      report = installer.uninstall_user(dry_run=True)
    self.assertEqual(report['status'], 'dry-run')
    self.assertEqual(before, self.targets['app'].joinpath('installation.json').read_bytes())
    self.assertTrue(self.units['path']['enabled'])

  def test_legacy_adoption_uses_earliest_original_backup_and_preserves_unknown_files(self):
    backup = installer.BACKUPS / '20260101-120000-000001'
    backup.mkdir(parents=True)
    (backup / 'greetd.toml').write_text(self.original_greetd)
    shutil.copytree(installer.GREETER_STATE, backup / 'state')
    installer.GREETD.write_text(installer.dump_toml({'terminal': {'vt': 7}, 'default_session': {
      'command': str(installer.SESSION_LAUNCHER), 'user': 'greeter'}}))
    installer.GREETER_UI.mkdir(parents=True)
    for name in installer.UI_FILES:
      destination = installer.GREETER_UI / name
      destination.parent.mkdir(parents=True, exist_ok=True)
      shutil.copy2(installer.ROOT / name, destination)
    foreign = installer.GREETER_UI / 'admin-extra.txt'
    foreign.write_text('keep')
    modified = installer.GREETER_UI / 'greeter/shell.qml'
    modified.write_text('keep changed known UI')
    result = self.remove()
    self.assertTrue(result['legacy_authorization_preserved'])
    self.assertEqual(foreign.read_text(), 'keep')
    self.assertEqual(modified.read_text(), 'keep changed known UI')
    self.assertEqual(installer.tomllib.loads(installer.GREETD.read_text())['default_session']['command'], '/usr/bin/original-greeter')

  def test_legacy_without_valid_original_backup_refuses_changes(self):
    installer.GREETD.write_text(installer.dump_toml({'default_session': {
      'command': str(installer.SESSION_LAUNCHER), 'user': 'greeter'}}))
    before = installer.GREETD.read_bytes()
    with self.assertRaisesRegex(ValueError, 'copia anterior'):
      installer.system_setup(self.username)
    self.assertEqual(installer.GREETD.read_bytes(), before)
    self.assertFalse(installer.SYSTEM_MANIFEST.exists())


class SnapshotOwnershipTests(unittest.TestCase):
  def test_file_replaced_by_directory_and_changed_permissions_are_preserved(self):
    with tempfile.TemporaryDirectory() as temporary:
      root = Path(temporary)
      target = root / 'managed'
      target.mkdir()
      target.chmod(0o750)
      (target / 'a').write_text('before')
      original = Snapshot.capture(root / 'baseline', {'app': target})
      (target / 'a').write_text('installed')
      target.chmod(0o700)
      owned = Snapshot.capture(root / 'owned', {'app': target})
      (target / 'a').unlink()
      (target / 'a').mkdir()
      (target / 'a/private').write_text('keep')
      target.chmod(0o755)
      report = original.restore_owned(owned)
      self.assertEqual((target / 'a/private').read_text(), 'keep')
      self.assertEqual(target.stat().st_mode & 0o777, 0o755)
      self.assertIn(str(target / 'a'), report['preserved'])

  def test_deleted_unowned_baseline_file_is_never_resurrected(self):
    with tempfile.TemporaryDirectory() as temporary:
      root = Path(temporary)
      target = root / 'managed'
      target.mkdir()
      (target / 'ours').write_text('original')
      (target / 'foreign').write_text('administrator file')
      (target / 'foreign-empty-directory').mkdir()
      original = Snapshot.capture(root / 'baseline', {'app': target})
      (target / 'ours').write_text('installed')
      owned = Snapshot.capture(root / 'owned', {'app': target})
      owned.records['app']['entries'].pop('foreign')
      owned.records['app']['entries'].pop('foreign-empty-directory')
      (target / 'foreign').unlink()
      (target / 'foreign-empty-directory').rmdir()
      original.restore_owned(owned)
      self.assertEqual((target / 'ours').read_text(), 'original')
      self.assertFalse((target / 'foreign').exists())
      self.assertFalse((target / 'foreign-empty-directory').exists())

  def test_symbolic_snapshot_paths_cannot_touch_outside_files(self):
    with tempfile.TemporaryDirectory() as temporary:
      root = Path(temporary)
      outside = root / 'outside'
      outside.write_text('keep')
      symlink = root / 'managed'
      symlink.symlink_to(outside)
      with self.assertRaises(ValueError):
        Snapshot.capture(root / 'snapshot', {'app': symlink})
      self.assertEqual(outside.read_text(), 'keep')


if __name__ == '__main__':
  unittest.main()
