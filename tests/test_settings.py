import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from backend.service import DEFAULTS, PALETTES, SETTINGS_HISTORY_LIMIT, Service, Store, palette_for, render_lock_config, validate_setting


class SettingsHistoryTests(unittest.TestCase):
  def setUp(self):
    self.temporary = tempfile.TemporaryDirectory()
    self.directory = Path(self.temporary.name)
    self.store = Store(self.directory)

  def tearDown(self):
    self.temporary.cleanup()

  def test_undo_and_redo_restore_complete_valid_configuration(self):
    changed = self.store.update({"theme": "oxocarbon", "barPosition": "left", "barSize": 48,
                 "barModules": ["clock", "launcher"], "moduleOpacities": {"clock": 0.5}})
    self.assertEqual(self.store.history_state(), {"undo": 1, "redo": 0})
    self.assertEqual(self.store.undo(), DEFAULTS)
    self.assertEqual(json.loads(self.store.file.read_text()), DEFAULTS)
    self.assertEqual(self.store.redo(), changed)
    self.assertEqual(json.loads(self.store.file.read_text()), changed)

  def test_new_edit_discards_redo_but_unchanged_edits_do_not(self):
    self.store.update({"barOpacity": 0.7})
    self.store.undo()
    self.store.update({"barOpacity": 1})
    self.assertEqual(self.store.history_state(), {"undo": 0, "redo": 1})
    self.store.update({"font": "Sans Serif"})
    self.assertEqual(self.store.history_state(), {"undo": 1, "redo": 0})

  def test_invalid_update_does_not_change_settings_or_history(self):
    original = self.store.update({"theme": "tokyonight"})
    original_file = self.store.file.read_text()
    with self.assertRaises(ValueError):
      self.store.update({"theme": "onedark", "barSize": 22})
    self.assertEqual(self.store.settings, original)
    self.assertEqual(self.store.file.read_text(), original_file)
    self.assertEqual(self.store.history_state(), {"undo": 1, "redo": 0})

  def test_failed_disk_writes_preserve_both_history_stacks(self):
    for operation in ["update", "undo", "redo", "reset"]:
      with self.subTest(operation=operation), tempfile.TemporaryDirectory() as directory:
        store = Store(Path(directory))
        store.update({"font": "Sans Serif"})
        if operation == "redo":
          store.undo()
        previous = copy.deepcopy(store.settings)
        history = copy.deepcopy((store.undo_stack, store.redo_stack))
        contents = store.file.read_text()
        with patch("backend.service.atomic_json", side_effect=OSError("disk full")):
          with self.assertRaises(OSError):
            if operation == "update":
              store.update({"font": "Monospace"})
            else:
              getattr(store, operation)()
        self.assertEqual(store.settings, previous)
        self.assertEqual((store.undo_stack, store.redo_stack), history)
        self.assertEqual(store.file.read_text(), contents)

  def test_reset_is_undoable_and_keeps_other_files(self):
    palette = {**DEFAULTS["customPalette"], "name": "Personal", "background": "#101820", "accent": "#e8d5b5"}
    previous = self.store.update({"customPalette": palette, "theme": "custom", "clipboardEnabled": False,
                  "barModules": [], "wallpaperDirectory": str(self.directory)})
    notifications = self.directory / "notifications.json"
    clipboard = self.directory / "clipboard-fixture.db"
    notifications.write_text('[{"summary":"Keep"}]')
    clipboard.write_bytes(b"clipboard fixture")
    self.assertEqual(self.store.reset(), DEFAULTS)
    self.assertEqual(self.store.undo(), previous)
    self.assertEqual(self.store.redo(), DEFAULTS)
    self.assertEqual(notifications.read_text(), '[{"summary":"Keep"}]')
    self.assertEqual(clipboard.read_bytes(), b"clipboard fixture")

  def test_reset_repairs_a_corrupt_file_even_when_defaults_are_loaded(self):
    self.store.file.write_text("broken json")
    store = Store(self.directory)
    self.assertTrue(store.warning)
    store.reset()
    self.assertEqual(json.loads(store.file.read_text()), DEFAULTS)
    self.assertEqual(store.history_state(), {"undo": 0, "redo": 0})

  def test_history_has_a_fixed_memory_bound(self):
    for number in range(SETTINGS_HISTORY_LIMIT + 10):
      self.store.update({"font": f"Font {number}"})
    self.assertEqual(self.store.history_state()["undo"], SETTINGS_HISTORY_LIMIT)
    for _ in range(SETTINGS_HISTORY_LIMIT):
      self.store.undo()
    self.assertEqual(self.store.settings["font"], "Font 9")
    self.assertEqual(self.store.history_state(), {"undo": 0, "redo": SETTINGS_HISTORY_LIMIT})
    for _ in range(SETTINGS_HISTORY_LIMIT):
      self.store.redo()
    self.assertEqual(self.store.settings["font"], f"Font {SETTINGS_HISTORY_LIMIT + 9}")

  def test_empty_history_is_a_noop_and_returned_values_are_isolated(self):
    self.assertEqual(self.store.undo(), DEFAULTS)
    self.assertEqual(self.store.redo(), DEFAULTS)
    self.assertFalse(self.store.file.exists())
    result = self.store.update({"theme": "onedark"})
    result["customPalette"]["text"] = "invalid"
    result["barModules"].clear()
    self.assertEqual(self.store.settings["customPalette"], DEFAULTS["customPalette"])
    self.assertEqual(self.store.undo(), DEFAULTS)

  def test_shell_panel_edits_are_not_added_to_configuration_history(self):
    self.store.update({"doNotDisturb": True}, record=False)
    self.assertEqual(self.store.history_state(), {"undo": 0, "redo": 0})
    self.assertTrue(self.store.undo()["doNotDisturb"])

  def test_shell_changes_survive_configuration_undo_and_redo(self):
    self.store.update({"theme": "oxocarbon", "font": "Sans Serif"})
    self.store.update({"doNotDisturb": True}, record=False)
    undone = self.store.undo()
    self.assertEqual(undone["theme"], "amoled")
    self.assertEqual(undone["font"], "Inter")
    self.assertTrue(undone["doNotDisturb"])
    redone = self.store.redo()
    self.assertEqual(redone["theme"], "oxocarbon")
    self.assertTrue(redone["doNotDisturb"])

  def test_external_edits_override_only_their_keys_in_both_history_stacks(self):
    self.store.update({"font": "Sans Serif", "doNotDisturb": True})
    self.store.update({"doNotDisturb": False}, record=False)
    self.assertEqual(self.store.undo()["font"], "Inter")
    self.assertFalse(self.store.settings["doNotDisturb"])
    self.store.update({"doNotDisturb": True}, record=False)
    self.assertEqual(self.store.redo()["font"], "Sans Serif")
    self.assertTrue(self.store.settings["doNotDisturb"])
    self.store.update({"font": "Monospace"}, record=False)
    self.assertEqual(self.store.history_state(), {"undo": 0, "redo": 0})


