import copy
import json
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import Mock, patch

from backend.service import DEFAULTS, Service, Store
from backend.revisions import CAPTURE_SHORTCUT, HISTORY_VERSION, LEGACY_DEFAULTS, VERSION_LIMIT, fingerprint


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
    history["version"] = 1
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

  def legacy_visual_history(self, removed=None):
    self.legacy_capture_history()
    removed = set(LEGACY_DEFAULTS) if removed is None else set(removed)
    settings = json.loads(self.store.file.read_text())
    history = json.loads(self.store.revisions.path.read_text())
    for key in removed:
      settings.pop(key, None)
    history["head"] = fingerprint(settings)
    for revision in history["revisions"]:
      for key in removed:
        revision["settings"].pop(key, None)
    self.store.file.write_text(json.dumps(settings))
    self.store.revisions.path.write_text(json.dumps(history))
    return self.store.file.read_bytes(), self.store.revisions.path.read_bytes()

  def test_legacy_visual_history_preserves_versions_and_undo_redo_without_writes(self):
    self.store.update({"font": "Monospace", "theme": "oxocarbon"})
    self.store.update({"barSize": 50})
    self.store.undo()
    before = self.legacy_visual_history()
    original = json.loads(before[1])
    restarted = Store(self.directory)
    self.assertEqual(restarted.warning, "")
    self.assertEqual(restarted.history_state(), {"undo": 1, "redo": 1})
    self.assertEqual((restarted.file.read_bytes(), restarted.revisions.path.read_bytes()), before)
    self.assertEqual(restarted.revisions.document["version"], HISTORY_VERSION)
    migrated = restarted.revisions.document["revisions"]
    self.assertEqual([v["id"] for v in migrated], [v["id"] for v in original["revisions"]])
    for old, new in zip(original["revisions"], migrated):
      for field in ("id", "label", "time"):
        self.assertEqual(new[field], old[field])
      for key, value in old["settings"].items():
        if key != "shortcuts":
          self.assertEqual(new["settings"][key], value)
      for key, value in LEGACY_DEFAULTS.items():
        self.assertEqual(new["settings"][key], value)
    self.assertEqual(restarted.undo()["font"], DEFAULTS["font"])
    self.assertEqual(restarted.redo()["font"], "Monospace")
    self.assertEqual(restarted.redo()["barSize"], 50)
    persisted = json.loads(restarted.revisions.path.read_text())
    self.assertEqual(persisted["version"], HISTORY_VERSION)
    self.assertEqual(Store(self.directory).history_state(), {"undo": 2, "redo": 0})

  def test_mixed_legacy_snapshot_schemas_match_the_head_schema(self):
    self.store.update({"font": "Monospace"})
    self.store.update({"barSize": 50})
    removed = set(LEGACY_DEFAULTS) - {"accessibilityTextScale", "accessibilityHighContrast",
      "accessibilityReducedMotion", "accessibilityLargeTargets"}
    self.legacy_visual_history(removed)
    history = json.loads(self.store.revisions.path.read_text())
    for key in LEGACY_DEFAULTS:
      history["revisions"][0]["settings"].pop(key, None)
    self.store.revisions.path.write_text(json.dumps(history))
    restarted = Store(self.directory)
    self.assertEqual(restarted.warning, "")
    self.assertEqual(restarted.history_state(), {"undo": 2, "redo": 0})
    self.assertEqual(len(restarted.revisions.document["revisions"]), len(history["revisions"]))

  def test_legacy_visual_head_without_snapshots_preserves_partial_undo(self):
    self.store.update({"font": "Monospace"})
    removed = set(LEGACY_DEFAULTS) - {"accessibilityTextScale", "accessibilityHighContrast",
      "accessibilityReducedMotion", "accessibilityLargeTargets"}
    self.legacy_visual_history(removed)
    history = json.loads(self.store.revisions.path.read_text())
    history["revisions"] = []
    self.store.revisions.path.write_text(json.dumps(history))
    restarted = Store(self.directory)
    self.assertEqual(restarted.warning, "")
    self.assertEqual(restarted.history_state(), {"undo": 1, "redo": 0})
    self.assertEqual(restarted.undo()["font"], DEFAULTS["font"])

  def test_external_edits_to_new_defaults_cannot_be_hidden_by_legacy_head_matching(self):
    self.store.update({"font": "Monospace"})
    self.legacy_visual_history()
    original = json.loads(self.store.file.read_text())
    for key, value in (("panelLayout", "centered"), ("themeScheduleEnabled", True),
        ("performanceMode", "efficient"), ("accessibilityMinimumFontSize", 16)):
      settings = {**original, key: value}
      self.store.file.write_text(json.dumps(settings))
      restarted = Store(self.directory)
      self.assertEqual(restarted.warning, "")
      self.assertEqual(restarted.settings[key], value)
      self.assertEqual(restarted.history_state(), {"undo": 0, "redo": 0})
      self.assertTrue(restarted.revisions.listing(restarted.settings))

  def test_legacy_migration_rejects_unknown_missing_and_invalid_existing_values(self):
    self.store.update({"font": "Monospace"})
    self.legacy_visual_history()
    document = json.loads(self.store.revisions.path.read_text())
    for mutation in ("unknown", "missing", "invalid"):
      with self.subTest(mutation=mutation):
        corrupted = copy.deepcopy(document)
        values = corrupted["revisions"][0]["settings"]
        if mutation == "unknown":
          values["futurePanelOption"] = True
        elif mutation == "missing":
          values.pop("font")
        else:
          values["panelBlur"] = "yes"
        self.store.revisions.path.write_text(json.dumps(corrupted))
        unchanged = self.store.revisions.path.read_bytes()
        restarted = Store(self.directory)
        self.assertTrue(restarted.warning)
        self.assertEqual(restarted.settings["font"], "Monospace")
        self.assertEqual(restarted.history_state(), {"undo": 0, "redo": 0})
        self.assertEqual(restarted.revisions.path.read_bytes(), unchanged)

  def test_current_schema_does_not_silently_repair_truncated_snapshots(self):
    self.store.update({"font": "Monospace"})
    document = json.loads(self.store.revisions.path.read_text())
    self.assertEqual(document["version"], HISTORY_VERSION)
    document["revisions"][0]["settings"].pop("panelLayout")
    self.store.revisions.path.write_text(json.dumps(document))
    restarted = Store(self.directory)
    self.assertTrue(restarted.warning)
    self.assertEqual(restarted.history_state(), {"undo": 0, "redo": 0})

  def test_future_or_boolean_schema_versions_are_rejected_without_modification(self):
    self.store.update({"font": "Monospace"})
    document = json.loads(self.store.revisions.path.read_text())
    for version in (HISTORY_VERSION + 1, True, "1"):
      with self.subTest(version=version):
        document["version"] = version
        self.store.revisions.path.write_text(json.dumps(document))
        unchanged = self.store.revisions.path.read_bytes()
        restarted = Store(self.directory)
        self.assertTrue(restarted.warning)
        self.assertEqual(restarted.settings["font"], "Monospace")
        self.assertEqual(restarted.revisions.path.read_bytes(), unchanged)

  def test_settings_edits_preserve_a_newer_unsupported_journal(self):
    self.store.update({"font": "Monospace"})
    document = json.loads(self.store.revisions.path.read_text())
    document["version"] = HISTORY_VERSION + 1
    self.store.revisions.path.write_text(json.dumps(document))
    unchanged = self.store.revisions.path.read_bytes()
    restarted = Store(self.directory)
    self.assertTrue(restarted.revisions.read_only)
    self.assertIn("posterior", restarted.warning)
    restarted.update({"font": "Sans Serif"})
    self.assertEqual(json.loads(restarted.file.read_text())["font"], "Sans Serif")
    self.assertEqual(restarted.revisions.path.read_bytes(), unchanged)
    self.assertIn("posterior", restarted.warning)
