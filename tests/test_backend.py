import copy
import io
import json
import os
from pathlib import Path
import tempfile
import subprocess
import sys
import shutil
import threading
import unittest
from unittest.mock import patch

from backend.service import DEFAULTS, ROOT, Service, Store, battery_state, brightness_state, generate_bindings, lua_string, parse_networks, poll_intervals, validate_geometry, validate_setting
from backend.icons import IconResolver, choose_icon_theme


class ConfigurationTests(unittest.TestCase):
  def test_new_bar_settings_preserve_zero_values_after_reload(self):
    with tempfile.TemporaryDirectory() as directory:
      updates = {"barOpacity": 0, "moduleOpacity": 0, "barBorderWidth": 0,
           "barPaddingX": 0, "barPaddingY": 0, "barSpacing": 0,
           "barMargins": {"top": 0, "right": 0, "bottom": 0, "left": 0},
           "barBlur": True, "barReserveSpace": False, "barLength": 25,
           "barAlignment": "end", "barSize": 22}
      store = Store(Path(directory))
      store.update(updates)
      loaded = Store(Path(directory)).settings
      for key, value in updates.items():
        self.assertEqual(loaded[key], value, key)

  def test_invalid_geometry_is_rejected_before_persisting(self):
    with tempfile.TemporaryDirectory() as directory:
      store = Store(Path(directory))
      store.update({"barPaddingY": 10, "barSize": 48})
      original = store.file.read_text()
      with self.assertRaises(ValueError):
        store.update({"barSize": 22})
      self.assertEqual(store.file.read_text(), original)

  def test_old_style_migrates_without_changing_the_original_file(self):
    with tempfile.TemporaryDirectory() as directory:
      saved = {"version": 1, "theme": "graphite", "accent": "#b8a1ff",
          "barSize": 48, "barMargin": 0, "barPosition": "bottom", "radius": 12}
      filename = Path(directory) / "settings.json"
      original = json.dumps(saved)
      filename.write_text(original)
      store = Store(Path(directory))
      self.assertEqual(store.settings["version"], 3)
      self.assertEqual(store.settings["theme"], "amoled")
      self.assertEqual(store.settings["barPosition"], "bottom")
      self.assertEqual(store.settings["barMargins"], {"top": 0, "right": 0, "bottom": 0, "left": 0})
      self.assertEqual(filename.read_text(), original)

  def test_invalid_saved_geometry_is_repaired_to_fit_content(self):
    with tempfile.TemporaryDirectory() as directory:
      saved = {**DEFAULTS, "barSize": 22, "barPaddingX": 64, "barPaddingY": 64}
      (Path(directory) / "settings.json").write_text(json.dumps(saved))
      store = Store(Path(directory))
      validate_geometry(store.settings)
      self.assertTrue(store.warning)

  def test_malformed_migration_fields_do_not_crash_loading(self):
    with tempfile.TemporaryDirectory() as directory:
      (Path(directory) / "settings.json").write_text(json.dumps({"version": [], "theme": [], "wallpaper": []}))
      store = Store(Path(directory))
      self.assertEqual(store.settings["theme"], "amoled")
      self.assertTrue(store.warning)

  def test_margins_and_blur_require_valid_shapes_and_types(self):
    for key, value in [("barMargins", {"top": 0}), ("barMargins", {"top": -1, "right": 0, "bottom": 0, "left": 0}), ("barBlur", "yes"), ("barLength", 101), ("barAlignment", "invalid")]:
      with self.subTest(key=key, value=value), self.assertRaises(ValueError):
        validate_setting(key, value)

  def test_updates_are_atomic_and_preserve_unrelated_preferences(self):
    with tempfile.TemporaryDirectory() as directory:
      store = Store(Path(directory))
      store.update({"barPosition": "left", "barSize": 48, "accent": "#123abc"})
      original = store.file.read_text()
      with self.assertRaises(ValueError):
        store.update({"accent": "#ffffff", "barOpacity": -1})
      self.assertEqual(store.file.read_text(), original)
      self.assertEqual(Store(Path(directory)).settings["barPosition"], "left")

  def test_corrupt_config_is_preserved(self):
    with tempfile.TemporaryDirectory() as directory:
      filename = Path(directory) / "settings.json"
      filename.write_text("{broken")
      store = Store(Path(directory))
      self.assertTrue(store.warning)
      self.assertEqual(store.settings, DEFAULTS)
      self.assertEqual(filename.read_text(), "{broken")

  def test_shortcuts_reject_injection_duplicates_and_unknown_modifiers(self):
    for value in ["SUPER, S\nexec = reboot", "SUPER, S; reboot", "WRONG, A", "SUPER, SPACE"]:
      shortcuts = copy.deepcopy(DEFAULTS["shortcuts"])
      shortcuts["settings"] = value
      with self.subTest(value=value), self.assertRaises(ValueError):
        validate_setting("shortcuts", shortcuts)

  def test_module_order_and_opacity_validation(self):
    self.assertEqual(validate_setting("barModules", ["clock", "launcher"]), ["clock", "launcher"])
    self.assertEqual(validate_setting("barModules", []), [])
    with self.assertRaises(ValueError):
      validate_setting("barModules", ["launcher", "launcher"])
    with self.assertRaises(ValueError):
      validate_setting("barModules", ["unknown"])
    with self.assertRaises(ValueError):
      validate_setting("moduleOpacities", {"volume": float("nan")})
    self.assertEqual(validate_setting("moduleOpacities", {"volume": 0.6}), {"volume": 0.6})

  def test_bindings_quote_paths_and_keep_the_keyboard_modifiers(self):
    generated = generate_bindings(DEFAULTS, Path("/tmp/a b/hyprlarp"))
    self.assertIn("'/tmp/a b/hyprlarp' settings", generated)
    self.assertIn('["chord"] = "SUPER, comma"', generated)
    self.assertNotIn("hl.unbind", generated)

  def test_migration_preserves_enabled_module_order_and_custom_shortcuts(self):
    with tempfile.TemporaryDirectory() as directory:
      shortcuts = {key: value for key, value in DEFAULTS["shortcuts"].items()
             if key not in {"wifi", "bluetooth", "resources", "battery", "capture"}}
      shortcuts["launcher"] = "SUPER CTRL, W"
      saved = {"version": 2, "barModules": ["clock", "media", "launcher", "wifi"],
           "disabledModules": ["media"], "showAppIcons": False, "shortcuts": shortcuts}
      (Path(directory) / "settings.json").write_text(json.dumps(saved))
      settings = Store(Path(directory)).settings
      self.assertEqual(settings["barModules"], ["clock", "launcher", "wifi"])
      self.assertEqual(settings["disabledModules"], [])
      self.assertTrue(settings["showAppIcons"])
      self.assertEqual(settings["shortcuts"]["launcher"], "SUPER CTRL, W")
      self.assertEqual(settings["shortcuts"]["wifi"], "")
      self.assertEqual(settings["shortcuts"]["bluetooth"], "SUPER CTRL, B")

  def test_module_style_and_empty_selection_persist(self):
    with tempfile.TemporaryDirectory() as directory:
      settings = Store(Path(directory))
      updates = {"barModules": [], "moduleBackgroundOpacity": 0, "moduleRadius": 0,
           "moduleBorderWidth": 0, "modulePaddingX": 0, "modulePaddingY": 0}
      settings.update(updates)
      reloaded = Store(Path(directory)).settings
      for key, value in updates.items():
        self.assertEqual(reloaded[key], value)

  def test_shortcuts_can_be_disabled_and_do_not_duplicate_workspace_bindings(self):
    settings = copy.deepcopy(DEFAULTS)
    settings["shortcuts"]["wifi"] = ""
    settings["shortcuts"]["launcher"] = "SUPER, 1"
    generated = generate_bindings(settings, ROOT / "bin/hyprlarp")
    self.assertNotIn("toggle wifi", generated)
    self.assertNotIn("workspace = 1 }", generated)
    self.assertNotIn("workspace = ", generated)
    self.assertNotIn("hl.unbind", generated)

  def test_saving_identical_settings_does_not_write_to_disk(self):
    with tempfile.TemporaryDirectory() as directory, patch("backend.service.atomic_json") as write:
      Store(Path(directory)).update({"theme": DEFAULTS["theme"]})
      write.assert_not_called()


