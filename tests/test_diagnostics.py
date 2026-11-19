import json
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

from backend import diagnostics
from backend.service import DEFAULTS


class DiagnosticsTests(unittest.TestCase):
  def test_missing_dependencies_are_reported_without_creating_settings(self):
    with tempfile.TemporaryDirectory() as folder:
      directory = Path(folder) / "not-created"
      with patch("backend.diagnostics.shutil.which", return_value=None), patch("backend.diagnostics.importlib.util.find_spec", return_value=None):
        report = diagnostics.collect(Path(folder), directory=directory, include_logs=False)
      self.assertFalse(report["ok"])
      self.assertFalse(directory.exists())
      self.assertTrue(any(check["id"] == "quickshell" and check["status"] == "error" for check in report["checks"]))

  def test_reports_hide_home_paths_and_named_secrets(self):
    text = diagnostics.redact(str(Path.home()) + "/private password=hidden token:abcd")
    self.assertNotIn(str(Path.home()), text)
    self.assertNotIn("hidden", text)
    self.assertNotIn("abcd", text)
    self.assertLessEqual(len(diagnostics.redact("a" * 20000)), 8192)

  def test_export_is_private_and_valid_json(self):
    with tempfile.TemporaryDirectory() as folder:
      file = Path(folder) / "report.json"
      diagnostics.export({"type": "hyprlarp-diagnostics", "ok": True}, file)
      self.assertTrue(json.loads(file.read_text())["ok"])
      self.assertEqual(stat.S_IMODE(file.stat().st_mode), 0o600)

  def test_probe_timeout_is_an_error_value(self):
    with patch("backend.diagnostics.bounded_process", side_effect=RuntimeError("timed out")):
      self.assertEqual(diagnostics.probe(["example"]), (False, "timed out"))

  def test_invalid_settings_are_diagnosed_without_rewriting_them(self):
    with tempfile.TemporaryDirectory() as folder:
      file = Path(folder) / "settings.json"
      document = {**DEFAULTS, "theme": []}
      file.write_text(json.dumps(document))
      original = file.read_bytes()
      with patch("backend.diagnostics.shutil.which", return_value=None):
        report = diagnostics.collect(Path(folder), directory=folder, include_logs=False)
      self.assertEqual(next(check for check in report["checks"] if check["id"] == "settings")["status"], "warning")
      self.assertEqual(file.read_bytes(), original)

  def test_old_versions_and_a_disconnected_backend_are_reported(self):
    def fake_probe(argv):
      if argv[-1] == "--version":
        return True, "Quickshell 0.2.0" if "quickshell" in argv[0] else "Hyprland 0.57.0"
      if argv[-1] == "health":
        return True, 'WARN: Qt locale diagnostic\n{"ready":true,"connected":false}'
      if argv[-2:] == ["ipc", "show"]:
        return True, "target shell"
      return True, "ActiveState=active"
    with tempfile.TemporaryDirectory() as folder, patch("backend.diagnostics.shutil.which", side_effect=lambda name: "/usr/bin/" + name), patch("backend.diagnostics.probe", side_effect=fake_probe):
      report = diagnostics.collect(Path(folder), directory=folder, include_logs=False)
    self.assertFalse(report["ok"])
    self.assertEqual(next(check for check in report["checks"] if check["id"] == "version-quickshell")["status"], "error")
    self.assertEqual(next(check for check in report["checks"] if check["id"] == "backend")["status"], "warning")
