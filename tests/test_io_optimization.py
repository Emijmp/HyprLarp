"""Bounded file results and icon fallbacks preserve their user-visible ordering."""

from contextlib import contextmanager
from pathlib import Path
import os
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch

from backend import service as api
from backend.icons import IconResolver
from backend.launcher import LauncherSearch, MAX_RESULTS


class BoundedSearchTests(unittest.TestCase):
  def setUp(self):
    self.temporary = tempfile.TemporaryDirectory()
    self.addCleanup(self.temporary.cleanup)
    self.home = Path(self.temporary.name)
    self.service = Mock()
    self.service.stopping = threading.Event()
    self.search = LauncherSearch(self.service, api, home=self.home)
    self.search.token = "current"

  def test_common_query_preserves_complete_ranking_and_stable_ties(self):
    entries = [("document " + str(i % 137), "Document " + str(i), str(self.home / str(i)), i % 3 == 0)
      for i in range(5000)]
    entries += [("a document first", "Other", str(self.home / "other"), True)]
    self.search.index, self.search.index_at = entries, time.monotonic()
    expected = sorted(entries, key=lambda item: (not item[0].startswith("document"), not item[3], item[0]))
    result, truncated = self.search.files("document", "current")
    self.assertEqual(result, self.search.results(expected))
    self.assertEqual(len(result), MAX_RESULTS)
    self.assertTrue(truncated)

  def test_path_completion_stops_after_the_visible_page_and_one_extra_match(self):
    for index in range(100):
      (self.home / ("report-" + str(index))).touch()
    native = os.scandir
    expected = [entry.name for entry in native(self.home)][:MAX_RESULTS]
    visited = []
    @contextmanager
    def counted(folder):
      with native(folder) as entries:
        def items():
          for entry in entries:
            visited.append(entry.name)
            yield entry
        yield items()
    with patch("backend.launcher.os.scandir", side_effect=counted):
      result, truncated = self.search.files(str(self.home) + "/", "current")
    self.assertEqual([entry["name"] for entry in result], expected)
    self.assertEqual(len(visited), MAX_RESULTS + 1)
    self.assertTrue(truncated)

  def test_partial_path_search_reports_the_traversal_budget(self):
    for index in range(10):
      (self.home / str(index)).touch()
    with patch("backend.launcher.MAX_ENTRIES", 3):
      results, truncated = self.search.files(str(self.home / "no-match"), "current")
    self.assertEqual(results, [])
    self.assertTrue(truncated)

  def test_cancelled_path_completion_drops_results_immediately(self):
    (self.home / "document.txt").touch()
    self.search.cancel()
    result, truncated = self.search.files(str(self.home) + "/", "current")
    self.assertEqual((result, truncated), ([], False))


class AdaptiveIconTests(unittest.TestCase):
  def setUp(self):
    self.temporary = tempfile.TemporaryDirectory()
    self.addCleanup(self.temporary.cleanup)
    self.root = Path(self.temporary.name)
    for theme, inherited in [("Child", "Parent"), ("Parent", "")]:
      directory = self.root / "icons" / theme
      (directory / "apps").mkdir(parents=True)
      (directory / "index.theme").write_text("[Icon Theme]\nDirectories=apps\nInherits=" + inherited + "\n[apps]\nSize=24\n")
    with patch("backend.icons.Path.home", return_value=self.root):
      self.resolver = IconResolver({"QS_ICON_THEME": "Child", "XDG_DATA_HOME": str(self.root),
        "XDG_DATA_DIRS": str(self.root / "absent")})

  def image(self, name, theme="Child"):
    path = self.root / "icons" / theme / "apps" / name
    path.write_text("fixture")
    return path

  def test_single_icon_keeps_inheritance_mixed_extensions_and_svg_preference(self):
    svg = self.image("editor.sVg", "Parent")
    self.image("editor.png", "Parent")
    with patch("backend.icons.os.scandir", side_effect=AssertionError("Single names must not enumerate theme folders")):
      self.assertEqual(self.resolver.resolve(["editor"]), {"editor": svg.as_uri()})

  def test_exact_extension_symlinks_and_directories_keep_their_meaning(self):
    target = self.image("editor.png")
    alias = target.with_name("alias.SVG")
    alias.symlink_to(target)
    folder = target.with_name("folder.svg")
    folder.mkdir()
    image = self.image("folder.png")
    for name, expected in [("editor.png", target), ("alias", alias), ("folder", image)]:
      with self.subTest(name=name):
        self.assertEqual(self.resolver.resolve([name])[name], expected.as_uri())

  def test_large_batches_switch_to_direct_probes_for_the_last_missing_icon(self):
    for index in range(10):
      self.image("editor" + str(index) + ".svg")
    native = os.scandir
    folders = []
    def scanned(folder):
      folders.append(Path(folder))
      return native(folder)
    names = ["editor" + str(index) for index in range(10)] + ["absent"]
    with patch("backend.icons.os.scandir", side_effect=scanned):
      result = self.resolver.resolve(names)
    self.assertEqual(folders, [self.root / "icons/Child/apps"])
    self.assertEqual(result["absent"], "")
    self.assertTrue(all(result[name] for name in names[:-1]))

  def test_repeated_missing_icon_uses_existing_bounded_name_cache(self):
    self.assertEqual(self.resolver.resolve(["missing"]), {"missing": ""})
    with patch("backend.icons.os.path.isfile", side_effect=AssertionError("A known miss must be cached")), \
        patch("backend.icons.os.scandir", side_effect=AssertionError("A known miss must be cached")):
      self.assertEqual(self.resolver.resolve(["missing"]), {"missing": ""})


if __name__ == "__main__":
  unittest.main()
