import copy
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

from backend.service import MODULE_DEFINITIONS, MODULES, DEFAULTS, ROOT, Service, Store, poll_intervals, validate_setting
from backend.captures import annotations_svg, window_geometry


class FeatureTests(unittest.TestCase):
  def setUp(self):
    self.temporary = tempfile.TemporaryDirectory()
    self.directory = Path(self.temporary.name)
    self.store = Store(self.directory)
    self.service = Service(self.store, preview=True)
    self.events = []
    self.service.emit = lambda kind, data: self.events.append((kind, copy.deepcopy(data)))

  def tearDown(self):
    self.service.executor.shutdown(wait=True)
    self.temporary.cleanup()

  def config(self, action, data=None):
    self.service.configuration_focused = True
    self.service.action({"action": action, "data": data or {}, "source": "config"})

  def errors(self):
    return [data for kind, data in self.events if kind == "error"]

  def test_every_shell_function_is_available_as_an_optional_module(self):
    required = {"calendar", "audio", "brightness", "wallpapers", "capture", "settings", "themes", "profiles", "shortcuts", "bar-settings", "module-settings", "do-not-disturb", "clipboard-pause", "lock", "screenshot-region", "screenshot-window", "screenshot-screen", "suspend", "logout", "reboot", "poweroff", "mute", "microphone-mute", "media-play-pause", "media-previous", "media-next"}
    self.assertTrue(required <= MODULES)
    self.assertEqual(len(MODULE_DEFINITIONS), len(MODULES))
    selected = [entry["id"] for entry in MODULE_DEFINITIONS]
    self.store.update({"barModules": selected})
    self.assertEqual(Store(self.directory).settings["barModules"], selected)
    self.assertFalse(required & set(DEFAULTS["barModules"]))

  def test_module_catalog_covers_lazy_panels_config_pages_and_safe_session_actions(self):
    pages = {"Appearance", "Bar", "Modules", "Wallpapers", "Shortcuts", "General", "Profiles"}
    for entry in MODULE_DEFINITIONS:
      self.assertTrue(entry["title"] and entry["description"] and entry["icon"])
      if entry["kind"] == "panel":
        sources = {"wifi": "Network", "clock": "Calendar", "night-light": "NightLight"}
        file = sources.get(entry["target"], entry["target"].capitalize()) + "Panel.qml"
        self.assertTrue((ROOT / "panels" / file).is_file(), entry["id"])
      if entry["kind"] == "settings":
        self.assertIn(entry["target"], pages)
      if entry["id"] in {"suspend", "logout", "reboot", "poweroff"}:
        self.assertEqual(entry["kind"], "session")
    self.assertTrue({"settings-undo", "settings-redo", "settings-reset"}.isdisjoint(MODULES))

  def test_new_modules_support_zones_monitor_overrides_and_opacity(self):
    self.store.update({"monitorBars": {"DP-1": {"barZones": {"start": ["profiles"], "center": ["calendar"], "end": ["lock", "capture"]}, "moduleOpacities": {"lock": 0.5}}}})
    reloaded = Store(self.directory).settings["monitorBars"]["DP-1"]
    self.assertEqual(reloaded["barModules"], ["profiles", "calendar", "lock", "capture"])
    self.assertEqual(reloaded["moduleOpacities"]["lock"], 0.5)
    self.store.undo()
    self.assertEqual(self.store.settings["monitorBars"], {})

  def test_brightness_reads_are_only_scheduled_when_visible(self):
    settings = copy.deepcopy(DEFAULTS)
    self.assertNotIn("brightness", poll_intervals(settings, "", native_services=True))
    self.assertIn("brightness", poll_intervals(settings, "brightness", native_services=True))
    settings["monitorBars"] = {"DP-1": {"barModules": ["brightness"]}}
    self.assertIn("brightness", poll_intervals(settings, "", native_services=True, outputs=["DP-1"]))
    self.assertNotIn("brightness", poll_intervals(settings, "", native_services=True, outputs=["eDP-1"]))

  def test_corner_radii_are_independent_persisted_and_undoable(self):
    self.store.update({"radius": 6, "cornerRadii": {"bar": 0, "button": 4, "workspace": 2}, "moduleRadius": 8})
    loaded = Store(self.directory).settings
    self.assertEqual(loaded["cornerRadii"], {"bar": 0, "button": 4, "workspace": 2})
    self.assertEqual(loaded["radius"], 6)
    self.assertEqual(loaded["moduleRadius"], 8)
    self.config("settings-reset-section", {"section": "Appearance"})
    self.assertEqual(self.store.settings["cornerRadii"], {})
    self.config("settings-undo")
    self.assertEqual(self.store.settings["cornerRadii"], loaded["cornerRadii"])
    for value in ({"unknown": 2}, {"panel": 9}, {"button": True}, {"workspace": -1}, []):
      with self.assertRaises((ValueError, TypeError)):
        validate_setting("cornerRadii", value)

  def test_old_radius_preference_remains_the_general_fallback(self):
    (self.directory / "settings.json").write_text(json.dumps({"version": 3, "radius": 3}))
    loaded = Store(self.directory).settings
    self.assertEqual(loaded["radius"], 3)
    self.assertEqual(loaded["cornerRadii"], {})

  def test_decoration_preference_is_validated_persisted_and_undoable(self):
    self.store.update({"decoration": "minimal"})
    self.assertEqual(Store(self.directory).settings["decoration"], "minimal")
    self.config("settings-reset-section", {"section": "Appearance"})
    self.assertEqual(self.store.settings["decoration"], "subtle")
    self.config("settings-undo")
    self.assertEqual(self.store.settings["decoration"], "minimal")
    with self.assertRaises(ValueError):
      validate_setting("decoration", "glow")

  def test_monitor_layout_is_inherited_validated_and_undoable(self):
    self.store.update({"monitorBars": {"DP-1": {"barPosition": "left", "barSize": 48,
      "barZones": {"start": ["workspaces"], "center": ["clock"], "end": ["session"]}}}})
    override = self.store.settings["monitorBars"]["DP-1"]
    self.assertEqual(override["barModules"], ["workspaces", "clock", "session"])
    self.assertEqual(self.store.settings["barPosition"], "top")
    original = self.store.file.read_text()
    with self.assertRaises(ValueError):
      self.store.update({"barIconSize": 24, "monitorBars": {"DP-1": {"barSize": 22}}})
    self.assertEqual(self.store.file.read_text(), original)
    self.store.undo()
    self.assertEqual(self.store.settings["monitorBars"], {})

  def test_layout_rejects_duplicates_and_keeps_legacy_order(self):
    with self.assertRaises(ValueError):
      self.store.update({"barZones": {"start": ["clock"], "center": ["clock"], "end": []}})
    self.store.update({"barModules": ["session", "clock"]})
    self.assertEqual(self.store.settings["barZones"], {"start": ["session", "clock"], "center": [], "end": []})

  def test_invalid_saved_monitor_geometry_does_not_break_loading(self):
    settings = copy.deepcopy(DEFAULTS)
    settings["monitorBars"] = {"DP-1": {"barPaddingX": 64, "modulePaddingX": 32, "barPosition": "left"}}
    (self.directory / "settings.json").write_text(json.dumps(settings))
    self.assertNotIn("DP-1", Store(self.directory).settings["monitorBars"])

  def test_only_connected_monitor_modules_schedule_reads(self):
    settings = copy.deepcopy(DEFAULTS)
    settings["monitorBars"] = {"DP-1": {"barModules": ["resources"]}}
    self.assertNotIn("metrics", poll_intervals(settings, "", native_services=True, outputs=["eDP-1"]))
    self.assertIn("metrics", poll_intervals(settings, "", native_services=True, outputs=["DP-1"]))
    settings["monitorBars"]["DP-1"]["barEnabled"] = False
    self.assertNotIn("metrics", poll_intervals(settings, "", native_services=True, outputs=["DP-1"]))

  def test_section_reset_preserves_other_sections_and_can_be_undone(self):
    self.store.update({"theme": "gruvbox", "barSpacing": 18})
    self.config("settings-reset-section", {"section": "Bar"})
    self.assertEqual(self.store.settings["barSpacing"], DEFAULTS["barSpacing"])
    self.assertEqual(self.store.settings["theme"], "gruvbox")
    self.config("settings-undo")
    self.assertEqual(self.store.settings["barSpacing"], 18)

  def test_section_reset_fits_geometry_changed_in_another_section(self):
    self.store.update({"modulePaddingY": 0, "moduleBorderWidth": 0, "barPaddingY": 0, "barSize": 22})
    self.config("settings-reset-section", {"section": "Modules"})
    self.assertFalse(self.errors())
    self.assertGreaterEqual(self.store.settings["barSize"], 24)
    self.config("settings-undo")
    self.assertEqual(self.store.settings["barSize"], 22)

  def test_library_write_failure_preserves_in_memory_library(self):
    self.service.configuration_focused = True
    with patch("backend.service.atomic_json", side_effect=OSError("disk full")):
      self.service.action({"action": "profile-save", "data": {"name": "failed"}, "source": "config"})
    self.assertEqual(self.service.features.library["profiles"], {})
    self.assertTrue(self.errors())

  def test_shortcut_modifier_aliases_cannot_duplicate_a_binding(self):
    shortcuts = dict(DEFAULTS["shortcuts"])
    shortcuts["control"] = "MOD4, SPACE"
    with self.assertRaises(ValueError):
      validate_setting("shortcuts", shortcuts)

  def test_reset_monitor_section_returns_to_inheritance(self):
    self.store.update({"monitorBars": {"DP-1": {"barSpacing": 18, "barModules": ["clock"]}}})
    self.config("settings-reset-section", {"section": "Bar", "monitor": "DP-1"})
    self.assertNotIn("barSpacing", self.store.settings["monitorBars"]["DP-1"])
    self.assertEqual(self.store.settings["monitorBars"]["DP-1"]["barModules"], ["clock"])

  def test_profiles_wait_for_explicit_config_source_and_restore_atomically(self):
    self.service.action({"action": "profile-save", "data": {"name": "Desk"}})
    self.assertTrue(self.errors())
    self.events.clear()
    self.store.update({"theme": "tokyonight", "barSpacing": 14})
    self.config("profile-save", {"name": "Desk"})
    saved = copy.deepcopy(self.store.settings)
    self.store.update({"theme": "amoled", "barSpacing": 10})
    self.config("profile-apply", {"name": "Desk"})
    self.assertEqual(self.store.settings["theme"], saved["theme"])
    self.assertEqual(self.store.settings["barSpacing"], 14)
    self.assertTrue((self.directory / "settings.backup.json").is_file())
    self.config("settings-undo")
    self.assertEqual(self.store.settings["theme"], "amoled")
    self.assertFalse(self.errors())

  def test_theme_library_retains_multiple_named_palettes(self):
    self.store.update({"theme": "gruvbox"})
    self.config("theme-save", {"name": "Warm"})
    self.store.update({"theme": "oxocarbon"})
    self.config("theme-save", {"name": "Dark"})
    self.config("theme-use", {"name": "Warm"})
    self.assertEqual(self.store.settings["theme"], "custom")
    self.assertEqual(self.store.settings["customPalette"]["name"], "Warm")
    self.assertEqual(set(self.service.features.library["themes"]), {"Warm", "Dark"})
    self.assertFalse(self.errors())

  def test_export_import_round_trip_and_invalid_import_preserves_state(self):
    self.store.update({"barPosition": "left", "barSize": 48, "theme": "onedark"})
    file = self.directory / "profile.json"
    self.config("settings-export", {"path": file.as_uri(), "kind": "profile"})
    document = json.loads(file.read_text())
    self.assertNotIn("clipboardPaused", document["settings"])
    self.store.reset()
    self.config("settings-import", {"path": file.as_uri()})
    self.assertEqual(self.store.settings["barPosition"], "left")
    self.assertEqual(self.store.settings["theme"], "onedark")
    before = self.store.file.read_text()
    file.write_text(json.dumps({"version": 1, "type": "hyprlarp-profile", "settings": {"barSize": 1}}))
    self.config("settings-import", {"path": str(file)})
    self.assertEqual(self.store.file.read_text(), before)
    self.assertTrue(self.errors())

  def test_theme_export_import_preserves_actual_accent(self):
    self.store.update({"theme": "gruvbox", "accent": "#ffffff"})
    file = self.directory / "theme.json"
    self.config("settings-export", {"path": str(file), "kind": "theme"})
    self.store.reset()
    self.config("settings-import", {"path": str(file)})
    self.assertEqual(self.store.settings["customPalette"]["accent"], "#ffffff")

  def test_launcher_favorites_and_usage_survive_backend_restart(self):
    for action in ("launcher-favorite", "launcher-used", "launcher-used"):
      self.service.action({"action": action, "data": {"id": "Alacritty.desktop"}})
    loaded = json.loads((self.directory / "launcher.json").read_text())
    self.assertEqual(loaded["favorites"], ["Alacritty.desktop"])
    self.assertEqual(loaded["recent"][0]["count"], 2)
    self.assertFalse(self.errors())

  def test_clipboard_pin_survives_history_clear_and_is_copied_exactly(self):
    clipboard = self.service.clipboard_manager
    self.service.preview = False
    with patch.object(clipboard, "decode", return_value=b"preserved\ntext"), patch("backend.clipboard.subprocess.run"), patch("backend.service.optional", return_value="1\tpreserved text"):
      clipboard.handle("clipboard-pin", {"raw": "1\tpreserved text"})
    ident = next(iter(clipboard.state["pins"]))
    with patch("backend.service.command"), patch("backend.service.optional", return_value=""):
      clipboard.handle("clipboard-clear", {})
    self.assertEqual((clipboard.directory / (ident + ".data")).read_bytes(), b"preserved\ntext")
    with patch("backend.clipboard.subprocess.run") as run:
      clipboard.handle("clipboard-copy", {"pin": ident})
      self.assertEqual(run.call_args.kwargs["input"], b"preserved\ntext")

  def test_clipboard_retention_is_optional_and_does_not_expire_pins(self):
    self.assertNotIn("clipboard-expiry", poll_intervals(DEFAULTS, "", native_services=True))
    self.store.update({"clipboardRetentionHours": 1})
    self.assertEqual(poll_intervals(self.store.settings, "", native_services=True)["clipboard-expiry"], 60)
    clipboard = self.service.clipboard_manager
    self.service.preview = False
    clipboard.state["seen"]["1"] = int(time.time()) - 7200
    with patch("backend.service.optional", return_value="1\told\n2\tnew"), patch("backend.service.command") as command:
      clipboard.refresh(expire=True)
      command.assert_called_once_with(["cliphist", "delete"], input_text="1\told")
    self.assertNotIn("1", clipboard.state["seen"])
    self.assertIn("2", clipboard.state["seen"])

  def test_clipboard_pause_stops_watchers_without_disabling_history(self):
    self.service.preview = False
    self.store.update({"clipboardPaused": True})
    watcher = unittest.mock.Mock()
    watcher.poll.return_value = None
    self.service.watchers = [watcher]
    self.service.sync_watchers()
    watcher.terminate.assert_called_once()
    self.assertEqual(self.service.watchers, [])
    self.assertTrue(self.store.settings["clipboardEnabled"])

  def test_notification_rules_reject_unknown_fields(self):
    for value in ({"app": {"command": "bad"}}, {"app": {"popup": 1}}, {"": {"sound": True}}):
      with self.assertRaises(ValueError):
        validate_setting("notificationRules", value)

  @unittest.skipUnless(shutil.which("node"), "Node is optional for matcher regression tests")
  def test_fuzzy_typo_accents_and_ranking(self):
    subprocess.run(["node", str(ROOT / "tests/test_fuzzy.js")], check=True, capture_output=True, text=True)

  @unittest.skipUnless(shutil.which("node"), "Node is optional for module icon regression tests")
  def test_all_module_icons_exist(self):
    subprocess.run(["node", str(ROOT / "tests/test_module_icons.js")], check=True, capture_output=True, text=True)


