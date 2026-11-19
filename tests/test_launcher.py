import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

from backend.launcher import LauncherSearch, calculate
from backend import service as api


class CalculatorTests(unittest.TestCase):
  def test_arithmetic_and_functions(self):
    for expression, expected in {"2*(3+4)": "14", "sqrt(81)+2": "11", "sin(pi/2)": "1", "round(1.234,2)": "1.23", "-10//3": "-4"}.items():
      with self.subTest(expression=expression):
        self.assertEqual(calculate(expression), expected)

  def test_code_execution_and_expensive_expressions_are_rejected(self):
    for expression in ["__import__('os').system('true')", "open('/etc/passwd')", "(1).__class__", "[1]*1000000", "2**1000000000", "1/0", "1e999", "True", "x" * 257]:
      with self.subTest(expression=expression), self.assertRaises(ValueError):
        calculate(expression)


class FileSearchTests(unittest.TestCase):
  def setUp(self):
    self.temporary = tempfile.TemporaryDirectory()
    self.addCleanup(self.temporary.cleanup)
    self.home = Path(self.temporary.name)
    self.s = Mock()
    self.s.stopping = threading.Event()
    self.s.queue_refresh.side_effect = lambda name, function, **options: function()
    self.search = LauncherSearch(self.s, api, home=self.home)

  def query(self, text, token="request"):
    self.search.handle("launcher-query", {"query": text, "token": token})
    return self.s.emit.call_args.args[1]

  def test_unicode_files_hidden_directories_and_symlinks(self):
    (self.home / "Niño ñ.txt").write_text("visible")
    hidden = self.home / ".private"
    hidden.mkdir()
    (hidden / "Niño secret.txt").write_text("private")
    (self.home / "linked").symlink_to(hidden, target_is_directory=True)
    result = self.query("? nino")
    self.assertEqual([entry["name"] for entry in result["results"]], ["Niño ñ.txt"])
    self.search.cancel()
    self.assertIsNone(self.search.index)

  def test_absolute_path_completion_preserves_special_characters(self):
    (self.home / "a # % ñ.txt").write_text("fixture")
    result = self.query(str(self.home / "a #"))
    self.assertEqual(result["results"][0]["path"], str(self.home / "a # % ñ.txt"))

  def test_search_budget_and_results_are_bounded(self):
    for index in range(20):
      (self.home / ("report" + str(index))).write_text("fixture")
    with patch("backend.launcher.MAX_ENTRIES", 5):
      result = self.query("report")
    self.assertLessEqual(len(result["results"]), 5)
    self.assertTrue(result["truncated"])

  def test_cancellation_drops_a_pending_reply(self):
    (self.home / "document.txt").write_text("fixture")
    with patch.object(self.search, "files", side_effect=lambda *args: (self.search.cancel() or [], False)):
      self.search.handle("launcher-query", {"query": "document", "token": "cancelled"})
    self.s.emit.assert_not_called()

  def test_calculator_results_and_invalid_tokens(self):
    self.assertEqual(self.query("= 6*7")["results"][0]["value"], "42")
    with self.assertRaises(ValueError):
      self.search.handle("launcher-query", {"query": [], "token": "bad"})

  def test_closing_an_unused_launcher_does_not_create_a_search_backend(self):
    service = api.Service(api.Store(self.home / "state"), preview=True)
    self.addCleanup(service.executor.shutdown, wait=True)
    service.emit = Mock()
    with patch("backend.launcher.LauncherSearch") as create:
      service.action({"action": "launcher-query", "data": {"token": ""}})
    create.assert_not_called()
    self.assertIsNone(service.launcher_search)

  def test_open_uses_an_argument_vector_and_checks_existence(self):
    file = self.home / "name $(touch injected).txt"
    file.write_text("fixture")
    with patch("backend.service.subprocess.Popen") as spawn, patch("backend.service.shutil.which", return_value="/usr/bin/xdg-open"):
      self.search.handle("launcher-open", {"path": str(file)})
    self.assertEqual(spawn.call_args.args[0], ["xdg-open", str(file)])
    self.assertFalse((self.home / "injected").exists())

  @unittest.skipUnless(shutil.which("node"), "Node.js opcional")
  def test_launcher_matching_and_prepared_fuzzy_scores(self):
    result = subprocess.run(["node", str(Path(__file__).with_suffix(".js"))], capture_output=True, text=True, timeout=10)
    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
