import copy
import json
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import Mock, patch

from backend.service import DEFAULTS, Service, Store
from backend.revisions import CAPTURE_SHORTCUT, VERSION_LIMIT, fingerprint


class PersistentHistoryTests(unittest.TestCase):
  def setUp(self):
    self.temporary = tempfile.TemporaryDirectory()
    self.addCleanup(self.temporary.cleanup)
    self.directory = Path(self.temporary.name)
    self.store = Store(self.directory)

  def test_restart_restores_undo_and_redo_without_reverting_shell_changes(self):
    self.store.update({"font": "Sans Serif", "theme": "oxocarbon"})
    self.store.update({"doNotDisturb": True}, record=False)
    restarted = Store(self.directory)
    self.assertEqual(restarted.history_state(), {"undo": 1, "redo": 0})
    self.assertEqual(restarted.undo()["font"], DEFAULTS["font"])
    restarted = Store(self.directory)
    self.assertTrue(restarted.settings["doNotDisturb"])
    self.assertEqual(restarted.history_state(), {"undo": 0, "redo": 1})
    self.assertEqual(restarted.redo()["font"], "Sans Serif")

  def test_external_file_edits_invalidate_undo_but_keep_restorable_versions(self):
    self.store.update({"font": "Sans Serif"})
    saved = json.loads(self.store.file.read_text())
    saved["font"] = "External font"
    self.store.file.write_text(json.dumps(saved))
    restarted = Store(self.directory)
    self.assertEqual(restarted.history_state(), {"undo": 0, "redo": 0})
    self.assertEqual(restarted.undo()["font"], "External font")
    self.assertEqual(len(restarted.revisions.listing(restarted.settings)), 2)

  def test_corrupt_journal_does_not_discard_settings_and_next_edit_repairs_it(self):
    self.store.update({"font": "Sans Serif"})
    self.store.revisions.path.write_text("broken json")
    restarted = Store(self.directory)
    self.assertEqual(restarted.settings["font"], "Sans Serif")
    self.assertTrue(restarted.warning)
    restarted.update({"font": "Monospace"})
    self.assertEqual(Store(self.directory).history_state()["undo"], 1)

  def test_history_failure_keeps_successfully_saved_preferences(self):
    with patch("backend.revisions.atomic_json", side_effect=OSError("disk full")):
      self.store.update({"font": "Monospace"})
    self.assertEqual(json.loads(self.store.file.read_text())["font"], "Monospace")
    self.assertIn("historial", self.store.warning)

  def test_history_failure_is_reported_to_the_ui_without_rejecting_saved_settings(self):
    service = Service(self.store, preview=True)
    self.addCleanup(service.executor.shutdown, wait=True)
    events = []
    service.emit = lambda kind, data: events.append((kind, data))
    service.configuration_focused = True
    with patch("backend.revisions.atomic_json", side_effect=OSError("disk full")):
      service.action({"action": "settings", "source": "config", "data": {"font": "Monospace"}})
    self.assertEqual(self.store.settings["font"], "Monospace")
    self.assertTrue(any(kind == "error" and "historial" in data for kind, data in events))
    self.assertFalse(any(kind == "settings-rejected" for kind, data in events))

  def test_versions_are_bounded_private_and_skip_transient_changes(self):
    for value in range(VERSION_LIMIT + 4):
      self.store.update({"font": "Font " + str(value)})
    versions = self.store.revisions.listing(self.store.settings)
    self.assertEqual(len(versions), VERSION_LIMIT)
    path = self.store.revisions.path
    self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
    self.store.update({"doNotDisturb": True}, record=False)
    self.assertEqual(len(self.store.revisions.listing(self.store.settings)), VERSION_LIMIT)
    self.assertNotIn("doNotDisturb", self.store.revisions.get(versions[0]["id"])["settings"])
    before = path.stat().st_mtime_ns
    self.store.update({"font": self.store.settings["font"]})
    self.assertEqual(path.stat().st_mtime_ns, before)

  def test_restore_requires_configuration_focus_and_is_undoable(self):
    self.store.update({"font": "Sans Serif"})
    initial = self.store.revisions.listing(self.store.settings)[-1]["id"]
    service = Service(self.store, preview=True)
    self.addCleanup(service.executor.shutdown, wait=True)
    service.emit = Mock()
    request = {"action": "settings-restore-revision", "source": "config", "data": {"id": initial}}
    service.action(request)
    self.assertEqual(self.store.settings["font"], "Sans Serif")
    service.configuration_focused = True
    service.action(request)
    self.assertEqual(self.store.settings["font"], DEFAULTS["font"])
    self.assertEqual(self.store.undo()["font"], "Sans Serif")

  def test_comparison_is_isolated_and_does_not_write_settings(self):
    self.store.update({"font": "Sans Serif"})
    version = self.store.revisions.listing(self.store.settings)[-1]["id"]
    previous = self.store.file.read_bytes()
    comparison = self.store.revisions.compare(version, self.store.settings)
    self.assertEqual(comparison["changes"][0]["key"], "font")
    self.assertEqual(self.store.file.read_bytes(), previous)
    item = self.store.revisions.get(version)
    item["settings"]["font"] = "mutated"
    self.assertEqual(self.store.revisions.get(version)["settings"]["font"], DEFAULTS["font"])

  def test_missing_old_wallpaper_does_not_destroy_all_revisions(self):
    image = self.directory / "old.png"
    image.write_bytes(b"fixture")
    self.store.update({"wallpaper": str(image)})
    self.store.update({"wallpaper": ""})
    image.unlink()
    restarted = Store(self.directory)
    self.assertGreaterEqual(len(restarted.revisions.listing(restarted.settings)), 3)
    self.assertEqual(restarted.settings["wallpaper"], "")

  def legacy_capture_history(self):
    settings = copy.deepcopy(self.store.settings)
    settings["shortcuts"].pop(CAPTURE_SHORTCUT)
    history = json.loads(self.store.revisions.path.read_text())
    history["head"] = fingerprint(settings)
    values = [item["settings"] for item in history["revisions"]]
    for name in ("undo", "redo"):
      for entry in history[name]:
        values.extend((entry["before"], entry["after"]))
    for value in values:
      if isinstance(value.get("shortcuts"), dict):
        value["shortcuts"].pop(CAPTURE_SHORTCUT, None)
    self.store.file.write_text(json.dumps(settings))
    self.store.revisions.path.write_text(json.dumps(history))
    return self.store.revisions.path.read_bytes()

  def test_new_capture_shortcut_preserves_legacy_versions_undo_redo_and_disk_bytes(self):
    shortcuts = {**self.store.settings["shortcuts"], "screenshot-region": "ALT, Print"}
    self.store.update({"shortcuts": shortcuts})
    self.store.update({"font": "Monospace"})
    self.store.undo()
    unchanged = self.legacy_capture_history()
    restarted = Store(self.directory)
    self.assertEqual(restarted.warning, "")
    self.assertEqual(restarted.history_state(), {"undo": 1, "redo": 1})
    self.assertEqual(restarted.revisions.path.read_bytes(), unchanged)
    self.assertEqual(restarted.settings["shortcuts"][CAPTURE_SHORTCUT], "CTRL, Print")
    initial = restarted.revisions.listing(restarted.settings)[-1]["id"]
    self.assertEqual(restarted.revisions.get(initial)["settings"]["shortcuts"][CAPTURE_SHORTCUT], "CTRL, Print")
    self.assertEqual(restarted.undo()["shortcuts"]["screenshot-region"], ", Print")
    self.assertEqual(restarted.redo()["shortcuts"]["screenshot-region"], "ALT, Print")
    self.assertEqual(restarted.redo()["font"], "Monospace")
    persisted = Store(self.directory)
    self.assertEqual(persisted.warning, "")
    self.assertEqual(persisted.history_state(), {"undo": 2, "redo": 0})

  def test_legacy_shortcut_undo_uses_enabled_custom_binding_context(self):
    self.store.update({"shortcuts": {**self.store.settings["shortcuts"], CAPTURE_SHORTCUT: ""}})
    custom = [{"id": "my-print", "name": "My capture", "chord": "CTRL, Print", "type": "command", "command": "personal-capture"}]
    self.store.update({"customBindings": custom})
    self.store.update({"shortcuts": {**self.store.settings["shortcuts"], "screenshot-region": "ALT, Print"}})
    # Keep the two existing entries relevant to shortcut/custom context.
    self.store.undo_stack = self.store.undo_stack[-2:]
    self.store._save_history(self.store.settings, capture=False)
    unchanged = self.legacy_capture_history()
    restarted = Store(self.directory)
    self.assertEqual(restarted.warning, "")
    self.assertEqual(restarted.revisions.path.read_bytes(), unchanged)
    self.assertEqual(restarted.settings["shortcuts"][CAPTURE_SHORTCUT], "")
    self.assertEqual(len(restarted.undo()["customBindings"]), 1)
    self.assertEqual(restarted.settings["shortcuts"][CAPTURE_SHORTCUT], "")
    self.assertEqual(restarted.redo()["shortcuts"][CAPTURE_SHORTCUT], "")
    for item in restarted.revisions.document["revisions"]:
      if item["settings"]["customBindings"]:
        self.assertEqual(item["settings"]["shortcuts"][CAPTURE_SHORTCUT], "")

  def test_legacy_capture_migration_does_not_accept_unknown_or_other_missing_shortcuts(self):
    self.store.update({"font": "Monospace"})
    self.legacy_capture_history()
    document = json.loads(self.store.revisions.path.read_text())
    for mutation in ("unknown", "missing"):
      corrupted = copy.deepcopy(document)
      shortcuts = corrupted["revisions"][0]["settings"]["shortcuts"]
      if mutation == "unknown":
        shortcuts["screenshot-unknown"] = "ALT, Print"
      else:
        shortcuts.pop("launcher")
      self.store.revisions.path.write_text(json.dumps(corrupted))
      restarted = Store(self.directory)
      self.assertTrue(restarted.warning)
      self.assertEqual(restarted.history_state(), {"undo": 0, "redo": 0})

  def test_external_change_to_new_capture_shortcut_invalidates_legacy_undo(self):
    self.store.update({"font": "Monospace"})
    self.legacy_capture_history()
    settings = json.loads(self.store.file.read_text())
    settings["shortcuts"][CAPTURE_SHORTCUT] = "ALT CTRL, Print"
    self.store.file.write_text(json.dumps(settings))
    restarted = Store(self.directory)
    self.assertEqual(restarted.warning, "")
    self.assertEqual(restarted.history_state(), {"undo": 0, "redo": 0})
    self.assertTrue(restarted.revisions.listing(restarted.settings))

  def test_legacy_head_without_full_snapshots_still_recovers_partial_undo(self):
    self.store.update({"font": "Monospace"})
    self.legacy_capture_history()
    document = json.loads(self.store.revisions.path.read_text())
    document["revisions"] = []
    self.store.revisions.path.write_text(json.dumps(document))
    unchanged = self.store.revisions.path.read_bytes()
    restarted = Store(self.directory)
    self.assertEqual(restarted.warning, "")
    self.assertEqual(restarted.history_state(), {"undo": 1, "redo": 0})
    self.assertEqual(restarted.revisions.path.read_bytes(), unchanged)
    self.assertEqual(restarted.undo()["font"], DEFAULTS["font"])
