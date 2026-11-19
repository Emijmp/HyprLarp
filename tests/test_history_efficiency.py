"""History updates preserve immutable snapshots and remain atomic on failure."""

import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from backend.service import Store
from backend.revisions import VERSION_LIMIT


class HistoryEfficiencyTests(unittest.TestCase):
  def setUp(self):
    self.temporary = tempfile.TemporaryDirectory()
    self.addCleanup(self.temporary.cleanup)
    self.store = Store(Path(self.temporary.name))
    for index in range(VERSION_LIMIT + 2):
      self.store.update({"font": "Font " + str(index)})

  def test_saving_a_full_history_does_not_modify_existing_snapshots(self):
    previous = self.store.revisions.document
    original = copy.deepcopy(previous)
    self.store.update({"barPosition": "bottom"})
    self.assertEqual(previous, original)
    current = self.store.revisions.document
    self.assertEqual(len(current["revisions"]), VERSION_LIMIT)
    self.assertEqual(current["revisions"][:-1], original["revisions"][1:])
    public = self.store.revisions.get(current["revisions"][0]["id"])
    public["settings"]["shortcuts"]["lock"] = "ALT, L"
    self.assertNotEqual(public, self.store.revisions.get(public["id"]))

  def test_failed_write_cannot_trim_or_mutate_the_previous_document(self):
    previous = self.store.revisions.document
    original = copy.deepcopy(previous)
    content = self.store.revisions.path.read_bytes()
    with patch("backend.revisions.atomic_json", side_effect=OSError("disk full")):
      self.store.update({"barPosition": "bottom"})
    self.assertIs(self.store.revisions.document, previous)
    self.assertEqual(previous, original)
    self.assertEqual(self.store.revisions.path.read_bytes(), content)
    self.assertEqual(self.store.settings["barPosition"], "bottom")

  def test_new_snapshots_and_undo_are_isolated_from_mutable_inputs(self):
    custom = copy.deepcopy(self.store.settings["shortcuts"])
    custom["lock"] = "ALT, L"
    self.store.update({"shortcuts": custom})
    document = copy.deepcopy(self.store.revisions.document)
    custom["lock"] = "ALT, K"
    self.store.undo_stack[-1]["after"]["shortcuts"]["lock"] = "ALT, J"
    self.assertEqual(self.store.revisions.document, document)
    self.assertEqual(document["revisions"][-1]["settings"]["shortcuts"]["lock"], "ALT, L")