class PaletteTests(unittest.TestCase):
  def test_all_presets_and_custom_theme_are_valid_for_the_lock_screen(self):
    for name in [*PALETTES, "custom"]:
      with self.subTest(theme=name):
        self.assertEqual(validate_setting("theme", name), name)
        settings = {**DEFAULTS, "theme": name}
        palette = palette_for(settings)
        self.assertEqual(set(palette), set(DEFAULTS["customPalette"]))
        config = render_lock_config(settings)
        self.assertIn("$background = rgb(" + palette["background"][1:] + ")", config)
        self.assertIn("$foreground = rgb(" + palette["text"][1:] + ")", config)

  def test_custom_palette_is_normalized_and_persists_after_restart(self):
    with tempfile.TemporaryDirectory() as directory:
      store = Store(Path(directory))
      palette = {**DEFAULTS["customPalette"], "name": "  Personal  ", "background": "#AABBCC", "accent": "#123ABC"}
      store.update({"theme": "custom", "customPalette": palette})
      reloaded = Store(Path(directory))
      self.assertEqual(reloaded.settings["theme"], "custom")
      self.assertEqual(reloaded.settings["customPalette"]["name"], "Personal")
      self.assertEqual(reloaded.settings["customPalette"]["background"], "#aabbcc")
      self.assertEqual(reloaded.settings["accent"], "#123abc")
      self.assertEqual(reloaded.history_state(), {"undo": 0, "redo": 0})

  def test_custom_palette_rejects_missing_roles_names_and_invalid_colors(self):
    cases = []
    missing = copy.deepcopy(DEFAULTS["customPalette"])
    del missing["text"]
    cases.append(missing)
    cases.append({**DEFAULTS["customPalette"], "unknown": "#ffffff"})
    for name in ["", " " * 3, "x" * 41, "line\nbreak", 1]:
      cases.append({**DEFAULTS["customPalette"], "name": name})
    for color in ["red", "#fff", "#11223344", "#zzzzzz", None, 1]:
      cases.append({**DEFAULTS["customPalette"], "surface": color})
    for palette in cases:
      with self.subTest(palette=palette), self.assertRaises(ValueError):
        validate_setting("customPalette", palette)

  def test_presets_and_custom_accents_remain_independent(self):
    with tempfile.TemporaryDirectory() as directory:
      store = Store(Path(directory))
      original = copy.deepcopy(PALETTES)
      store.update({"theme": "oxocarbon"})
      self.assertEqual(store.settings["accent"], PALETTES["oxocarbon"]["accent"])
      store.update({"customPalette": {**DEFAULTS["customPalette"], "accent": "#123abc"}})
      self.assertEqual(store.settings["accent"], PALETTES["oxocarbon"]["accent"])
      store.update({"theme": "custom"})
      self.assertEqual(store.settings["accent"], "#123abc")
      store.update({"accent": "#abcdef"})
      self.assertEqual(store.settings["customPalette"]["accent"], "#abcdef")
      store.update({"theme": "tokyonight"})
      self.assertEqual(store.settings["accent"], PALETTES["tokyonight"]["accent"])
      self.assertEqual(store.settings["customPalette"]["accent"], "#abcdef")
      self.assertEqual(PALETTES, original)