class IntegrationParserTests(unittest.TestCase):
  def test_icon_fallback_resolves_inherited_themes_and_24px_variants(self):
    with tempfile.TemporaryDirectory() as directory:
      base = Path(directory)
      icons = base / "icons"
      for name, metadata in {"Custom": "Inherits=Parent\nDirectories=48/apps,24/apps\n\n[48/apps]\nSize=48\n[24/apps]\nSize=24\n", "Parent": "Directories=24/apps\n\n[24/apps]\nSize=24\n"}.items():
        folder = icons / name
        folder.mkdir(parents=True)
        (folder / "index.theme").write_text("[Icon Theme]\n" + metadata)
      for relative in ["Custom/48/apps/editor.svg", "Custom/24/apps/editor.svg", "Parent/24/apps/network.png"]:
        image = icons / relative
        image.parent.mkdir(parents=True, exist_ok=True)
        image.write_text("fixture")
      resolver = IconResolver({"QS_ICON_THEME": "Custom", "XDG_DATA_HOME": str(base), "XDG_DATA_DIRS": str(base / "other")})
      resolved = resolver.resolve(["editor", "network", "missing", "../../invalid"])
      self.assertEqual(resolved["editor"], (icons / "Custom/24/apps/editor.svg").as_uri())
      self.assertEqual(resolved["network"], (icons / "Parent/24/apps/network.png").as_uri())
      self.assertEqual(resolved["missing"], "")
      self.assertNotIn("../../invalid", resolved)

  def test_broken_absolute_desktop_icons_use_the_generic_fallback(self):
    with tempfile.TemporaryDirectory() as directory:
      image = Path(directory) / "valid.png"
      image.write_text("fixture")
      missing = Path(directory) / "missing.svg"
      resolver = IconResolver({"QS_ICON_THEME": "", "XDG_DATA_HOME": directory, "XDG_DATA_DIRS": directory})
      result = resolver.resolve([str(image), str(missing)])
      self.assertEqual(result[str(image)], image.as_uri())
      self.assertEqual(result[str(missing)], "")
  def test_installed_desktop_icon_theme_is_detected_and_explicit_override_wins(self):
    with tempfile.TemporaryDirectory() as directory:
      base = Path(directory)
      theme = base / "share/icons/Custom"
      theme.mkdir(parents=True)
      (theme / "index.theme").write_text("[Icon Theme]\nName=Custom\n")
      config = base / "config/gtk-3.0"
      config.mkdir(parents=True)
      (config / "settings.ini").write_text("[Settings]\ngtk-icon-theme-name=Custom\n")
      environment = {"XDG_CONFIG_HOME": str(base / "config"), "XDG_DATA_HOME": str(base / "share"), "XDG_DATA_DIRS": str(base / "other")}
      self.assertEqual(choose_icon_theme(environment), "Custom")
      self.assertEqual(choose_icon_theme({**environment, "QS_ICON_THEME": "Override"}), "Override")
  def test_backlight_is_read_without_spawning_a_process(self):
    with tempfile.TemporaryDirectory() as directory:
      device = Path(directory) / "panel"
      device.mkdir()
      (device / "brightness").write_text("200")
      (device / "max_brightness").write_text("800")
      self.assertEqual(brightness_state(Path(directory)), {"brightness": 25, "brightnessAvailable": True})
      (device / "max_brightness").write_text("0")
      self.assertFalse(brightness_state(Path(directory))["brightnessAvailable"])
  def test_wifi_names_with_colons_and_backslashes_are_not_split(self):
    networks = parse_networks("*:Studio\\:5G:88:WPA2:wlan0\n:Studio\\:5G:42:WPA2:wlan0\n:Path\\\\Room:55:WPA3:wlan0\ninvalid\n:bad:wrong:WPA2:wlan0")
    self.assertEqual([n["ssid"] for n in networks], ["Studio:5G", "Path\\Room"])
    self.assertTrue(networks[0]["connected"])
    self.assertEqual(networks[0]["signal"], 88)

  def test_desktop_without_battery_is_supported(self):
    with tempfile.TemporaryDirectory() as directory:
      self.assertFalse(battery_state(Path(directory))["available"])

  def test_battery_energy_and_charging_are_read(self):
    with tempfile.TemporaryDirectory() as directory:
      battery = Path(directory) / "BAT0"
      battery.mkdir()
      for key, value in {"type": "Battery", "capacity": "72", "status": "Charging", "energy_full": "40000000", "energy_full_design": "50000000", "power_now": "12000000"}.items():
        (battery / key).write_text(value)
      data = battery_state(Path(directory))
      self.assertEqual(data["percent"], 72)
      self.assertTrue(data["charging"])
      self.assertEqual(data["batteries"][0]["health"], 80)


