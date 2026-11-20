"""Packaged commands configure the user while leaving the global payload alone."""

import importlib.machinery
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import session_setup

ROOT = Path(__file__).resolve().parents[1]


class PackagedCliTests(unittest.TestCase):
  def setUp(self):
    temporary = tempfile.TemporaryDirectory()
    self.addCleanup(temporary.cleanup)
    self.app = Path(temporary.name) / "usr/share/hyprlarp"
    self.app.mkdir(parents=True)
    (self.app / ".hyprlarp-package.json").write_text("{}")
    loader = importlib.machinery.SourceFileLoader("hyprlarp_packaged_cli_test", str(ROOT / "bin/hyprlarp"))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    self.cli = importlib.util.module_from_spec(spec)
    loader.exec_module(self.cli)
    self.cli.ROOT = self.app

  def test_install_and_setup_only_call_user_integration(self):
    for command in ["install", "setup"]:
      with self.subTest(command=command), patch("sys.argv", ["hyprlarp", command, "--dry-run"]), \
          patch.object(session_setup, "setup") as setup, patch.object(self.cli.subprocess, "call") as child:
        self.assertEqual(self.cli.main(), 0)
        setup.assert_called_once_with(self.app, prefix=None, dry_run=True)
        child.assert_not_called()

  def test_teardown_and_uninstall_never_remove_global_program_files(self):
    for command in ["teardown", "uninstall"]:
      with self.subTest(command=command), patch("sys.argv", ["hyprlarp", command, "--purge", "--dry-run"]), \
          patch.object(session_setup, "teardown") as teardown, patch.object(self.cli.subprocess, "call") as child:
        self.assertEqual(self.cli.main(), 0)
        teardown.assert_called_once_with(self.app, prefix=None, dry_run=True, purge=True)
        child.assert_not_called()

  def test_first_settings_launch_prepares_user_config_before_ipc(self):
    with patch("sys.argv", ["hyprlarp", "settings"]), \
        patch.object(session_setup, "ready", return_value=False), patch.object(session_setup, "setup") as setup, \
        patch.object(self.cli, "runtime", return_value="qs"), patch.object(self.cli, "ipc", return_value=True), \
        patch("backend.icons.choose_icon_theme", return_value=""):
      self.assertEqual(self.cli.main(), 0)
      setup.assert_called_once_with(self.app)

  def test_package_start_uses_global_executable_without_a_user_launcher(self):
    with patch("sys.argv", ["hyprlarp", "start"]), patch.object(session_setup, "ready", return_value=True), \
        patch.object(session_setup, "setup") as setup, patch.object(self.cli, "runtime", return_value="qs"), \
        patch("backend.recovery.start") as start, patch.dict(os.environ, {}, clear=True):
      self.assertEqual(self.cli.main(), 0)
      setup.assert_not_called()
      self.assertEqual(start.call_args.args, (self.app, self.app.parents[1] / "bin/hyprlarp", "qs"))

  def test_preview_never_sets_up_a_packaged_user_session(self):
    with patch("sys.argv", ["hyprlarp", "preview"]), patch.object(session_setup, "ready") as ready, \
        patch.object(session_setup, "setup") as setup, patch.object(self.cli, "runtime", return_value="qs"), \
        patch("backend.icons.choose_icon_theme", return_value=""), patch.object(self.cli.os, "execvpe") as execute:
      self.assertEqual(self.cli.main(), 0)
      ready.assert_not_called()
      setup.assert_not_called()
      self.assertEqual(execute.call_args.args[2]["HYPRLARP_EXECUTABLE"], str(self.app.parents[1] / "bin/hyprlarp"))
