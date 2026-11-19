"""Regression checks for session-scoped control and safe live replacement."""

import contextlib
from dataclasses import replace
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from backend import recovery, supervisor
from backend.service import DEFAULTS, ROOT

sys.path.insert(0, str(ROOT / 'tools'))
from deployment import Locations
from install import install


class SessionControlTests(unittest.TestCase):
  def test_recovery_request_never_signals_another_verified_wayland_session(self):
    with tempfile.TemporaryDirectory(prefix='hyprlarp-session-control-') as temporary:
      folder = Path(temporary)
      root = folder / 'app'
      root.mkdir()
      environment = {**os.environ, 'XDG_RUNTIME_DIR': str(folder), 'HYPRLAND_INSTANCE_SIGNATURE': 'session-a'}
      child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'],
        env={**environment, 'HYPRLARP_SUPERVISOR': '1'}, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
      try:
        value = {'pid': child.pid, 'identity': supervisor.identity(child.pid), 'root': str(root.resolve()), 'signature': 'session-b'}
        other = supervisor.state_path(root, {**environment, 'HYPRLAND_INSTANCE_SIGNATURE': 'session-b'})
        other.write_text(json.dumps(value))
        with patch.object(recovery, 'current_session', return_value=environment), patch.object(supervisor.os, 'kill') as kill:
          with self.assertRaisesRegex(RuntimeError, 'supervisor'):
            supervisor.request(root, 'recovery', environment=environment)
          kill.assert_not_called()
          # A stale/misplaced state record must not bypass the signature check.
          own = supervisor.state_path(root, environment)
          own.write_text(json.dumps(value))
          with self.assertRaises(RuntimeError):
            supervisor.request(root, 'normal', environment=environment)
          kill.assert_not_called()
        self.assertIsNone(child.poll())
      finally:
        child.terminate()
        child.wait(timeout=5)

  def test_stop_refuses_to_finish_while_the_recovery_renderer_is_alive(self):
    def running(root, entrypoint='shell.qml'):
      return [321] if entrypoint == 'recovery.qml' else []
    with patch.object(recovery, 'service_running', return_value=False), \
        patch.object(recovery, 'running_pids', side_effect=running), \
        patch.object(recovery, 'run') as run, patch.object(recovery.time, 'sleep') as sleep, \
        patch.object(recovery.time, 'monotonic', side_effect=[0, 0, 13]):
      with self.assertRaisesRegex(RuntimeError, 'instancia anterior'):
        recovery.stop(ROOT, 'quickshell')
      run.assert_called_once_with(['quickshell', 'kill', '--path', str(ROOT / 'recovery.qml')], check=False)
      sleep.assert_called_once_with(.1)

  def test_live_install_stops_and_restarts_a_shell_in_recovery_mode(self):
    with tempfile.TemporaryDirectory(prefix='hyprlarp-live-recovery-install-') as temporary:
      isolated = Locations.create(Path(temporary) / 'prefix')
      with contextlib.redirect_stdout(io.StringIO()):
        install(isolated)
      locations = replace(isolated, prefix='')
      sentinel = locations.app / 'previous-version'
      sentinel.write_text('running recovery version')
      # Model a real owned file removed in the next release, rather than a
      # foreign file which a code update must now preserve.
      from deployment import MARKER, digest
      marker = locations.app / MARKER
      manifest = json.loads(marker.read_text())
      manifest['prefix'] = ''
      manifest['files']['previous-version'] = digest(sentinel)
      marker.write_text(json.dumps(manifest))

      def stopped_before_replacement(*args, **options):
        self.assertTrue(sentinel.is_file())

      with patch.dict(os.environ, {}, clear=False), \
          patch('install.shutil.which', return_value='/usr/bin/quickshell'), \
          patch.object(recovery, 'service_running', return_value=False), \
          patch.object(recovery, 'running_pids', side_effect=lambda root, entrypoint='shell.qml': [321] if entrypoint == 'recovery.qml' else []), \
          patch.object(recovery, 'current_session', return_value={**os.environ, 'HYPRLAND_INSTANCE_SIGNATURE': 'isolated-fixture'}), \
          patch.object(recovery, 'stop', side_effect=stopped_before_replacement) as stop, \
          patch.object(recovery, 'start') as start, contextlib.redirect_stdout(io.StringIO()):
        install(locations)
      stop.assert_called_once()
      start.assert_called_once()
      self.assertFalse(sentinel.exists())
      self.assertTrue(any(locations.app.parent.glob('hyprlarp.backup-*')))