class ResourceSchedulingTests(unittest.TestCase):
  def test_native_idle_only_samples_enabled_battery_alerts_and_settings_never_poll(self):
    self.assertEqual(poll_intervals(DEFAULTS, "", native_services=True), {"battery": 30})
    self.assertEqual(poll_intervals({**DEFAULTS, "batteryAlertsEnabled": False}, "", native_services=True), {})
    self.assertEqual(poll_intervals(DEFAULTS, "resources", settings_only=True), {})

  def test_metrics_only_sample_when_visible_and_clipboard_only_when_open(self):
    self.assertNotIn("metrics", poll_intervals(DEFAULTS, "launcher"))
    self.assertEqual(poll_intervals(DEFAULTS, "resources")["metrics"], 2)
    self.assertEqual(poll_intervals(DEFAULTS, "clipboard")["clipboard"], 2)
    self.assertNotIn("clipboard", poll_intervals(DEFAULTS, ""))
    settings = {**DEFAULTS, "barModules": ["resources", "battery"]}
    self.assertEqual(poll_intervals(settings, "", native_services=True), {"metrics": 2, "battery": 30})
    self.assertEqual(poll_intervals(settings, "battery")["battery"], 2)

  def test_native_services_do_not_poll_wifi_or_bluetooth(self):
    self.assertNotIn("network", poll_intervals(DEFAULTS, "wifi", native_services=True))
    self.assertNotIn("bluetooth", poll_intervals(DEFAULTS, "bluetooth", native_services=True))
    self.assertEqual(poll_intervals(DEFAULTS, "wifi")["network"], 60)

  def test_refresh_requests_are_bounded_and_coalesce_the_latest_event(self):
    with tempfile.TemporaryDirectory() as directory:
      service = Service(Store(Path(directory)), preview=True)
      entered, release, completed = threading.Event(), threading.Event(), threading.Event()
      calls = []
      def slow():
        calls.append("first")
        entered.set()
        release.wait(3)
      def latest():
        calls.append("latest")
        completed.set()
      try:
        self.assertTrue(service.queue_refresh("wifi", slow))
        self.assertTrue(entered.wait(1))
        for _ in range(20):
          self.assertFalse(service.queue_refresh("wifi", latest, latest=True))
        self.assertEqual(len(service.refreshing), 1)
        self.assertEqual(len(service.pending_refresh), 1)
        release.set()
        self.assertTrue(completed.wait(2))
      finally:
        release.set()
        service.executor.shutdown(wait=True)
      self.assertEqual(calls, ["first", "latest"])

  def test_system_snapshots_only_emit_when_the_data_changes_and_need_no_commands(self):
    with tempfile.TemporaryDirectory() as directory:
      service = Service(Store(Path(directory)), preview=True)
      events = []
      service.emit = lambda kind, data: events.append((kind, data))
      try:
        with patch("backend.service.command") as command:
          service.refresh_system(brightness=True, battery=True)
          service.refresh_system(brightness=True, battery=True)
          command.assert_not_called()
        self.assertEqual(len(events), 1)
      finally:
        service.executor.shutdown(wait=True)


