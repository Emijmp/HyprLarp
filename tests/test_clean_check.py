"""Clean-root orchestration cannot silently fall back to the host system."""

import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from tools import clean_check as api


class CleanCheckTests(unittest.TestCase):
  def test_rootfs_rejects_host_root_home_and_overlapping_results(self):
    for root in [Path('/'), Path.home(), api.ROOT.parent]:
      with self.subTest(root=root), self.assertRaises(ValueError):
        api.validate_rootfs(root, Path('/tmp/clean-check-results'))
    with tempfile.TemporaryDirectory() as folder:
      root = Path(folder)
      with self.assertRaises(ValueError):
        api.validate_rootfs(root, root / 'results')

  def test_container_mode_requires_an_explicit_identified_root_container(self):
    with patch.object(api.os, 'geteuid', return_value=1000):
      self.assertFalse(api.container_allowed())
    with patch.object(api.os, 'geteuid', return_value=0), patch.object(Path, 'is_file', return_value=False):
      self.assertFalse(api.container_allowed())
    with patch.object(api, 'container_allowed', return_value=False), self.assertRaises(ValueError):
      api.check('/tmp/no-package', '/tmp/no-output', container=True)

  def test_user_namespace_uses_readonly_root_private_home_and_no_network(self):
    with patch.object(api.shutil, 'which', return_value='/usr/bin/bwrap'):
      args = api.bubble_command(Path('/private/rootfs'), Path('/private/app.pkg.tar.zst'),
        Path('/private/home'), 'verify', uid=1000, release='0.1.0')
    self.assertIn('--unshare-all', args)
    self.assertNotIn('--share-net', args)
    self.assertIn('--clearenv', args)
    mount = args.index('/private/rootfs')
    self.assertEqual(args[mount - 1:mount + 2], ['--ro-bind', '/private/rootfs', '/'])
    self.assertNotIn('/dev/dri', args)
    self.assertNotIn('/run/user/1000', args)
    self.assertIn('/home/qa', args)
    env = api.environment(Path('/home/qa'), uid=1000)
    for key in ['DBUS_SESSION_BUS_ADDRESS', 'WAYLAND_DISPLAY', 'HYPRLAND_INSTANCE_SIGNATURE', 'GH_TOKEN']:
      self.assertNotIn(key, env)
    self.assertEqual(env['XDG_CONFIG_HOME'], '/home/qa/.config')

  def test_phase_results_reject_ambiguity_missing_payload_and_errors(self):
    success = api.RESULT_PREFIX + json.dumps({'ok': True, 'result': {'installed': True}})
    self.assertEqual(api.phase_result('other output\n' + success), {'installed': True})
    for value in ['', success + '\n' + success, api.RESULT_PREFIX + '[]',
        api.RESULT_PREFIX + '{"ok":true}', api.RESULT_PREFIX + '{"ok":false,"error":"failed"}']:
      with self.subTest(value=value), self.assertRaises(RuntimeError):
        api.phase_result(value)

  def test_phase_timeout_keeps_partial_logs_for_diagnosis(self):
    with tempfile.TemporaryDirectory() as folder:
      output = Path(folder)
      with patch.object(api.subprocess, 'run', side_effect=subprocess.TimeoutExpired(['fixture'], 30, output=b'partial log\n')):
        with self.assertRaisesRegex(RuntimeError, 'límite'):
          api.run_phase(['fixture'], output, 'verify', timeout=30)
      self.assertEqual((output / 'verify.log').read_text(), 'partial log\n')

  def test_missing_rootfs_never_invokes_package_management(self):
    with patch.object(api.subprocess, 'run') as run, self.assertRaises(ValueError):
      api.check('/tmp/no-package', '/tmp/no-output')
    run.assert_not_called()
