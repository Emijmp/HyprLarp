import json
import os
from pathlib import Path
import signal
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from backend.faults import FaultRegistry
from backend.supervisor import FailureWindow, identity, request, state_path
from backend.service import Service, Store, ROOT
from backend import recovery


class FaultTests(unittest.TestCase):
  def setUp(self):
    temporary = tempfile.TemporaryDirectory(prefix='hyprlarp-faults-')
    self.addCleanup(temporary.cleanup)
    self.directory = Path(temporary.name)
    self.now = 1000
    self.allowed = {'panel:wifi', 'bar:clock', 'backend:metrics'}
    self.registry = FaultRegistry(self.directory, self.allowed, clock=lambda: self.now)

  def test_three_recent_failures_quarantine_only_the_affected_component(self):
    for count in range(3):
      self.registry.report('panel:wifi', 'Loader failed')
      self.assertEqual(self.registry.blocked('panel:wifi'), count == 2)
    self.assertFalse(self.registry.blocked('bar:clock'))
    restored = FaultRegistry(self.directory, self.allowed, clock=lambda: self.now)
    self.assertTrue(restored.blocked('panel:wifi'))
    restored.reset('panel:wifi')
    self.assertFalse(restored.blocked('panel:wifi'))

  def test_expired_failures_do_not_trigger_quarantine_and_messages_are_redacted(self):
    self.registry.report('panel:wifi', str(Path.home()) + ' password=private')
    self.now += 301
    self.registry.report('panel:wifi', 'error')
    self.registry.report('panel:wifi', 'error')
    self.assertFalse(self.registry.blocked('panel:wifi'))
    self.assertNotIn('private', self.registry.path.read_text())
    self.assertLessEqual(len(self.registry.snapshot()[0]['events']), 3)

  def test_bad_scope_and_corrupt_persistence_preserve_user_settings(self):
    settings = self.directory / 'settings.json'
    settings.write_text('{"user":"preserve"}')
    with self.assertRaises(ValueError): self.registry.report('bar:unknown', 'error')
    self.registry.path.write_text('broken')
    restored = FaultRegistry(self.directory, self.allowed)
    self.assertEqual(restored.snapshot(), [])
    self.assertEqual(settings.read_text(), '{"user":"preserve"}')

  def test_expected_operational_errors_never_quarantine_a_module(self):
    service = Service(Store(self.directory), preview=True)
    service.emit = lambda *args: None
    try:
      def unavailable(): raise RuntimeError('Device disconnected')
      for _ in range(4): service.safe_refresh(unavailable, 'backend:metrics')
      self.assertFalse(service.faults.blocked('backend:metrics'))
      def broken(): raise AttributeError('Broken component')
      for _ in range(3): service.safe_refresh(broken, 'backend:metrics')
      self.assertTrue(service.faults.blocked('backend:metrics'))
      self.assertFalse(service.queue_refresh('metrics', lambda: None))
    finally:
      service.executor.shutdown(wait=True)

  def test_unexpected_action_errors_release_busy_state_and_preserve_other_panels(self):
    service = Service(Store(self.directory), preview=True)
    service.active_panel = 'wifi'
    events = []
    service.emit = lambda kind, data: events.append((kind, data))
    try:
      with patch.object(service.system_actions, 'handle', side_effect=AttributeError('bug')):
        for _ in range(3): service.action({'action': 'fixture', 'data': {}})
      self.assertTrue(service.faults.blocked('panel:wifi'))
      self.assertFalse(service.faults.blocked('panel:audio'))
      self.assertEqual(sum(kind == 'idle' for kind, _ in events), 3)
    finally:
      service.executor.shutdown(wait=True)


