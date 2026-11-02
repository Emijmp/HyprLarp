import copy
import datetime as dt
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from backend.service import DEFAULTS, ROOT, Service, Store, generate_bindings, validate_setting
from backend.battery import battery_state
from backend.devices import UDISKS, usb_devices, usb_snapshot
from backend.night import scheduled_active


def usb_objects(protected=False):
  drive = "/org/freedesktop/UDisks2/drives/fixture"
  volume = "/org/freedesktop/UDisks2/block_devices/sdz1"
  return {drive: {UDISKS + ".Drive": {"ConnectionBus": "usb", "CanPowerOff": True, "Vendor": "Test", "Model": "USB", "Size": 1000000}},
    volume: {UDISKS + ".Block": {"Drive": drive, "PreferredDevice": list(b"/dev/sdz1\0"), "IdType": "exfat", "IdLabel": "Data", "Size": 1000000, "HintSystem": protected},
      UDISKS + ".Filesystem": {"MountPoints": [list((b"/" if protected else b"/run/media/test/data") + b"\0")]}}}


class BatteryTelemetryTests(unittest.TestCase):
  def make_battery(self, values):
    temporary = tempfile.TemporaryDirectory()
    self.addCleanup(temporary.cleanup)
    root = Path(temporary.name)
    pack = root / "BAT0"
    pack.mkdir()
    for name, value in {"type": "Battery", **values}.items():
      (pack / name).write_text(str(value))
    return root

  def test_missing_health_and_power_are_unknown(self):
    data = battery_state(self.make_battery({"capacity": 50, "status": "Discharging"}))["batteries"][0]
    for field in ("health", "watts", "cycles", "energyFull", "energyDesign", "timeToEmpty"):
      self.assertIsNone(data[field], field)

  def test_energy_health_cycles_and_remaining_time(self):
    pack = battery_state(self.make_battery({"capacity": 60, "status": "Discharging",
      "energy_now": 24000000, "energy_full": 40000000, "energy_full_design": 50000000,
      "power_now": 12000000, "cycle_count": 120, "voltage_now": 12000000, "temp": 315}))["batteries"][0]
    self.assertEqual(pack["health"], 80)
    self.assertEqual(pack["degradation"], 20)
    self.assertEqual(pack["energyNow"], 24)
    self.assertEqual(pack["timeToEmpty"], 7200)
    self.assertEqual(pack["cycles"], 120)
    self.assertEqual(pack["temperature"], 31.5)

  def test_charge_only_battery_converts_units_and_marks_estimate(self):
    pack = battery_state(self.make_battery({"status": "Charging", "charge_now": 2000000,
      "charge_full": 4000000, "charge_full_design": 5000000, "voltage_now": 12000000,
      "current_now": 1000000}))["batteries"][0]
    self.assertEqual(pack["health"], 80)
    self.assertEqual(pack["watts"], 12)
    self.assertEqual(pack["energyFull"], 48)
    self.assertEqual(pack["timeToFull"], 7200)
    self.assertTrue(pack["capacityEstimated"])

  def test_absent_battery_is_not_reported_as_present(self):
    self.assertFalse(battery_state(self.make_battery({"present": 0, "capacity": 0}))["available"])


