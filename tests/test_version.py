"""Every installed entry point reads the same release without Git or a desktop."""

import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from backend import diagnostics
from backend.performance import package_revision
from backend.version import ROOT, VERSION, read_version
from tools import deployment, install_greeter

sys.path.insert(0, str(ROOT / 'tools'))
from install import install


class UnifiedVersionTests(unittest.TestCase):
  def version_command(self, target, *, environment=None):
    return subprocess.run([sys.executable, str(target), '--version'], cwd=target.parent,
      env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1', 'PATH': '/nonexistent',
        'WAYLAND_DISPLAY': '', **(environment or {})}, capture_output=True, text=True, timeout=5)

  def test_all_source_commands_read_the_release_without_external_commands(self):
    for relative, name in [('bin/hyprlarp', 'HyprLarp'), ('bin/hyprlarp-greeter', 'HyprLarp Greeter'),
        ('backend/service.py', 'HyprLarp'),
        ('backend/greeter.py', 'HyprLarp Greeter'), ('greeter/model.py', 'HyprLarp Greeter'),
        ('tools/install.py', 'HyprLarp'), ('tools/install_greeter.py', 'HyprLarp Greeter')]:
      with self.subTest(relative=relative):
        result = self.version_command(ROOT / relative)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), name + ' ' + VERSION)

  def test_installed_commands_use_their_own_version_and_survive_without_checkout(self):
    with tempfile.TemporaryDirectory(prefix='hyprlarp-version-') as folder:
      locations = deployment.Locations.create(Path(folder) / 'prefix')
      with contextlib.redirect_stdout(io.StringIO()):
        install(locations)
      self.assertIn('VERSION', deployment.load_manifest(locations)['files'])
      self.assertEqual(deployment.load_manifest(locations)['release'], VERSION)
      self.assertEqual((locations.app / 'VERSION').read_text().strip(), VERSION)
      # An alternate release in the installed bundle must be authoritative;
      # loading the checkout or hard-coding the CLI would fail this assertion.
      (locations.app / 'VERSION').write_text('2.3.4-rc.1+packaged\n')
      for relative in ['bin/hyprlarp', 'bin/hyprlarp-greeter', 'greeter/model.py']:
        result = self.version_command(locations.app / relative)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.strip().endswith('2.3.4-rc.1+packaged'))

  def test_standalone_greeter_bundle_includes_its_own_release_reader(self):
    with tempfile.TemporaryDirectory(prefix='hyprlarp-greeter-version-') as folder:
      root = Path(folder)
      for relative in install_greeter.SYNC_FILES:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
      self.assertTrue((root / 'backend/__init__.py').is_file())
      shadow = root / 'foreign-site/backend'
      shadow.mkdir(parents=True)
      (shadow / '__init__.py').write_text('raise RuntimeError("Unrelated backend package loaded")\n')
      (root / 'VERSION').write_text('3.2.1\n')
      for relative in ['backend/greeter.py', 'greeter/model.py', 'tools/install_greeter.py']:
        result = self.version_command(root / relative, environment={'PYTHONPATH': str(shadow.parent)})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), 'HyprLarp Greeter 3.2.1')

  def test_login_ui_has_a_complete_version_bundle(self):
    with tempfile.TemporaryDirectory(prefix='hyprlarp-login-version-') as folder:
      root = Path(folder)
      ui = root / 'ui'
      backup = root / 'backup'
      backup.mkdir()
      with patch.object(install_greeter, 'GREETER_UI', ui), \
          patch.object(install_greeter, 'UI_LAUNCHER', root / 'bin/greeter-ui'), \
          patch.object(install_greeter, 'SESSION_LAUNCHER', root / 'bin/greeter-session'):
        install_greeter.install_ui(backup, 'fixture')
      self.assertEqual(read_version(ui), VERSION)
      result = self.version_command(ui / 'greeter/model.py')
      self.assertEqual(result.returncode, 0, result.stderr)
      self.assertEqual(result.stdout.strip(), 'HyprLarp Greeter ' + VERSION)

  def test_diagnostics_keep_release_separate_from_report_format(self):
    with tempfile.TemporaryDirectory() as folder, patch('backend.diagnostics.shutil.which', return_value=None):
      report = diagnostics.collect(ROOT, directory=folder, include_logs=False)
    self.assertEqual(report['version'], 1)
    self.assertEqual(report['versions']['HyprLarp'], VERSION)

  def test_runtime_revision_includes_the_release_file(self):
    with tempfile.TemporaryDirectory(prefix='hyprlarp-version-revision-') as folder:
      root = Path(folder)
      shutil.copy2(ROOT / 'VERSION', root / 'VERSION')
      shutil.copytree(ROOT / 'backend', root / 'backend', ignore=shutil.ignore_patterns('__pycache__'))
      before = package_revision(root)
      (root / 'VERSION').write_text('2.0.0\n')
      self.assertNotEqual(package_revision(root), before)

  def test_version_file_is_bounded_and_rejects_invalid_semantic_versions(self):
    with tempfile.TemporaryDirectory() as folder:
      target = Path(folder) / 'VERSION'
      for value in ['1.2', '01.2.3', '1.2.3-01', '1.2.3-rc..1', '1.2.3\n2.3.4',
          '1.2.3+ñ', '1.2.3+' + 'a' * 129, '']:
        with self.subTest(value=value):
          target.write_text(value)
          with self.assertRaises(ValueError):
            read_version(folder)
      for value in ['0.1.0', '1.2.3-rc.1+linux-x86_64'.replace('_', '-'), '1.2.3+001']:
        target.write_text(value + '\n')
        self.assertEqual(read_version(folder), value)

  def test_fresh_install_marker_is_kept_across_updates_but_not_added_to_legacy_users(self):
    with tempfile.TemporaryDirectory(prefix='hyprlarp-first-run-') as folder:
      locations = deployment.Locations.create(Path(folder) / 'prefix')
      with contextlib.redirect_stdout(io.StringIO()):
        install(locations)
        self.assertTrue(deployment.load_manifest(locations)['first_run'])
        install(locations)
        self.assertTrue(deployment.load_manifest(locations)['first_run'])
        manifest = deployment.load_manifest(locations)
        del manifest['first_run']
        (locations.app / deployment.MARKER).write_text(json.dumps(manifest))
        install(locations)
      self.assertFalse(deployment.load_manifest(locations)['first_run'])

  def test_existing_configuration_is_not_treated_as_first_run(self):
    with tempfile.TemporaryDirectory(prefix='hyprlarp-existing-user-') as folder:
      locations = deployment.Locations.create(Path(folder) / 'prefix')
      locations.config.mkdir(parents=True)
      settings = locations.config / 'settings.json'
      settings.write_text('{"theme":"amoled"}')
      original = settings.read_bytes()
      with contextlib.redirect_stdout(io.StringIO()):
        install(locations)
      self.assertFalse(deployment.load_manifest(locations)['first_run'])
      self.assertEqual(settings.read_bytes(), original)