class SupervisorTests(unittest.TestCase):
  def test_failure_window_prunes_old_failures(self):
    policy = FailureWindow()
    self.assertFalse(policy.failed(100))
    self.assertFalse(policy.failed(101))
    self.assertFalse(policy.failed(500))
    self.assertFalse(policy.failed(501))
    self.assertTrue(policy.failed(502))

  def test_recovery_health_requires_its_own_visible_bar(self):
    def run(args, **kwargs):
      output = 'target recovery\n' if 'ipc' in args else json.dumps([{'name': 'eDP-1'}]) if 'monitors' in args else json.dumps([{'namespace': namespace, 'w': 100, 'h': 40, 'alpha': 1}])
      return subprocess.CompletedProcess(args, 0, output, '')
    with patch.object(recovery, 'running_pids', side_effect=lambda root, entrypoint='shell.qml': [3] if entrypoint == 'recovery.qml' else []), patch.object(recovery, 'run', side_effect=run):
      namespace = 'hyprlarp-bar'
      self.assertFalse(recovery.healthy(ROOT, 'quickshell'))
      namespace = 'hyprlarp-recovery'
      self.assertTrue(recovery.healthy(ROOT, 'quickshell'))

  def test_real_supervisor_falls_back_retries_and_keeps_independent_apps_alive(self):
    with tempfile.TemporaryDirectory(prefix='hyprlarp-supervisor-') as temporary:
      folder = Path(temporary)
      root = folder / 'app'
      root.mkdir()
      runtime = folder / 'runtime'
      runtime.mkdir(mode=0o700)
      trace = folder / 'trace.jsonl'
      renderer = folder / 'renderer'
      renderer.write_text('#!' + sys.executable + '\n'
        'import json,os,pathlib,signal,subprocess,sys,time\n'
        'root=pathlib.Path(' + repr(str(root)) + ')\n'
        'entry=pathlib.Path(sys.argv[sys.argv.index("--path")+1]).name\n'
        'with open(' + repr(str(trace)) + ',"a") as f:f.write(json.dumps({"entry":entry,"pid":os.getpid()})+"\\n")\n'
        'if entry=="shell.qml" and not (root/"fixed").exists():sys.exit(9)\n'
        'if entry=="recovery.qml":\n'
        ' child=subprocess.Popen(["sleep","60"],start_new_session=True)\n'
        ' (root/"independent").write_text(str(child.pid))\n'
        'signal.signal(signal.SIGTERM,signal.SIG_IGN)\n'
        'while True:time.sleep(1)\n')
      renderer.chmod(0o755)
      environment = {**os.environ, 'XDG_RUNTIME_DIR': str(runtime), 'HYPRLAND_INSTANCE_SIGNATURE': 'fixture', 'HYPRLARP_SUPERVISOR': '1'}
      for key in ['WAYLAND_DISPLAY', 'DISPLAY']: environment.pop(key, None)
      script = ('from backend.supervisor import supervise\nfrom pathlib import Path\nimport sys\ncounts={}\n'
        'def ready(child,mode):\n counts[child.pid]=counts.get(child.pid,0)+1\n'
        ' if counts[child.pid]>=3: (Path(sys.argv[1])/"ready").write_text(str(child.pid))\n return True\n'
        'sys.exit(supervise(sys.argv[1],sys.argv[2],readiness=ready,shutdown_timeout=.1))')
      process = subprocess.Popen([sys.executable, '-c', script, str(root), str(renderer)], env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
      independent = None
      try:
        state = state_path(root, environment)
        def wait_mode(mode):
          deadline = time.monotonic() + 12
          while time.monotonic() < deadline:
            if process.poll() is not None: self.fail(process.stderr.read())
            try:
              value = json.loads(state.read_text())
              last = json.loads(trace.read_text().splitlines()[-1]) if trace.exists() else {}
              ready_pid = int((root / 'ready').read_text()) if (root / 'ready').exists() else None
              if value['mode'] == mode and last.get('entry') == ('recovery.qml' if mode == 'recovery' else 'shell.qml') and last.get('pid') == ready_pid:
                return value
            except (OSError, ValueError): pass
            time.sleep(.05)
          self.fail('Supervisor did not enter ' + mode)
        wait_mode('recovery')
        deadline = time.monotonic() + 3
        while not (root / 'independent').exists() and time.monotonic() < deadline: time.sleep(.05)
        independent = int((root / 'independent').read_text())
        entries = [json.loads(line)['entry'] for line in trace.read_text().splitlines()]
        self.assertEqual(entries, ['shell.qml'] * 3 + ['recovery.qml'])
        (root / 'fixed').touch()
        request(root, 'normal', environment=environment)
        wait_mode('normal')
        os.kill(independent, 0)
        process.terminate()
        self.assertEqual(process.wait(timeout=5), 0)
        os.kill(independent, 0)
        self.assertFalse(state.exists())
      finally:
        if process.poll() is None:
          process.terminate()
          try: process.wait(timeout=5)
          except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=3)
        process.stderr.close()
        if independent:
          try: os.kill(independent, signal.SIGTERM)
          except ProcessLookupError: pass


@unittest.skipUnless(shutil.which('quickshell'), 'Quickshell unavailable')
class LoaderIsolationTests(unittest.TestCase):
  def test_actual_qml_error_is_quarantined_and_another_component_stays_usable(self):
    with tempfile.TemporaryDirectory(prefix='h-fuse-') as temporary:
      folder = Path(temporary)
      bad = folder / 'bad.qml'
      bad.write_text('import QtQuick\nItem { invalid syntax ! }\n')
      good = folder / 'good.qml'
      good.write_text('import QtQuick\nItem { implicitWidth: 20; implicitHeight: 20 }\n')
      configuration = ROOT / 'resilience-check.qml'
      env = {**os.environ, 'XDG_RUNTIME_DIR': temporary, 'HYPRLARP_STATE_DIR': str(folder / 'settings'),
        'HYPRLARP_PREVIEW': '1', 'QT_QPA_PLATFORM': 'offscreen', 'QT_QUICK_BACKEND': 'software',
        'HYPRLARP_TEST_BROKEN_COMPONENT': bad.as_uri(), 'HYPRLARP_TEST_GOOD_COMPONENT': good.as_uri()}
      env.pop('WAYLAND_DISPLAY', None)
      with (folder / 'log').open('w') as output:
        process = subprocess.Popen(['quickshell', '--path', str(configuration)], env=env, stdout=output, stderr=subprocess.STDOUT)
        def ipc(method):
          result = subprocess.run(['quickshell', '--path', str(configuration), 'ipc', 'call', 'resilienceTest', method],
            env=env, capture_output=True, text=True, timeout=3)
          if result.returncode: raise RuntimeError(result.stderr + result.stdout)
          return result.stdout.strip()
        def wait(predicate):
          deadline = time.monotonic() + 8
          while time.monotonic() < deadline:
            try:
              value = json.loads(ipc('status'))
              if predicate(value): return value
            except (RuntimeError, ValueError): pass
            if process.poll() is not None: self.fail((folder / 'log').read_text())
            time.sleep(.05)
          self.fail((folder / 'log').read_text())
        try:
          first = wait(lambda state: state['ready'] and state['faults'])
          self.assertTrue(first['goodReady'])
          for count in [2, 3]:
            ipc('retry')
            result = wait(lambda state: len(state['faults'][0]['events']) == count)
            self.assertTrue(result['goodReady'])
          self.assertTrue(result['blocked'])
          self.assertIsNone(process.poll())
          ipc('fix')
          repaired = wait(lambda state: not state['blocked'] and state['badStatus'] == 1)
          self.assertTrue(repaired['goodReady'])
          ipc('quit')
          self.assertEqual(process.wait(timeout=4), 0)
        finally:
          if process.poll() is None:
            process.terminate()
            try: process.wait(timeout=4)
            except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=3)