class SystemFeatureTests(unittest.TestCase):
  def setUp(self):
    self.temp = tempfile.TemporaryDirectory()
    self.addCleanup(self.temp.cleanup)
    self.service = Service(Store(Path(self.temp.name)), preview=True)
    self.addCleanup(self.service.executor.shutdown, wait=True)
    self.events = []
    self.service.emit = lambda kind, data: self.events.append((kind, copy.deepcopy(data)))

  def test_new_preferences_validate_and_persist(self):
    settings = {"barWorkspaceDisplay": "current", "osdTimeout": 2000, "nightLightSchedule": True,
      "nightLightStart": "22:00", "nightLightEnd": "06:00", "nightLightTemperature": 3500}
    self.service.store.update(settings)
    loaded = Store(Path(self.temp.name)).settings
    for key, value in settings.items():
      self.assertEqual(loaded[key], value)
    for key, value in (("osdTimeout", 0), ("nightLightStart", "25:00"), ("nightLightEnd", "7:00"), ("nightLightTemperature", 999), ("barWorkspaceDisplay", "bad")):
      with self.assertRaises(ValueError):
        validate_setting(key, value)

  def test_night_schedule_crosses_midnight_and_daytime(self):
    settings = {**DEFAULTS, "nightLightSchedule": True}
    for hour, expected in [(19, False), (20, True), (23, True), (0, True), (6, True), (7, False), (12, False)]:
      self.assertEqual(scheduled_active(settings, dt.datetime(2026, 11, 1, hour)), expected)
    settings.update(nightLightStart="08:00", nightLightEnd="17:00")
    self.assertTrue(scheduled_active(settings, dt.datetime(2026, 11, 1, 10)))
    self.assertFalse(scheduled_active(settings, dt.datetime(2026, 11, 1, 20)))

  def test_preview_never_changes_usb_energy_or_starts_a_filter(self):
    with patch("backend.devices.subprocess.Popen") as start, patch("backend.night.subprocess.Popen") as night:
      for action, data in [("power-profile", {"profile": "performance"}), ("usb-mount", {"id": "bad"}),
        ("usb-eject", {"id": "bad"}), ("usb-open", {"id": "bad"})]:
        self.service.action({"action": action, "data": data})
      self.service.store.update({"nightLightEnabled": True})
      self.service.night.sync()
      start.assert_not_called()
      night.assert_not_called()

  def test_night_filter_does_not_take_over_an_existing_instance(self):
    self.service.preview = False
    self.service.store.update({"nightLightEnabled": True})
    with patch.object(self.service.night, "ipc", return_value="6500"), patch("backend.night.shutil.which", return_value="/usr/bin/hyprsunset"), patch("backend.night.subprocess.Popen") as start:
      self.service.night.sync()
      start.assert_not_called()
    state = [data for kind, data in self.events if kind == "night-light"][-1]
    self.assertFalse(state["active"])
    self.assertIn("otra instancia", state["error"])

  def test_managed_filter_starts_with_private_config_and_stops_only_its_process(self):
    self.service.preview = False
    self.service.store.update({"nightLightEnabled": True})
    process = Mock()
    process.poll.return_value = None
    with patch.object(self.service.night, "ipc", side_effect=[OSError("no daemon"), "4000"]), patch("backend.night.shutil.which", return_value="/usr/bin/hyprsunset"), patch("backend.night.subprocess.Popen", return_value=process) as start, patch("backend.night.threading.Thread"):
      self.service.night.sync()
      self.assertEqual(start.call_args.args[0][1], str(ROOT / "backend/night_child.py"))
      self.assertTrue(start.call_args.kwargs["env"]["XDG_CONFIG_HOME"].startswith(self.temp.name))
      self.service.store.update({"nightLightEnabled": False})
      self.service.night.sync()
      process.terminate.assert_called_once()

  def setup_devices(self, protected=False):
    self.service.preview = False
    devices = self.service.devices
    devices.need_usb = True
    devices.GLib = Mock()
    devices.GLib.Variant.side_effect = lambda signature, value: value
    devices.objects = Mock(return_value=usb_objects(protected))
    devices.call = Mock(return_value=())
    return devices

  def test_usb_snapshot_excludes_internal_disks_and_decodes_mounts(self):
    objects = usb_objects()
    objects["/org/freedesktop/UDisks2/drives/internal"] = {UDISKS + ".Drive": {"ConnectionBus": "nvme", "CanPowerOff": True}}
    snapshot = usb_snapshot(objects)
    self.assertEqual(len(snapshot), 1)
    self.assertEqual(snapshot[0]["volumes"][0]["device"], "/dev/sdz1")
    self.assertEqual(snapshot[0]["volumes"][0]["mounts"], ["/run/media/test/data"])

  def test_usb_inventory_includes_peripherals_without_duplicate_interfaces(self):
    base = Path(self.temp.name) / "usb"
    base.mkdir()
    for name in ("usb1", "1-1", "1-1:1.0"):
      (base / name).mkdir()
    for name in ("usb1", "1-1"):
      for key, value in {"idVendor": "1234", "idProduct": "abcd", "product": "USB keyboard", "speed": "12"}.items():
        (base / name / key).write_text(value)
    inventory = usb_devices(base)
    self.assertEqual(len(inventory), 1)
    self.assertEqual(inventory[0]["id"], "1-1")
    self.assertEqual(inventory[0]["speed"], "12")
    self.assertEqual(inventory[0]["manufacturer"], "")

  def test_old_dbus_startup_cannot_clear_a_new_connection(self):
    devices = self.service.devices
    old_connection, current_connection = Mock(), Mock()
    devices.connection = current_connection
    devices.generation = 2
    devices.need_usb = True
    glib = Mock()
    gio = Mock()
    gio.bus_get_sync.return_value = old_connection
    gi = Mock()
    with patch.dict(sys.modules, {"gi": gi, "gi.repository": SimpleNamespace(Gio=gio, GLib=glib)}):
      devices.run(1)
    self.assertIs(devices.connection, current_connection)
    self.assertGreater(old_connection.signal_unsubscribe.call_count, 0)
    glib.MainContext.new.return_value.pop_thread_default.assert_called_once()
    glib.MainLoop.new.return_value.run.assert_not_called()

  def test_native_observers_are_only_started_by_a_running_shell(self):
    self.service.preview = False
    with patch.object(self.service.devices, "sync") as sync, patch.object(self.service.backlight, "start") as backlight:
      self.service.sync_hardware()
      sync.assert_not_called()
      backlight.assert_not_called()
      self.service.serving = True
      self.service.active_panel = "energy"
      self.service.sync_hardware()
      sync.assert_called_once_with(power=True, usb=False)
      backlight.assert_called_once()

  def test_media_keys_include_microphone_and_respect_custom_bindings(self):
    settings = copy.deepcopy(DEFAULTS)
    bindings = generate_bindings(settings, ROOT / "bin/hyprlarp")
    self.assertIn("wpctl set-mute @DEFAULT_AUDIO_SOURCE@ toggle", bindings)
    settings["shortcuts"]["launcher"] = ", XF86AudioMicMute"
    bindings = generate_bindings(settings, ROOT / "bin/hyprlarp")
    self.assertNotIn("wpctl set-mute @DEFAULT_AUDIO_SOURCE@ toggle", bindings)
    self.assertEqual(bindings.count('hl.unbind("XF86AudioMicMute")'), 1)

  def test_usb_eject_unmounts_before_poweroff_and_never_forces(self):
    devices = self.setup_devices()
    devices.handle("usb-eject", {"id": "/org/freedesktop/UDisks2/drives/fixture"})
    methods = [call.args[3] for call in devices.call.call_args_list]
    self.assertEqual(methods, ["Unmount", "PowerOff"])
    for call in devices.call.call_args_list:
      self.assertEqual(call.args[4], ({},))

  def test_usb_busy_unmount_aborts_eject(self):
    devices = self.setup_devices()
    devices.call.side_effect = RuntimeError("busy")
    with self.assertRaises(RuntimeError):
      devices.handle("usb-eject", {"id": "/org/freedesktop/UDisks2/drives/fixture"})
    self.assertEqual(devices.call.call_count, 1)

  def test_usb_system_mount_and_unknown_paths_cannot_be_changed(self):
    devices = self.setup_devices(protected=True)
    for action, ident in [("usb-unmount", "/org/freedesktop/UDisks2/block_devices/sdz1"),
      ("usb-eject", "/org/freedesktop/UDisks2/drives/fixture"),
      ("usb-mount", "/dev/sdz1;bad"), ("usb-open", "/org/freedesktop/UDisks2/block_devices/internal")]:
      with self.assertRaises(ValueError):
        devices.handle(action, {"id": ident})
    devices.call.assert_not_called()

  def test_power_profiles_only_allow_hardware_supported_choices(self):
    devices = self.setup_devices()
    devices.need_power = True
    devices.power_endpoint = ("org.freedesktop.UPower.PowerProfiles", "/org/freedesktop/UPower/PowerProfiles")
    devices.power_properties = Mock(return_value={"Profiles": [{"Profile": "power-saver"}, {"Profile": "balanced"}], "ActiveProfile": "balanced"})
    with self.assertRaises(ValueError):
      devices.handle("power-profile", {"profile": "performance"})
    devices.call.assert_not_called()
    devices.handle("power-profile", {"profile": "power-saver"})
    self.assertEqual(devices.call.call_args.args[3], "Set")
    self.assertEqual(devices.call.call_args.args[4][-1], "power-saver")

  @unittest.skipUnless(shutil.which("node"), "Node is optional")
  def test_osd_and_schedule_state_models(self):
    subprocess.run(["node", str(ROOT / "tests/test_system_models.js")], check=True, text=True, capture_output=True)
