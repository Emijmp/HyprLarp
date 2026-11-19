import copy
from datetime import datetime
import json
import os
import shutil
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from backend.metrics import poll_intervals
from backend.performance import MIB, PAGE, TICKS, Performance, ProcessSampler, package_revision
from backend.service import DEFAULTS, ROOT, Service, Store


def process(folder, pid, *, ticks=100, start=1000, rss=256, parent=1, threads=2, pss=512):
  target = folder / str(pid)
  target.mkdir(exist_ok=True)
  fields = ['0'] * 30
  for index, value in {0: 'S', 1: parent, 11: ticks, 12: 0, 13: 100000, 14: 100000, 17: threads, 19: start, 21: rss}.items():
    fields[index] = str(value)
  (target / 'stat').write_text(str(pid) + ' (name ) with spaces) ' + ' '.join(fields))
  (target / 'smaps_rollup').write_text('Rss: 1000 kB\nPss: ' + str(pss) + ' kB\n')


class Clock:
  def __init__(self): self.now = 0
  def __call__(self): return self.now


class Sampler:
  def __init__(self, clock):
    self.clock, self.previous, self.calls, self.targets = clock, None, 0, {}
  def reset(self): self.previous = None
  def sample(self):
    self.calls += 1
    elapsed = self.clock() - self.previous if self.previous is not None else 0
    self.previous = self.clock()
    return {'time': self.clock(), 'cpuPercent': 25 if elapsed else None,
      'rssMiB': 100 + self.calls, 'pssMiB': 80, 'pssAgeSeconds': 0, 'processes': 3,
      'threads': 15, 'parts': [], '_elapsed': elapsed, '_cpuSeconds': elapsed * .25 if elapsed else None}


class ProcessMeasurementsTests(unittest.TestCase):
  def test_public_cli_reaches_the_performance_panel(self):
    with tempfile.TemporaryDirectory() as directory:
      folder = Path(directory)
      marker, executable = folder / 'arguments.json', folder / 'quickshell-test'
      executable.write_text('#!/usr/bin/python3\nimport json,sys\nfrom pathlib import Path\nPath(' + repr(str(marker)) + ').write_text(json.dumps(sys.argv[1:]))\n')
      executable.chmod(0o755)
      result = subprocess.run([str(ROOT / 'bin/hyprlarp'), 'toggle', 'performance'],
        env={**os.environ, 'HYPRLARP_QUICKSHELL': str(executable)}, capture_output=True, text=True)
      self.assertEqual(result.returncode, 0, result.stderr)
      self.assertEqual(json.loads(marker.read_text())[-4:], ['call', 'shell', 'toggle', 'performance'])

  def test_cpu_identity_shared_memory_and_unrelated_apps(self):
    with tempfile.TemporaryDirectory() as directory:
      proc, clock = Path(directory), Clock()
      process(proc, 10, ticks=100, rss=256, pss=512)
      process(proc, 11, ticks=100, parent=10, pss=256)
      process(proc, 12, ticks=9999999, parent=10, rss=99999)
      sampler = ProcessSampler(proc, proc=proc, clock=clock, pids={'interface': 10, 'backend': 11})
      initial = sampler.sample()
      self.assertIsNone(initial['cpuPercent'])
      self.assertEqual(initial['processes'], 2)
      self.assertEqual(initial['pssMiB'], .75)
      clock.now = 2
      process(proc, 10, ticks=100 + TICKS * 5, pss=9999)
      measured = sampler.sample()
      self.assertEqual(measured['cpuPercent'], 250)
      self.assertEqual(measured['pssMiB'], .75, 'PSS is cached for eight seconds')
      self.assertEqual(measured['rssMiB'], round(512 * PAGE / MIB, 2))
      clock.now = 10
      process(proc, 11, start=2000)
      changed = sampler.sample()
      self.assertEqual(changed['processes'], 1, 'PID reuse must not measure the new process')
      self.assertIsNone(changed['cpuPercent'])
      sampler.reset()
      self.assertIsNone(sampler.sample()['cpuPercent'])

  def test_unavailable_pss_is_not_reported_as_zero_or_partial_total(self):
    with tempfile.TemporaryDirectory() as directory:
      proc = Path(directory)
      process(proc, 10)
      (proc / '10/smaps_rollup').unlink()
      sampler = ProcessSampler(proc, proc=proc, pids={'interface': 10})
      self.assertIsNone(sampler.sample()['pssMiB'])

  def test_package_fingerprint_changes_with_code_but_not_docs_or_measurements(self):
    with tempfile.TemporaryDirectory() as directory:
      root = Path(directory)
      (root / 'backend').mkdir()
      source = root / 'backend/service.py'
      source.write_text('first')
      first = package_revision(root)
      (root / '.runtime').mkdir()
      (root / '.runtime/measurement.json').write_text('{}')
      (root / 'docs').mkdir()
      (root / 'docs/note.md').write_text('changed')
      self.assertEqual(first, package_revision(root))
      source.write_text('second')
      self.assertNotEqual(first, package_revision(root))


