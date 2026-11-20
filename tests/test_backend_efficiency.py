"""Grouped battery reads and settings effects retain their observable behavior."""

import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from backend.battery import battery_state
from backend.service import Service, Store


class BatteryReadEfficiencyTests(unittest.TestCase):
  def setUp(self):
    self.temporary = tempfile.TemporaryDirectory()
    self.addCleanup(self.temporary.cleanup)
    self.root = Path(self.temporary.name)
    self.pack = self.root / "BAT0"
    self.pack.mkdir()

  def attributes(self, values):
    for key, value in {"type": "Battery", **values}.items():
      (self.pack / key).write_text(str(value))

  def snapshot(self, values):
    (self.pack / "uevent").write_text("\n".join("POWER_SUPPLY_" + key.upper() + "=" + str(value)
      for key, value in {"type": "Battery", **values}.items()))

  def reads(self):
    opened = []
    original = Path.open
    def tracked(path, *args, **kwargs):
      opened.append(path)
      return original(path, *args, **kwargs)
    return opened, patch.object(Path, "open", tracked)

  def test_grouped_snapshot_matches_the_individual_attribute_fallback(self):
    values = {"status": "Discharging", "present": 1, "capacity": 60,
      "energy_now": 24000000, "energy_full": 40000000, "energy_full_design": 50000000,
      "power_now": 12000000, "voltage_now": 12000000, "cycle_count": 120, "temp": 315,
      "manufacturer": "Fabricante", "model_name": "Equipo", "technology": "Li-ion", "serial_number": "test"}
    self.attributes(values)
    expected = battery_state(self.root)
    for path in self.pack.iterdir():
      path.unlink()
    self.snapshot(values)
    opened, track = self.reads()
    with track:
      self.assertEqual(battery_state(self.root), expected)
    self.assertEqual(opened.count(self.pack / "uevent"), 1)
    for key in values:
      self.assertNotIn(self.pack / key, opened)
    self.assertFalse(any(path.name in {"charge_now", "charge_full", "charge_full_design"} for path in opened))

  def test_missing_snapshot_fields_use_individual_attributes_once(self):
    self.snapshot({"status": "Charging", "present": 1, "charge_now": 2000000,
      "charge_full": 4000000, "charge_full_design": 5000000, "voltage_now": 12000000})
    (self.pack / "current_now").write_text("1000000")
    opened, track = self.reads()
    with track:
      battery = battery_state(self.root)["batteries"][0]
    self.assertEqual(battery["watts"], 12)
    self.assertEqual(battery["timeToFull"], 7200)
    self.assertEqual(opened.count(self.pack / "current_now"), 1)

  def test_bad_or_oversized_snapshot_keeps_the_compatible_attribute_path(self):
    self.attributes({"capacity": 25, "status": "Discharging"})
    expected = battery_state(self.root)
    for content in [b"\xff", b"POWER_SUPPLY_CAPACITY=99\n" + b"x" * 65536]:
      (self.pack / "uevent").write_bytes(content)
      self.assertEqual(battery_state(self.root), expected)

  def test_partial_energy_without_voltage_still_uses_charge_health(self):
    self.snapshot({"status": "Unknown", "energy_full": 40000000,
      "charge_full": 4000000, "charge_full_design": 5000000})
    battery = battery_state(self.root)["batteries"][0]
    self.assertEqual(battery["health"], 80)
    self.assertIsNone(battery["energyDesign"])
    self.assertFalse(battery["capacityEstimated"])

  def test_each_sample_observes_new_charge_and_external_power(self):
    self.snapshot({"capacity": 15, "status": "Discharging"})
    adapter = self.root / "AC"
    adapter.mkdir()
    (adapter / "uevent").write_text("POWER_SUPPLY_TYPE=Mains\nPOWER_SUPPLY_ONLINE=0")
    self.assertEqual(battery_state(self.root)["percent"], 15)
    self.assertFalse(battery_state(self.root)["externalPower"])
    self.snapshot({"capacity": 16, "status": "Charging"})
    (adapter / "uevent").write_text("POWER_SUPPLY_TYPE=Mains\nPOWER_SUPPLY_ONLINE=1")
    current = battery_state(self.root)
    self.assertEqual(current["percent"], 16)
    self.assertTrue(current["charging"])
    self.assertTrue(current["externalPower"])


