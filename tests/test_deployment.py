import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from backend.service import ROOT
sys.path.insert(0, str(ROOT / "tools"))
import deployment
from install import install
from uninstall import uninstall


class DeploymentTests(unittest.TestCase):
  def setUp(self):
    self.temp = tempfile.TemporaryDirectory()
    self.addCleanup(self.temp.cleanup)
    self.root = Path(self.temp.name)
    self.locations = deployment.Locations.create(self.root / "prefix")

  def install(self):
    with contextlib.redirect_stdout(io.StringIO()):
      install(self.locations)

  def uninstall(self, **options):
    with contextlib.redirect_stdout(io.StringIO()):
      uninstall(self.locations, stop=False, **options)

  def test_install_uninstall_preserve_settings_and_remove_owned_code(self):
    self.install()
    launched = subprocess.run([str(self.locations.executable), "--help"], capture_output=True, text=True, timeout=5)
    self.assertEqual(launched.returncode, 0, launched.stderr)
    settings = self.locations.config / "settings.json"
    content = settings.read_bytes()
    (self.locations.config / "clipboard-private.data").write_text("preserve")
    self.uninstall()
    self.assertFalse(self.locations.app.exists())
    self.assertFalse(self.locations.executable.exists())
    self.assertEqual(settings.read_bytes(), content)
    self.assertTrue((self.locations.config / "clipboard-private.data").is_file())
    self.uninstall()

  def test_dry_runs_do_not_create_or_delete_files(self):
    with contextlib.redirect_stdout(io.StringIO()):
      install(self.locations, dry_run=True)
    self.assertFalse((self.root / "prefix").exists())
    self.install()
    self.uninstall(dry_run=True, purge=True)
    self.assertTrue(self.locations.executable.is_file())
    self.assertTrue(self.locations.config.is_dir())

  def test_purge_and_modified_file_preservation(self):
    self.install()
    modified = self.locations.app / "core/Theme.qml"
    modified.write_text("user custom code")
    launcher = self.locations.executable
    launcher.write_text("user custom launcher")
    self.uninstall(purge=True)
    self.assertFalse(self.locations.config.exists())
    self.assertEqual(modified.read_text(), "user custom code")
    self.assertEqual(launcher.read_text(), "user custom launcher")
    self.assertTrue((self.locations.app / deployment.MARKER).is_file())

  def test_path_traversal_in_manifest_cannot_delete_outside_files(self):
    self.install()
    sentinel = self.root / "sentinel"
    sentinel.write_text("keep")
    path = self.locations.app / deployment.MARKER
    document = json.loads(path.read_text())
    document["files"]["../../sentinel"] = deployment.digest(sentinel)
    path.write_text(json.dumps(document))
    with self.assertRaises(ValueError):
      self.uninstall(purge=True)
    self.assertEqual(sentinel.read_text(), "keep")
    self.assertTrue(self.locations.executable.is_file())

  def test_symlinked_ancestors_are_rejected_before_writing(self):
    real = self.root / "real"
    real.mkdir()
    link = self.root / "link"
    link.symlink_to(real, target_is_directory=True)
    locations = deployment.Locations.create(link / "prefix")
    with self.assertRaises(ValueError):
      install(locations)
    self.assertEqual(list(real.iterdir()), [])

  def test_parallel_installations_cannot_modify_the_same_destination(self):
    with deployment.deployment_lock(self.locations):
      with self.assertRaises(ValueError):
        install(self.locations)
    self.assertFalse(self.locations.app.exists())

  def test_install_write_failure_restores_the_previous_installation(self):
    self.install()
    old_launcher = self.locations.executable.read_bytes()
    old_manifest = (self.locations.app / deployment.MARKER).read_bytes()
    old_service = self.locations.managed()['service'].read_bytes()
    write = deployment.atomic_bytes
    def failing(path, content):
      if path == self.locations.app / deployment.MARKER:
        raise OSError("injected write failure")
      return write(path, content)
    with patch("deployment.atomic_bytes", side_effect=failing), \
        patch("install.recovery.render_unit", return_value=old_service.decode() + '# candidate unit\n'), \
        contextlib.redirect_stdout(io.StringIO()):
      with self.assertRaises(OSError):
        install(self.locations)
    self.assertEqual(self.locations.executable.read_bytes(), old_launcher)
    self.assertEqual((self.locations.app / deployment.MARKER).read_bytes(), old_manifest)
    self.assertEqual(self.locations.managed()['service'].read_bytes(), old_service)

  def test_failed_runtime_validation_restores_code_unit_and_settings(self):
    self.install()
    manifest = (self.locations.app / deployment.MARKER).read_bytes()
    targets = {**self.locations.managed(), 'settings': self.locations.config / 'settings.json'}
    contents = {role: target.read_bytes() for role, target in targets.items()}
    stage = self.root / 'candidate'
    stage.mkdir()
    deployment.copy_sources(stage)
    def unhealthy():
      raise RuntimeError('candidate has no bar')
    with self.assertRaises(RuntimeError):
      deployment.commit(self.locations, stage, {**contents, 'service': b'broken unit'}, manifest, activate=unhealthy)
    for role, target in targets.items():
      self.assertEqual(target.read_bytes(), contents[role])
    self.assertEqual((self.locations.app / deployment.MARKER).read_bytes(), manifest)

  def test_desktop_file_supports_reserved_characters_in_paths(self):
    self.locations = deployment.Locations.create(self.root / 'space $dollar `tick` "quote" %percent')
    self.install()
    desktop = self.locations.managed()["desktop"]
    if shutil.which("desktop-file-validate"):
      result = subprocess.run(["desktop-file-validate", str(desktop)], capture_output=True, text=True)
      self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
    self.assertIn("%%", desktop.read_text())
    try:
      import gi
      gi.require_version("GioUnix", "2.0")
      from gi.repository import GioUnix
    except (ImportError, ValueError):
      return
    marker = self.root / "desktop-arguments.json"
    target = self.locations.app / "bin/hyprlarp"
    target.write_text("#!" + sys.executable + "\nimport json,sys\nfrom pathlib import Path\nPath(" + repr(str(marker)) + ").write_text(json.dumps(sys.argv[1:]))\n")
    target.chmod(0o755)
    app = GioUnix.DesktopAppInfo.new_from_filename(str(desktop))
    self.assertTrue(app.launch([], None))
    for _ in range(100):
      if marker.exists():
        break
      time.sleep(0.01)
    self.assertTrue(marker.is_file())
    self.assertEqual(json.loads(marker.read_text()), ["settings"])

  def test_source_copy_excludes_unselected_root_files_and_generated_caches(self):
    staged = self.root / "stage"
    staged.mkdir()
    files = deployment.copy_sources(staged)
    self.assertIn("backend/service.py", files)
    self.assertIn("bin/hyprlarp", files)
    self.assertIn("uninstall.sh", files)
    self.assertTrue(all(".runtime" not in name and "__pycache__" not in name for name in files))
    self.assertFalse((staged / ".git").exists())

  def test_public_scripts_install_and_uninstall_with_an_isolated_prefix(self):
    prefix = self.root / "cli"
    install_result = subprocess.run([str(ROOT / "install.sh"), "--prefix", str(prefix)], text=True, capture_output=True, timeout=15)
    self.assertEqual(install_result.returncode, 0, install_result.stderr)
    result = subprocess.run([str(ROOT / "uninstall.sh"), "--prefix", str(prefix), "--purge"], text=True, capture_output=True, timeout=15)
    self.assertEqual(result.returncode, 0, result.stderr)
    self.assertFalse((prefix / "share/hyprlarp").exists())
    self.assertFalse((prefix / "config/hyprlarp").exists())
