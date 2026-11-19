import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from backend import recovery
from backend.service import DEFAULTS, ROOT


class RecoveryTests(unittest.TestCase):
  def test_ipc_error_containing_shell_is_never_considered_healthy(self):
    result = subprocess.CompletedProcess([], 0, 'ERROR quickshell.ipc: shell not found\n', '')
    with patch.object(recovery, 'running_pids', return_value=[123]), patch.object(recovery, 'run', return_value=result):
      self.assertFalse(recovery.healthy(ROOT, 'quickshell'))
    result.stdout = 'target shellUnavailable\n'
    with patch.object(recovery, 'running_pids', return_value=[123]), patch.object(recovery, 'run', return_value=result):
      self.assertFalse(recovery.healthy(ROOT, 'quickshell'))

  def test_ready_requires_live_process_and_visible_bar(self):
    def run(args, **options):
      output = (json.dumps({'ready': True, 'connected': True, 'backendPid': 456}) if args[-1] == 'health'
        else 'target shell\n' if 'ipc' in args else json.dumps([{'name': 'eDP-1'}]) if 'monitors' in args else json.dumps(layers))
      return subprocess.CompletedProcess(args, 0, output, '')
    layers = {'eDP-1': {'levels': [{'namespace': 'hyprlarp-bar', 'w': 48, 'h': 864, 'alpha': 1}]}}
    with patch.object(recovery, 'running_pids', return_value=[123]), patch.object(recovery, 'run', side_effect=run):
      self.assertTrue(recovery.healthy(ROOT, 'quickshell', settings=DEFAULTS))
      layers['eDP-1']['levels'][0]['alpha'] = 0
      self.assertFalse(recovery.healthy(ROOT, 'quickshell', settings=DEFAULTS))
      self.assertTrue(recovery.healthy(ROOT, 'quickshell', settings={**DEFAULTS, 'barEnabled': False}))
    with patch.object(recovery, 'running_pids', return_value=[]):
      self.assertFalse(recovery.healthy(ROOT, 'quickshell', settings=DEFAULTS))

  def test_disconnected_monitor_settings_do_not_require_a_bar(self):
    settings = copy.deepcopy(DEFAULTS)
    settings.update(barEnabled=False, monitorBars={'HDMI-A-1': {'barEnabled': True}})
    self.assertFalse(recovery.expects_bar(settings, [{'name': 'eDP-1'}]))
    self.assertTrue(recovery.expects_bar(settings, [{'name': 'eDP-1'}, {'name': 'HDMI-A-1'}]))

  def test_startup_checks_must_be_consecutively_healthy(self):
    with patch.object(recovery, 'session_alive', return_value=True), \
        patch.object(recovery, 'healthy', side_effect=[True, False, True, True, True]) as healthy, \
        patch.object(recovery.time, 'sleep'):
      recovery.wait_ready(ROOT, 'quickshell')
    self.assertEqual(healthy.call_count, 5)

  def test_readiness_timeout_is_an_error(self):
    with patch.object(recovery.time, 'monotonic', side_effect=[0, 1, 25]), \
        patch.object(recovery, 'session_alive', return_value=False), patch.object(recovery.time, 'sleep'):
      with self.assertRaises(RuntimeError):
        recovery.wait_ready(ROOT, 'quickshell', timeout=20)

  def test_stale_session_does_not_restart_on_another_compositor(self):
    with patch.dict(os.environ, {'HYPRLAND_INSTANCE_SIGNATURE': 'old'}), \
        patch.object(recovery, 'current_session', return_value={'HYPRLAND_INSTANCE_SIGNATURE': 'new'}):
      self.assertFalse(recovery.session_alive())
    with patch.object(recovery, 'current_session', side_effect=RuntimeError('session closed')):
      self.assertFalse(recovery.session_alive())

  def test_old_process_must_exit_before_starting_a_new_instance(self):
    normal = iter([[7], [7], [], []])
    with patch.object(recovery, 'service_running', return_value=False), \
        patch.object(recovery, 'running_pids', side_effect=lambda root, entrypoint='shell.qml': next(normal) if entrypoint == 'shell.qml' else []), \
        patch.object(recovery, 'run') as run, patch.object(recovery.time, 'sleep') as sleep:
      recovery.stop(ROOT, 'quickshell')
      self.assertEqual(run.call_args.args[0], ['quickshell', 'kill', '--path', str(ROOT / 'shell.qml')])
      sleep.assert_called_once()

  def test_unit_limits_recovery_and_keeps_independent_apps_alive(self):
    unit = recovery.render_unit(Path('/home/test/.local/bin/hyprlarp'), ROOT)
    self.assertIn('Restart=on-failure', unit)
    self.assertIn('StartLimitBurst=3', unit)
    self.assertIn('ExecCondition=', unit)
    self.assertIn('ExecStartPost=', unit)
    self.assertIn('KillMode=process', unit)
    self.assertNotIn('WantedBy=default.target', unit)

  def test_unit_argument_escaping_is_not_shell_quoting(self):
    value = recovery.systemd_word('/tmp/space $dollar `tick` "quote" %percent/bin/hyprlarp')
    self.assertIn('$$dollar', value)
    self.assertIn('%%percent', value)
    self.assertIn('\\"quote\\"', value)
    with self.assertRaises(ValueError):
      recovery.systemd_word('/tmp/new\nline')

  def test_preview_and_rendering_overrides_are_not_copied_to_service_environment(self):
    self.assertTrue({'WAYLAND_DISPLAY', 'HYPRLAND_INSTANCE_SIGNATURE'} <= recovery.ENVIRONMENT)
    self.assertTrue({'HYPRLARP_PREVIEW', 'HYPRLARP_SETTINGS_ONLY', 'QT_QUICK_BACKEND', 'GREETD_SOCK'}.isdisjoint(recovery.ENVIRONMENT))

  def test_modified_or_uninstalled_service_is_not_started(self):
    with tempfile.TemporaryDirectory() as temporary:
      path = Path(temporary) / recovery.UNIT
      path.write_text('[Service]\nExecStart=/bin/false\n')
      with patch.object(recovery, 'run') as run:
        with self.assertRaises(RuntimeError):
          recovery.start(ROOT, ROOT / 'bin/hyprlarp', 'quickshell', destination=path)
        run.assert_not_called()