class PerformanceHistoryTests(unittest.TestCase):
  def setUp(self):
    temporary = tempfile.TemporaryDirectory()
    self.addCleanup(temporary.cleanup)
    self.directory = Path(temporary.name)
    self.clock = Clock()
    self.sampler = Sampler(self.clock)
    self.performance = Performance(ROOT, self.directory, clock=self.clock, sampler=self.sampler)
    self.performance.revision = '0123456789ab'
    self.performance.set_screens([{'name': 'eDP-1', 'width': 1536, 'height': 864}])
    self.settings = copy.deepcopy(DEFAULTS)

  def record(self, label='Before'):
    self.performance.set_open(True)
    self.performance.begin_recording(label, 5, self.settings)
    for _ in range(3):
      self.clock.now += 2
      self.performance.sample(self.settings)

  def test_recording_uses_actual_elapsed_time_and_preserves_settings(self):
    before = copy.deepcopy(self.settings)
    self.record()
    report = self.performance.history[0]
    self.assertEqual(report['summary']['seconds'], 6)
    self.assertEqual(report['summary']['samples'], 3)
    self.assertEqual(report['summary']['cpuPercent'], 25)
    self.assertEqual(self.settings, before)
    self.assertEqual(self.performance.history_path.stat().st_mode & 0o777, 0o600)
    restored = Performance(ROOT, self.directory)
    self.assertEqual(restored.history[0], report)

  def test_peak_rss_includes_the_initial_measurement_sample(self):
    sample = self.sampler.sample
    def initial_memory_peak():
      value = sample()
      value['rssMiB'] = 1000 if self.sampler.calls == 1 else 100
      return value
    with patch.object(self.sampler, 'sample', side_effect=initial_memory_peak):
      self.record()
    self.assertEqual(self.performance.history[0]['summary']['peakRssMiB'], 1000)
    self.assertEqual(self.performance.history[0]['summary']['rssMiB'], 100)

  def test_automatic_theme_change_cancels_a_mixed_context_measurement(self):
    self.settings.update(themeScheduleEnabled=True, themeDay='paper', themeNight='amoled',
      themeDayStart='07:00', themeNightStart='19:00')
    with patch('backend.theme_context.datetime') as clock:
      clock.now.return_value = datetime(2026, 11, 18, 18, 59)
      self.performance.set_open(True)
      self.performance.begin_recording('Across sunset', 5, self.settings)
      clock.now.return_value = datetime(2026, 11, 18, 19, 0)
      self.clock.now += 2
      self.performance.sample(self.settings)
    self.assertIsNone(self.performance.recording)
    self.assertFalse(self.performance.history)
    self.assertIn('cambió', self.performance.error)

  def test_queued_periodic_reads_are_dropped_after_demand_disappears(self):
    store = Store(self.directory)
    store.update({'barEnabled': False, 'batteryAlertsEnabled': False, 'clipboardEnabled': False})
    service = Service(store, native_services=True)
    self.addCleanup(service.executor.shutdown, wait=True)
    service.active_panel = 'resources'
    queued = {}
    with patch.object(service, 'queue_refresh', side_effect=lambda name, function: queued.setdefault(name, function)), \
        patch.object(service.wakeup, 'wait', side_effect=lambda timeout: service.stopping.set()), \
        patch.object(service, 'refresh_system') as reader:
      service.poll()
      self.assertIn('metrics', queued)
      service.stopping.clear()
      reader.reset_mock()
      service.active_panel = ''
      queued['metrics']()
      reader.assert_not_called()
      service.active_panel = 'resources'
      queued['metrics']()
      reader.assert_called_once_with(metrics=True)

  def test_closing_cancels_recording_and_stops_all_process_reads(self):
    self.performance.set_open(True)
    self.performance.begin_recording('Cancel', 5, self.settings)
    self.performance.set_open(False)
    calls = self.sampler.calls
    self.clock.now += 10
    self.performance.sample(self.settings)
    self.assertEqual(self.sampler.calls, calls)
    self.assertIsNone(self.performance.recording)
    self.assertFalse(self.performance.history_path.exists())
    self.performance.set_open(True)
    self.assertFalse(self.performance.samples)
    self.assertIsNone(self.performance.current)

  def test_changed_configuration_cannot_produce_a_mixed_measurement(self):
    self.performance.set_open(True)
    self.performance.begin_recording('Cancel', 5, self.settings)
    self.settings['font'] = 'Sans'
    self.clock.now += 2
    self.performance.sample(self.settings)
    self.assertIsNone(self.performance.recording)
    self.assertFalse(self.performance.history)

  def test_history_is_bounded_and_a_failed_write_does_not_delete_previous_reports(self):
    for index in range(22): self.record(str(index))
    self.assertEqual(len(self.performance.history), 20)
    self.assertEqual(self.performance.history[0]['label'], '2')
    before = self.performance.history_path.read_bytes()
    with patch('backend.performance.atomic_json', side_effect=OSError('full')):
      self.record('cannot save')
    self.assertEqual(self.performance.history_path.read_bytes(), before)
    self.assertEqual(len(self.performance.history), 20)
    self.assertTrue(self.performance.error)

  def test_invalid_data_is_rejected_without_starting_or_writing(self):
    self.performance.set_open(True)
    for seconds in [True, 0, 121, float('nan'), '15']:
      with self.subTest(seconds=seconds), self.assertRaises(ValueError):
        self.performance.begin_recording('test', seconds, self.settings)
    with self.assertRaises(ValueError):
      self.performance.set_screens([{'name': 'eDP', 'width': True, 'height': 100}])
    self.performance.history_path.write_text('[{"type":"invalid"}]')
    self.assertEqual(Performance(ROOT, self.directory).history, [])

  def test_consumption_thresholds_are_validated_and_saved_separately(self):
    self.performance.set_open(True)
    self.performance.handle('performance-thresholds', {'cpuPercent': 125.5, 'rssMiB': 768}, self.settings)
    self.assertEqual(self.performance.snapshot()['thresholds'], {'cpuPercent': 125.5, 'rssMiB': 768.0})
    restored = Performance(ROOT, self.directory)
    self.assertEqual(restored.thresholds, {'cpuPercent': 125.5, 'rssMiB': 768.0})
    for values in [{'cpuPercent': True, 'rssMiB': 768}, {'cpuPercent': 10, 'rssMiB': 1}]:
      with self.subTest(values=values), self.assertRaises(ValueError):
        restored.set_thresholds(values)
    self.assertEqual(restored.preferences_path.stat().st_mode & 0o777, 0o600)

  def test_pause_and_context_requests_are_validated(self):
    self.performance.handle('performance-context', {'screens': []}, self.settings)
    self.performance.set_open(True)
    self.performance.handle('performance-pause', {'paused': True}, self.settings)
    self.assertTrue(self.performance.paused)
    with self.assertRaises(ValueError): self.performance.begin_recording('blocked', 5, self.settings)
    self.performance.handle('performance-pause', {'paused': False}, self.settings)
    self.assertFalse(self.performance.paused)
    self.assertIsNone(self.sampler.previous)

  def test_startup_is_a_real_acknowledgment_and_survives_backend_reconnection(self):
    self.sampler.targets = {'interface': {'pid': 4000, 'start': TICKS * 1000}}
    with patch('backend.performance.time.clock_gettime', return_value=1001.234):
      self.performance.mark_ready()
    self.assertEqual(self.performance.startup['readyMs'], 1234)
    restored = Performance(ROOT, self.directory, sampler=self.sampler)
    with patch('backend.performance.time.clock_gettime', return_value=1010):
      restored.mark_ready()
    self.assertEqual(restored.startup['readyMs'], 1234)

  def test_independent_settings_do_not_overwrite_the_native_startup(self):
    self.sampler.targets = {'interface': {'pid': 4000, 'start': TICKS * 1000}}
    with patch('backend.performance.time.clock_gettime', return_value=1001.234):
      self.performance.mark_ready()
    other = Sampler(self.clock)
    other.targets = {'interface': {'pid': 4001, 'start': TICKS * 1000}}
    settings = Performance(ROOT, self.directory, settings_only=True, sampler=other)
    with patch('backend.performance.time.clock_gettime', return_value=1002):
      settings.mark_ready()
    restored = Performance(ROOT, self.directory, sampler=self.sampler)
    with patch('backend.performance.time.clock_gettime', return_value=1010):
      restored.mark_ready()
    self.assertEqual(restored.startup['readyMs'], 1234)

  def test_sampling_is_scheduled_only_for_the_visible_panel(self):
    settings = {**DEFAULTS, 'barModules': ['performance'], 'batteryAlertsEnabled': False}
    self.assertNotIn('performance', poll_intervals(settings, ''))
    self.assertEqual(poll_intervals(settings, 'performance')['performance'], 2)
    self.assertEqual(poll_intervals(settings, 'performance', settings_only=True), {'performance': 2})

  def test_performance_profiles_adjust_only_background_poll_rates(self):
    balanced = poll_intervals({**DEFAULTS, 'barModules': ['resources'], 'batteryAlertsEnabled': True}, '')
    efficient = poll_intervals({**DEFAULTS, 'barModules': ['resources'], 'batteryAlertsEnabled': True, 'performanceMode': 'efficient'}, '')
    responsive = poll_intervals({**DEFAULTS, 'barModules': ['resources'], 'batteryAlertsEnabled': True, 'performanceMode': 'responsive'}, '')
    self.assertEqual(efficient['metrics'], balanced['metrics'] * 2.5)
    self.assertEqual(efficient['battery'], balanced['battery'] * 2.5)
    self.assertEqual(responsive['metrics'], balanced['metrics'] * .75)
    self.assertEqual(poll_intervals({**DEFAULTS, 'performanceMode': 'efficient'}, 'performance')['performance'], 2)

  def test_service_routes_and_fault_isolation_are_connected(self):
    service = Service(Store(self.directory), preview=True)
    events = []
    service.emit = lambda kind, data: events.append((kind, data))
    try:
      service.action({'action': 'panel', 'data': {'name': 'performance'}})
      self.assertTrue(service.performance.open)
      self.assertIn('backend:performance', service.faults.allowed)
      service.action({'action': 'performance-pause', 'data': {'paused': True}})
      self.assertTrue(service.performance.paused)
      self.assertTrue(any(kind == 'performance' for kind, _ in events))
      service.action({'action': 'panel', 'data': {'name': ''}})
      self.assertFalse(service.performance.open)
    finally:
      service.executor.shutdown(wait=True)

  @unittest.skipUnless(shutil.which('node'), 'Node unavailable')
  def test_javascript_comparison_handles_context_and_missing_measurements(self):
    result = subprocess.run(['node', str(ROOT / 'tests/test_performance.js')], capture_output=True, text=True)
    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