class BackendSettingsEfficiencyTests(unittest.TestCase):
  def setUp(self):
    temporary = tempfile.TemporaryDirectory()
    self.addCleanup(temporary.cleanup)
    self.service = Service(Store(Path(temporary.name)), preview=True)
    self.addCleanup(self.service.executor.shutdown, wait=True)
    self.service.serving = True
    self.service.configuration_focused = True
    self.service.sync_watchers = Mock(return_value=None)
    self.service.sync_hardware = Mock()
    self.service.queue_refresh = Mock()
    self.service.wakeup.set = Mock()
    self.service.emit = Mock()

  def edit(self, updates):
    self.service.edit_settings("settings", updates, "config")

  def test_visual_edits_only_persist_and_acknowledge_preferences(self):
    self.edit({"theme": "gruvbox", "panelOpacity": .8, "font": "Sans Serif"})
    self.service.sync_watchers.assert_not_called()
    self.service.sync_hardware.assert_not_called()
    self.service.queue_refresh.assert_not_called()
    self.service.wakeup.set.assert_not_called()
    events = [call.args[0] for call in self.service.emit.call_args_list]
    self.assertIn("settings", events)
    self.assertIn("settings-history", events)
    self.assertEqual(self.service.store.history_state()["undo"], 1)

  def test_each_hardware_change_reaches_only_its_observers(self):
    self.edit({"clipboardEnabled": False})
    self.service.sync_watchers.assert_called_once()
    self.service.sync_hardware.assert_not_called()
    self.service.wakeup.set.assert_called_once()
    self.service.sync_watchers.reset_mock()
    self.service.wakeup.set.reset_mock()
    self.edit({"osdEnabled": False})
    self.service.sync_watchers.assert_not_called()
    self.service.sync_hardware.assert_called_once()
    self.service.wakeup.set.assert_not_called()
    self.edit({"performanceMode": "efficient"})
    self.service.wakeup.set.assert_called_once()

  def test_undo_redo_and_reset_still_resynchronize_changed_devices(self):
    self.edit({"clipboardEnabled": False, "osdEnabled": False, "nightLightTemperature": 5000})
    for action in ["settings-undo", "settings-redo", "settings-reset"]:
      self.service.sync_watchers.reset_mock()
      self.service.sync_hardware.reset_mock()
      self.service.queue_refresh.reset_mock()
      self.service.edit_settings(action, {}, "config")
      self.service.sync_watchers.assert_called_once()
      self.service.sync_hardware.assert_called_once()
      self.service.queue_refresh.assert_called_once_with("night-light", self.service.night.sync, latest=True)

  def test_monitor_overrides_reconfigure_hardware_and_sampling(self):
    self.edit({"monitorBars": {"DP-1": {"barModules": ["resources"]}}})
    self.service.sync_hardware.assert_called_once()
    self.service.wakeup.set.assert_called_once()

  def test_initial_poll_schedules_one_battery_read_only_when_needed(self):
    for settings_only in [False, True]:
      self.service.settings_only = settings_only
      self.service.stopping.clear()
      self.service.queue_refresh.reset_mock()
      with patch.object(self.service, "refresh_system") as reader, \
          patch.object(self.service.wakeup, "wait", side_effect=lambda timeout: self.service.stopping.set()):
        self.service.poll()
        reader.assert_not_called()
      tasks = {call.args[0]: call.args[1] for call in self.service.queue_refresh.call_args_list}
      if settings_only:
        self.assertNotIn("battery", tasks)
      else:
        self.assertIn("battery", tasks)
        self.service.stopping.clear()
        with patch.object(self.service, "refresh_system") as reader:
          tasks["battery"]()
          reader.assert_called_once_with(battery=True)

  def test_compact_events_preserve_unicode_json_lines(self):
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
      Service.emit(self.service, "message", {"text": "Captura ñ", "items": [1, 2]})
    message = output.getvalue()
    self.assertEqual(json.loads(message), {"type": "message", "data": {"text": "Captura ñ", "items": [1, 2]}})
    self.assertEqual(len(message.splitlines()), 1)
    self.assertNotIn(': ', message)
    self.assertNotIn(', ', message)
