import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from backend.onboarding import Onboarding
from backend.persistence import atomic_json
from backend.service import Service, Store
from backend.version import VERSION


class FirstRunStateTests(unittest.TestCase):
  def setUp(self):
    self.temporary = tempfile.TemporaryDirectory()
    self.root = Path(self.temporary.name)
    self.directory = self.root / "config"
    self.directory.mkdir()

  def tearDown(self):
    self.temporary.cleanup()

  def test_first_start_is_pending_without_creating_any_files(self):
    state = Onboarding(self.directory, self.root)
    self.assertEqual(state.snapshot(), {"needed": True, "status": "pending", "readOnly": False, "error": ""})
    self.assertEqual(list(self.directory.iterdir()), [])

  def test_existing_preferences_do_not_trigger_the_assistant(self):
    file = self.directory / "settings.json"
    file.write_text('{"theme":"gruvbox"}')
    original = file.read_bytes()
    self.assertEqual(Onboarding(self.directory, self.root).snapshot()["status"], "existing")
    self.assertFalse(Onboarding(self.directory, self.root).snapshot()["needed"])
    self.assertEqual(file.read_bytes(), original)

  def test_installer_flag_survives_defaults_written_before_first_launch(self):
    (self.directory / "settings.json").write_text("{}")
    marker = self.root / ".hyprlarp-install.json"
    marker.write_text(json.dumps({"type": "hyprlarp-install", "version": 1, "first_run": True}))
    self.assertTrue(Onboarding(self.directory, self.root).snapshot()["needed"])
    for flag in [False, 1, "yes", None]:
      marker.write_text(json.dumps({"type": "hyprlarp-install", "version": 1, "first_run": flag}))
      self.assertFalse(Onboarding(self.directory, self.root).snapshot()["needed"])

  def test_preview_and_standalone_settings_never_automatically_prompt(self):
    for automatic in [True, False]:
      state = Onboarding(self.directory, self.root, automatic=automatic)
      self.assertEqual(state.snapshot()["needed"], automatic)
      self.assertFalse(state.file.exists())

  def test_system_package_tracks_first_run_per_user(self):
    (self.directory / "settings.json").write_text("{}")
    marker = self.directory / ".hyprlarp-session.json"
    marker.write_text(json.dumps({"type": "hyprlarp-session", "version": 1, "first_run": True}))
    self.assertTrue(Onboarding(self.directory, self.root).snapshot()["needed"])
    marker.write_text(json.dumps({"type": "hyprlarp-session", "version": 1, "first_run": False}))
    self.assertFalse(Onboarding(self.directory, self.root).snapshot()["needed"])

  def test_completed_and_skipped_states_prevent_further_automatic_prompts(self):
    for status in ["completed", "skipped"]:
      state = Onboarding(self.directory, self.root)
      state.finish(status, VERSION)
      loaded = Onboarding(self.directory, self.root)
      self.assertFalse(loaded.snapshot()["needed"])
      self.assertEqual(loaded.snapshot()["status"], status)
      self.assertEqual(json.loads(state.file.read_text())["release"], VERSION)
      self.assertEqual(state.file.stat().st_mode & 0o777, 0o600)

  def test_malformed_and_future_states_are_preserved_and_read_only(self):
    file = self.directory / "onboarding.json"
    for content in ["{broken", "[]", '{"version":true,"status":"skipped"}',
      '{"version":2,"status":"completed","future":42}',
      '{"version":1,"status":[]}', '{"version":1,"status":"skipped","future":42}']:
      with self.subTest(content=content):
        file.write_text(content)
        state = Onboarding(self.directory, self.root)
        self.assertTrue(state.snapshot()["readOnly"])
        self.assertFalse(state.snapshot()["needed"])
        with self.assertRaises(ValueError):
          state.finish("completed", VERSION)
        self.assertEqual(file.read_text(), content)

  def test_symlink_state_is_preserved_without_writing_its_target(self):
    target = self.root / "unrelated.json"
    target.write_text("keep")
    (self.directory / "onboarding.json").symlink_to(target)
    state = Onboarding(self.directory, self.root)
    self.assertTrue(state.snapshot()["readOnly"])
    with self.assertRaises(ValueError):
      state.finish("skipped", VERSION)
    self.assertEqual(target.read_text(), "keep")

  def test_future_state_created_after_start_is_not_overwritten(self):
    state = Onboarding(self.directory, self.root)
    content = '{"version":9,"status":"completed"}'
    state.file.write_text(content)
    with self.assertRaises(ValueError):
      state.finish("skipped", VERSION)
    self.assertEqual(state.file.read_text(), content)