class CaptureTests(unittest.TestCase):
  def test_active_window_geometry_includes_negative_monitor_coordinates(self):
    self.assertEqual(window_geometry({"at": [-1920, 20], "size": [800, 600]}), "-1920,20 800x600")
    for value in ({}, {"at": [0, 0], "size": [0, 0]}):
      with self.assertRaises(ValueError):
        window_geometry(value)

  def test_annotation_text_is_escaped_and_redaction_is_opaque(self):
    svg = annotations_svg([{"kind": "text", "x": 3, "y": 20, "x2": 3, "y2": 20, "text": "<script>&"},
      {"kind": "redact", "x": 30, "y": 30, "x2": 10, "y2": 10}], 100, 100)
    self.assertIn("&lt;script&gt;&amp;", svg)
    self.assertIn('width="20" height="20" fill="#000000"', svg)
    self.assertNotIn("opacity", svg)
    with self.assertRaises(ValueError):
      annotations_svg([{"kind": "redact", "x": float("nan"), "y": 0, "x2": 1, "y2": 1}], 100, 100)

  @unittest.skipUnless(shutil.which("magick"), "ImageMagick is optional")
  def test_saved_capture_has_real_crop_and_solid_hidden_pixels(self):
    with tempfile.TemporaryDirectory() as directory:
      service = Service(Store(Path(directory)), preview=False)
      service.emit = lambda *args: None
      capture = service.captures
      try:
        capture.directory.mkdir()
        source = capture.directory / "draft.png"
        subprocess.run(["magick", "-size", "100x80", "xc:white", str(source)], check=True, capture_output=True)
        capture.drafts["test"] = {"path": source, "width": 100, "height": 80}
        result = Path(directory) / "result.png"
        with patch.object(capture, "destination", return_value=result), patch.object(capture, "copy"):
          capture.handle("capture-save", {"token": "test",
            "operations": [{"kind": "redact", "x": 5, "y": 5, "x2": 35, "y2": 35}],
            "crop": {"x": 0, "y": 0, "width": 50, "height": 40}})
        dimensions = subprocess.run(["magick", "identify", "-format", "%w %h", str(result)], check=True, text=True, capture_output=True).stdout
        self.assertEqual(dimensions, "50 40")
        pixel = subprocess.run(["magick", str(result), "-format", "%[pixel:p{10,10}]", "info:"], check=True, text=True, capture_output=True).stdout
        self.assertIn("(0", pixel)
        self.assertNotIn("test", capture.drafts)
      finally:
        service.executor.shutdown(wait=True)