class SettingsProtocolTests(unittest.TestCase):
  def test_settings_history_actions_are_serialized_before_acknowledgment(self):
    with tempfile.TemporaryDirectory() as directory:
      service = Service(Store(Path(directory)), preview=True, settings_only=True)
      events = []
      service.emit = lambda kind, data: events.append((kind, copy.deepcopy(data)))
      requests = [
        {"action": "settings-context", "data": {"focused": True}},
        {"action": "settings", "data": {"theme": "oxocarbon"}, "source": "config"},
        {"action": "settings-undo", "source": "config"},
        {"action": "settings-redo", "source": "config"},
        {"action": "settings-reset", "source": "config"},
        {"action": "settings-undo", "source": "config"}
      ]
      source = io.StringIO("\n".join(json.dumps(request) for request in requests))
      with patch("sys.stdin", source), patch.object(service, "poll"), patch.object(service, "sync_watchers"):
        service.serve()
      settings = [data for kind, data in events if kind == "settings"]
      self.assertEqual([entry["theme"] for entry in settings], ["amoled", "oxocarbon", "amoled", "oxocarbon", "amoled", "oxocarbon"])
      states = [data for kind, data in events if kind == "settings-history"]
      self.assertEqual(states[-1], {"undo": 1, "redo": 1})
      self.assertFalse(any(kind == "error" for kind, _ in events))

  def test_restore_requires_the_focused_configuration_window_and_source(self):
    for action in ["settings-undo", "settings-redo", "settings-reset"]:
      for focused, origin in [(False, "config"), (True, "shell")]:
        with self.subTest(action=action, focused=focused, source=origin), tempfile.TemporaryDirectory() as directory:
          service = Service(Store(Path(directory)), preview=True)
          events = []
          service.emit = lambda kind, data: events.append((kind, data))
          service.store.update({"theme": "oxocarbon"})
          if action == "settings-redo":
            service.store.undo()
          before = copy.deepcopy(service.store.settings)
          history = service.store.history_state()
          contents = service.store.file.read_text()
          try:
            service.action({"action": "settings-context", "data": {"focused": focused}})
            service.action({"action": action, "source": origin})
            self.assertEqual(service.store.settings, before)
            self.assertEqual(service.store.history_state(), history)
            self.assertEqual(service.store.file.read_text(), contents)
            self.assertTrue(any(kind == "settings-rejected" for kind, _ in events))
          finally:
            service.executor.shutdown(wait=True)

  def test_shell_updates_remain_untracked_while_configuration_is_focused(self):
    with tempfile.TemporaryDirectory() as directory:
      service = Service(Store(Path(directory)), preview=True)
      service.emit = lambda *_: None
      try:
        service.action({"action": "settings-context", "data": {"focused": True}})
        service.action({"action": "settings", "data": {"doNotDisturb": True}})
        self.assertEqual(service.store.history_state(), {"undo": 0, "redo": 0})
        service.action({"action": "settings-undo", "source": "config"})
        self.assertTrue(service.store.settings["doNotDisturb"])
      finally:
        service.executor.shutdown(wait=True)

  def test_rejected_settings_acknowledge_current_state_once(self):
    with tempfile.TemporaryDirectory() as directory:
      service = Service(Store(Path(directory)), preview=True)
      events = []
      service.emit = lambda kind, data: events.append((kind, data))
      try:
        service.action({"action": "settings", "data": {"barSize": 22}})
        self.assertEqual(len([kind for kind, _ in events if kind == "settings"]), 1)
        self.assertIn(("settings-rejected", {"action": "settings"}), events)
        self.assertEqual(service.store.settings, DEFAULTS)
      finally:
        service.executor.shutdown(wait=True)


if __name__ == "__main__":
  unittest.main()