class WorkspaceModelTests(unittest.TestCase):
  @unittest.skipUnless(shutil.which("node"), "Node is optional for workspace model regression tests")
  def test_monitor_state_and_dispatch_commands(self):
    subprocess.run(["node", str(ROOT / "tests/test_workspaces.js")], check=True, capture_output=True, text=True)


class InstallerTests(unittest.TestCase):
  def test_install_and_reinstall_preserve_preferences_and_back_up_files(self):
    with tempfile.TemporaryDirectory(prefix="hyprlarp-install-") as directory:
      prefix = Path(directory) / "prefix with spaces"
      invocation = [sys.executable, str(ROOT / "tools/install.py"), "--prefix", str(prefix)]
      subprocess.run(invocation, check=True, capture_output=True, text=True)
      config = prefix / "config/hyprlarp"
      Store(config).update({"accent": "#123456"})
      active_bindings = (config / "bindings.lua").read_bytes()
      bindings_inode = (config / "bindings.lua").stat().st_ino
      subprocess.run(invocation, check=True, capture_output=True, text=True)
      self.assertEqual(Store(config).settings["accent"], "#123456")
      self.assertTrue((prefix / "bin/hyprlarp").is_file())
      self.assertTrue((prefix / "share/hyprlarp/shell.qml").is_file())
      self.assertTrue(list((prefix / "share").glob("hyprlarp.backup-*")))
      self.assertEqual((config / "bindings.lua").read_bytes(), active_bindings)
      self.assertEqual((config / "bindings.lua").stat().st_ino, bindings_inode)
      self.assertFalse(list(config.glob("bindings.lua.backup-*")))
      self.assertIn("inhibit_sleep = 3", (config / "hypridle.conf").read_text())

  def test_dry_run_does_not_create_the_destination(self):
    with tempfile.TemporaryDirectory() as directory:
      prefix = Path(directory) / "not-created"
      subprocess.run([sys.executable, str(ROOT / "tools/install.py"), "--prefix", str(prefix), "--dry-run"],
             check=True, capture_output=True)
      self.assertFalse(prefix.exists())

  @unittest.skipUnless(shutil.which("Hyprland"), "Hyprland no está instalado")
  def test_generated_lua_is_accepted_by_the_installed_compositor(self):
    with tempfile.TemporaryDirectory(prefix="hyprlarp-lua-") as directory:
      prefix = Path(directory) / "isolated"
      subprocess.run([sys.executable, str(ROOT / "tools/install.py"), "--prefix", str(prefix)],
             check=True, capture_output=True)
      config = Path(directory) / "verify.lua"
      config.write_text("dofile(" + lua_string(str(prefix / "config/hyprlarp/bindings-prelude.lua")) + ")\n"
               + "hl.bind(\"SUPER + SHIFT + S\", function() end)\n"
               + "dofile(" + lua_string(str(prefix / "config/hyprlarp/hyprlarp.lua")) + ")\n"
               + "dofile(" + lua_string(str(ROOT / "config/hyprland-look.lua")) + ")\n")
      result = subprocess.run(["Hyprland", "--verify-config", "--config", str(config)],
                  env={**os.environ, "XDG_RUNTIME_DIR": directory},
                  capture_output=True, text=True, timeout=15)
      self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
      self.assertIn("config ok", result.stdout, result.stdout + result.stderr)