class ReadinessStateTests(unittest.TestCase):
  def test_visible_bar_and_registered_target_require_a_connected_backend(self):
    state = {'ready': True, 'connected': False, 'backendPid': 100}

    def run(args, **options):
      if args[-1] == 'health':
        output = json.dumps(state)
      elif 'ipc' in args:
        output = 'target shell\n'
      elif 'monitors' in args:
        output = json.dumps([{'name': 'eDP-1'}])
      else:
        output = json.dumps([{'namespace': 'hyprlarp-bar', 'w': 1200, 'h': 40, 'alpha': 1}])
      return subprocess.CompletedProcess(args, 0, output, '')

    with patch.object(recovery, 'running_pids', return_value=[99]), patch.object(recovery, 'run', side_effect=run):
      self.assertFalse(recovery.healthy(ROOT, 'quickshell', settings=DEFAULTS))
      state['connected'] = True
      self.assertTrue(recovery.healthy(ROOT, 'quickshell', settings=DEFAULTS))
      state['backendPid'] = 0
      self.assertFalse(recovery.healthy(ROOT, 'quickshell', settings=DEFAULTS))
      state.update(backendPid=100, ready=False)
      self.assertFalse(recovery.healthy(ROOT, 'quickshell', settings=DEFAULTS))

  @unittest.skipUnless(shutil.which('quickshell') or shutil.which('qs'), 'Quickshell is required for the real IPC regression')
  def test_real_registered_ipc_with_disconnected_backend_is_not_ready(self):
    with tempfile.TemporaryDirectory(prefix='hyprlarp-readiness-ipc-') as temporary:
      folder = Path(temporary)
      (folder / 'shell.qml').write_text('''import Quickshell
import Quickshell.Io
ShellRoot {
  IpcHandler {
    target: "shell"
    function health(): string { return JSON.stringify({ready: true, connected: false, backendPid: 100}); }
  }
}
''')
      binary = shutil.which('quickshell') or shutil.which('qs')
      environment = {**os.environ, 'QT_QPA_PLATFORM': 'offscreen', 'QT_QUICK_BACKEND': 'software', 'XDG_RUNTIME_DIR': temporary}
      environment.pop('WAYLAND_DISPLAY', None)
      with (folder / 'log').open('w') as log:
        child = subprocess.Popen([binary, '--path', str(folder / 'shell.qml'), '--no-color'], env=environment, stdout=log, stderr=subprocess.STDOUT)
      try:
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
          registered = subprocess.run([binary, '--path', str(folder / 'shell.qml'), 'ipc', 'show'], env=environment, capture_output=True, text=True, timeout=3)
          if registered.returncode == 0 and 'target shell' in registered.stdout:
            break
          time.sleep(.03)
        self.assertEqual(registered.returncode, 0, (folder / 'log').read_text())
        self.assertIn('target shell', registered.stdout)

        def run(args, **options):
          if args[0] == 'hyprctl':
            output = json.dumps([{'name': 'eDP-1'}]) if 'monitors' in args else json.dumps([{'namespace': 'hyprlarp-bar', 'w': 1200, 'h': 40, 'alpha': 1}])
            return subprocess.CompletedProcess(args, 0, output, '')
          return subprocess.run(args, env=environment, capture_output=True, text=True, timeout=3)

        with patch.object(recovery, 'running_pids', return_value=[child.pid]), patch.object(recovery, 'run', side_effect=run):
          self.assertFalse(recovery.healthy(folder, binary, settings=DEFAULTS))
      finally:
        child.terminate()
        child.wait(timeout=5)