class FirstRunActionTests(unittest.TestCase):
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

  def complete(self, updates):
    self.service.action({"action": "onboarding-complete", "data": {"updates": updates}})

  def errors(self):
    return [data for kind, data in self.events if kind == "action-error"]

  def test_completion_saves_only_selected_preferences_and_can_be_undone(self):
    wallpapers = self.directory / "wallpapers"
    wallpapers.mkdir()
    self.store.update({"wallpaperDirectory": str(wallpapers), "panelOpacity": 0.85})
    before = copy.deepcopy(self.store.settings)
    undo_count = len(self.store.undo_stack)
    self.complete({"theme": "paper", "panelLayout": "centered", "performanceMode": "efficient",
      "accessibilityHighContrast": True})
    self.assertFalse(self.errors())
    expected = {**before, "theme": "paper", "panelLayout": "centered",
      "performanceMode": "efficient", "accessibilityHighContrast": True}
    # The theme's accent is selected through the normal settings pipeline.
    from backend.settings_schema import PALETTES
    expected["accent"] = PALETTES["paper"]["accent"]
    self.assertEqual(self.store.settings, expected)
    self.assertEqual(len(self.store.undo_stack), undo_count + 1)
    self.assertEqual(self.service.onboarding.snapshot()["status"], "completed")
    self.store.undo()
    self.assertEqual(self.store.settings, before)
    self.assertIn(("done", {"action": "onboarding-complete"}), self.events)

  def test_pending_shortcuts_and_live_bindings_are_never_applied(self):
    shortcuts = copy.deepcopy(self.store.settings["shortcuts"])
    shortcuts["lock"] = "SUPER SHIFT, L"
    self.store.update({"shortcuts": shortcuts, "customBindings": [{"id": "fullscreen", "name": "Pantalla completa",
      "chord": "SUPER, F", "type": "command", "command": "hyprctl dispatch fullscreen"}]})
    custom = copy.deepcopy(self.store.settings["customBindings"])
    file = self.directory / "bindings.lua"
    file.write_text("-- active Super+L binding stays here\n")
    metadata = file.stat()
    content = file.read_bytes()
    with patch("backend.service.command", side_effect=AssertionError("No native commands expected")):
      self.complete({"panelStyle": "flat"})
    self.assertFalse(self.errors())
    self.assertEqual(self.store.settings["shortcuts"], shortcuts)
    self.assertEqual(self.store.settings["customBindings"], custom)
    self.assertEqual(file.read_bytes(), content)
    self.assertEqual(file.stat().st_ino, metadata.st_ino)

  def test_skip_changes_no_configuration_and_remains_skipped_after_restart(self):
    self.store.update({"barPosition": "bottom"})
    before = {file.name: file.read_bytes() for file in self.directory.iterdir() if file.is_file()}
    self.service.action({"action": "onboarding-skip"})
    self.assertFalse(self.errors())
    self.assertEqual(self.service.onboarding.snapshot()["status"], "skipped")
    for name, content in before.items():
      self.assertEqual((self.directory / name).read_bytes(), content)
    self.assertFalse(Onboarding(self.directory, self.directory).snapshot()["needed"])

  def test_invalid_updates_are_rejected_without_settings_or_completion(self):
    for updates in [{"theme": "invalid"}, {"shortcuts": {}}, {"wallpaper": "/tmp/changed"},
      {"version": 99}, {"barPosition": "bottom", "accessibilityTextScale": 99}, []]:
      with self.subTest(updates=updates):
        self.events.clear()
        self.complete(updates)
        self.assertTrue(self.errors())
        self.assertFalse(self.service.onboarding.file.exists())
        self.assertFalse(self.store.file.exists())
        self.assertFalse(self.store.undo_stack)

  def test_settings_write_failure_does_not_mark_completion(self):
    self.store.write = lambda *args: (_ for _ in ()).throw(OSError("disk full"))
    original = copy.deepcopy(self.store.settings)
    self.complete({"panelStyle": "flat"})
    self.assertTrue(self.errors())
    self.assertFalse(self.service.onboarding.file.exists())
    self.assertEqual(self.store.settings, original)
    self.assertFalse(self.store.undo_stack)

  def test_state_write_failure_keeps_saved_choices_and_allows_retry(self):
    self.service.onboarding.write = lambda *args: (_ for _ in ()).throw(OSError("disk full"))
    self.complete({"panelStyle": "flat"})
    self.assertTrue(self.errors())
    self.assertEqual(self.store.settings["panelStyle"], "flat")
    self.assertFalse(self.service.onboarding.file.exists())
    self.assertEqual(len(self.store.undo_stack), 1)
    self.service.onboarding.write = atomic_json
    self.events.clear()
    self.complete({"panelStyle": "flat"})
    self.assertFalse(self.errors())
    self.assertEqual(len(self.store.undo_stack), 1)
    self.assertEqual(self.service.onboarding.snapshot()["status"], "completed")

  def test_future_state_prevents_both_preferences_and_state_changes(self):
    content = '{"version":7,"status":"completed","future":true}'
    self.service.onboarding.file.write_text(content)
    self.complete({"panelStyle": "flat"})
    self.assertTrue(self.errors())
    self.assertFalse(self.store.file.exists())
    self.assertEqual(self.service.onboarding.file.read_text(), content)

  def test_skip_rejects_hidden_updates(self):
    self.service.action({"action": "onboarding-skip", "data": {"updates": {"theme": "paper"}}})
    self.assertTrue(self.errors())
    self.assertFalse(self.service.onboarding.file.exists())
    self.assertFalse(self.store.file.exists())