class ActionSafetyTests(unittest.TestCase):
  def setUp(self):
    self.temp = tempfile.TemporaryDirectory()
    self.service = Service(Store(Path(self.temp.name)), preview=True)
    self.events = []
    self.service.emit = lambda kind, data: self.events.append((kind, data))

  def tearDown(self):
    self.service.executor.shutdown(wait=True)
    self.temp.cleanup()

  def test_preview_never_executes_device_or_session_mutations(self):
    actions = ["volume", "brightness", "wifi-connect", "wifi-power", "bluetooth-connect", "clipboard-copy", "clipboard-clear", "screenshot", "session", "apply-shortcuts", "apply-window-gaps", "open-tool"]
    with patch("backend.service.command") as run, patch("backend.service.subprocess.Popen") as spawn:
      for action in actions:
        self.service.action({"action": action, "data": {"command": "poweroff", "value": 0.5}})
      run.assert_not_called()
      spawn.assert_not_called()
    self.assertEqual(len([event for event in self.events if event[0] == "error"]), len(actions))

  def test_empty_history_can_be_saved(self):
    self.service.action({"action": "history", "data": []})
    self.assertEqual(json.loads((Path(self.temp.name) / "notifications.json").read_text()), [])

  def test_production_rejects_command_injection_before_spawning(self):
    self.service.preview = False
    with patch("backend.service.command") as run:
      self.service.action({"action": "bluetooth-connect", "data": {"address": "AA:BB:CC:DD:EE:FF; reboot"}})
      self.service.action({"action": "workspace", "data": {"id": "1; reboot"}})
      self.service.action({"action": "volume", "data": {"value": 999}})
      self.service.action({"action": "session", "data": {"command": "arbitrary"}})
      run.assert_not_called()

  def test_unknown_action_and_wrong_payload_fail_closed(self):
    self.service.action({"action": "run-anything", "data": {}})
    self.service.action({"action": "volume", "data": []})
    self.assertEqual(len([event for event in self.events if event[0] == "error"]), 2)

  def test_suspend_requires_the_managed_idle_daemon(self):
    with patch("backend.service.optional", return_value=""), patch("backend.service.command") as run:
      with self.assertRaises(RuntimeError):
        Service.session("suspend", Path(self.temp.name))
      run.assert_not_called()


if __name__ == "__main__":
  unittest.main()
