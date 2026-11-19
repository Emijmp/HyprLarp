"""Small daily-use preferences, warnings and greeter keyboard metadata."""

from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from backend.battery_alerts import BatteryAlerts
from backend.service import DEFAULTS, Service, Store, validate_setting
from backend.layouts import section_updates
from backend.metrics import poll_intervals
from greeter.model import keyboard_layout, keyboard_status


class DailyTests(unittest.TestCase):
  def setUp(self):
    temporary = tempfile.TemporaryDirectory(prefix='hyprlarp-daily-')
    self.addCleanup(temporary.cleanup)
    self.directory = Path(temporary.name)

  def test_new_preferences_persist_and_support_undo_reset_and_profiles(self):
    store = Store(self.directory)
    preferences = {'clockFormat': '12h', 'clockSeconds': True, 'clockDateFormat': 'yyyy-MM-dd',
      'calendarFirstDay': 'sunday', 'calendarWeekNumbers': True, 'batteryAlertsEnabled': False,
      'batteryAlertLevels': {'low': 25, 'critical': 7}}
    store.update(preferences)
    loaded = Store(self.directory)
    for key, value in preferences.items():
      self.assertEqual(loaded.settings[key], value)
    store.update(section_updates('General', DEFAULTS, store.settings))
    for key in preferences:
      self.assertEqual(store.settings[key], DEFAULTS[key])
    restored = store.undo()
    for key, value in preferences.items():
      self.assertEqual(restored[key], value)

  def test_invalid_formats_and_thresholds_are_rejected_without_saving(self):
    invalid = {'clockFormat': ['13h', [], None], 'clockDateFormat': ['cmd[update:1] anything', 'invalid', True],
      'calendarFirstDay': ['friday', 1], 'calendarWeekNumbers': [1, 'true'],
      'batteryAlertLevels': [{'low': 10, 'critical': 10}, {'low': 20, 'critical': 30},
        {'low': True, 'critical': 1}, {'low': 101, 'critical': 5}, {'low': 20}]}
    for key, values in invalid.items():
      for value in values:
        with self.subTest(key=key, value=value), self.assertRaises(ValueError):
          validate_setting(key, value)

  def battery(self, percent, *, plugged=False):
    return {'available': True, 'percent': percent, 'externalPower': plugged, 'charging': plugged,
      'batteries': [{'status': 'Charging' if plugged else 'Discharging'}]}

  def test_battery_warns_once_per_level_including_after_restart_and_jitter(self):
    alerts = BatteryAlerts(self.directory)
    self.assertIsNone(alerts.update(self.battery(30), DEFAULTS))
    self.assertEqual(alerts.update(self.battery(20), DEFAULTS), {'level': 'low', 'percent': 20})
    alerts = BatteryAlerts(self.directory)
    for value in [19, 21, 20, 11]:
      self.assertIsNone(alerts.update(self.battery(value), DEFAULTS))
    self.assertEqual(alerts.update(self.battery(9), DEFAULTS)['level'], 'critical')
    for value in [8, 11, 10]:
      self.assertIsNone(alerts.update(self.battery(value), DEFAULTS))
    self.assertIsNone(alerts.update(self.battery(10, plugged=True), DEFAULTS))
    self.assertEqual(alerts.update(self.battery(10), DEFAULTS)['level'], 'critical')

  def test_critical_startup_produces_one_notice_and_charge_rearms(self):
    alerts = BatteryAlerts(self.directory)
    self.assertEqual(alerts.update(self.battery(5), DEFAULTS)['level'], 'critical')
    self.assertIsNone(alerts.update(self.battery(19), DEFAULTS))
    self.assertIsNone(alerts.update(self.battery(26), DEFAULTS))
    self.assertEqual(alerts.update(self.battery(15), DEFAULTS)['level'], 'low')

  def test_battery_unknown_values_disabled_and_storage_failure_do_not_spam(self):
    alerts = BatteryAlerts(self.directory)
    for value in [None, float('nan'), -1, 101, True]:
      self.assertIsNone(alerts.update(self.battery(value), DEFAULTS))
    self.assertIsNone(alerts.update(self.battery(5), {**DEFAULTS, 'batteryAlertsEnabled': False}))
    unknown = self.battery(5)
    unknown['batteries'] = [{'status': 'Unknown'}]
    self.assertIsNone(alerts.update(unknown, DEFAULTS))
    with patch('backend.battery_alerts.atomic_json', side_effect=OSError('full')):
      self.assertIsNotNone(alerts.update(self.battery(5), DEFAULTS))
      self.assertIsNone(alerts.update(self.battery(4), DEFAULTS))

  def test_battery_sampling_does_not_require_a_battery_bar_module(self):
    settings = {**DEFAULTS, 'barModules': [], 'clipboardRetentionHours': 0}
    self.assertEqual(poll_intervals(settings, '', native_services=True), {'battery': 30})
    self.assertEqual(poll_intervals({**settings, 'batteryAlertsEnabled': False}, '', native_services=True), {})
    self.assertEqual(poll_intervals(settings, '', settings_only=True), {})

  def test_previews_never_send_or_persist_battery_alerts(self):
    for preview, settings_only in [(True, False), (False, True)]:
      service = Service(Store(self.directory), preview=preview, settings_only=settings_only)
      try:
        with patch('backend.service.battery_state', return_value=self.battery(1)), patch.object(service, 'emit') as emit:
          service.refresh_system(battery=True)
        self.assertFalse(any(call.args[0] == 'battery-alert' for call in emit.call_args_list))
        self.assertFalse((self.directory / 'battery-alerts.json').exists())
      finally:
        service.executor.shutdown(wait=True)

  def test_keyboard_reads_caps_lock_including_initial_state_and_unavailable(self):
    self.assertIsNone(keyboard_status(self.directory, self.directory)['capsLock'])
    led = self.directory / 'input3::capslock'
    led.mkdir()
    (led / 'brightness').write_text('1\n')
    self.assertTrue(keyboard_status(self.directory, self.directory)['capsLock'])
    (led / 'brightness').write_text('0\n')
    self.assertFalse(keyboard_status(self.directory, self.directory)['capsLock'])
    (led / 'brightness').write_text('unavailable')
    self.assertIsNone(keyboard_status(self.directory, self.directory)['capsLock'])

  def test_keyboard_layout_uses_compositor_precedence_and_shows_multiple_layouts(self):
    system = self.directory / 'keyboard'
    system.write_text('XKBMODEL="pc105"\nXKBLAYOUT="us,es" # system keyboard\n')
    self.assertEqual(keyboard_layout({}, {}, system), 'US / ES')
    self.assertEqual(keyboard_layout({}, {'XKB_DEFAULT_LAYOUT': 'latam'}, system), 'LATAM')
    self.assertEqual(keyboard_layout({'keyboard': {'layout': 'es'}}, {'XKB_DEFAULT_LAYOUT': 'us'}, system), 'ES')
    self.assertEqual(keyboard_layout({'keyboard': {'layout': '<script>'}}, {}, system), 'Predeterminado')

  @unittest.skipUnless(shutil.which('node'), 'Node unavailable')
  def test_calendar_and_settings_search(self):
    result = subprocess.run(['node', str(Path(__file__).with_suffix('.js'))], capture_output=True, text=True)
    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