@unittest.skipUnless(shutil.which('quickshell'), 'Quickshell unavailable')
class PerformanceInterfaceTests(unittest.TestCase):
  def test_live_pause_record_and_comparison_with_the_actual_backend(self):
    with tempfile.TemporaryDirectory(prefix='h-performance-') as temporary:
      folder = Path(temporary)
      environment = {**os.environ, 'XDG_RUNTIME_DIR': temporary, 'HYPRLARP_STATE_DIR': str(folder / 'settings'),
        'HYPRLARP_PREVIEW': '1', 'QT_QPA_PLATFORM': 'offscreen', 'QT_QUICK_BACKEND': 'software'}
      environment.pop('WAYLAND_DISPLAY', None)
      for key in ['HYPRLARP_PERFORMANCE_HOLD', 'HYPRLARP_PERFORMANCE_CAPTURE', 'HYPRLARP_SETTINGS_ONLY']:
        environment.pop(key, None)
      result = subprocess.run(['quickshell', '--path', str(ROOT / 'performance-check.qml'), '--no-color'],
        env=environment, capture_output=True, text=True, timeout=25)
      output = result.stdout + result.stderr
      self.assertEqual(result.returncode, 0, output)
      self.assertIn('PERFORMANCE COMPLETE', output)
      self.assertFalse(any(message in output for message in ['TypeError:', 'ReferenceError:', 'Failed to load', 'Binding loop']))
      history = json.loads((folder / 'settings/performance-history.json').read_text())
      self.assertEqual(len(history), 2)
      self.assertEqual(history[0]['context']['fingerprint'], history[1]['context']['fingerprint'])
      self.assertGreaterEqual(history[0]['summary']['seconds'], 5)
