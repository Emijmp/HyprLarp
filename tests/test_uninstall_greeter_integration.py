"""Greeter authorization failures must leave the desktop installation intact."""

import contextlib
from dataclasses import replace
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from backend.service import ROOT
sys.path.insert(0, str(ROOT / 'tools'))
import deployment
import install as installer
import install_greeter
import uninstall as remover


class GreeterRemovalIntegrationTests(unittest.TestCase):
  def setUp(self):
    self.temporary = tempfile.TemporaryDirectory(prefix='hyprlarp-greeter-removal-')
    self.addCleanup(self.temporary.cleanup)
    isolated = deployment.Locations.create(Path(self.temporary.name) / 'prefix')
    with contextlib.redirect_stdout(io.StringIO()):
      installer.install(isolated)
    self.isolated = isolated
    self.locations = replace(isolated, prefix='')
    marker = self.locations.app / deployment.MARKER
    manifest = json.loads(marker.read_text())
    manifest['prefix'] = ''
    marker.write_text(json.dumps(manifest))
    self.greeter = self.locations.data / 'hyprlarp-greeter/installation.json'
    self.greeter.parent.mkdir()
    self.greeter.write_text('{}')

  def test_no_privileges_leaves_core_code_and_configuration_untouched(self):
    paths = [self.locations.app / deployment.MARKER, self.locations.executable,
      self.locations.config / 'settings.json', self.locations.managed()['bindings']]
    before = {p: p.read_bytes() for p in paths}
    with patch.object(install_greeter, 'uninstall_user', create=True,
        side_effect=RuntimeError('Falta autorización de administrador')) as greeter, \
        patch.object(remover, 'stop_runtime') as stop, contextlib.redirect_stdout(io.StringIO()):
      with self.assertRaisesRegex(RuntimeError, 'autorización'):
        remover.uninstall(self.locations)
    greeter.assert_called_once_with(dry_run=False)
    stop.assert_not_called()
    for path, data in before.items():
      self.assertEqual(path.read_bytes(), data)

  def test_greeter_is_restored_before_stopping_and_removing_core(self):
    order = []
    def restored(**options):
      self.assertTrue(self.locations.executable.is_file())
      self.assertTrue(self.locations.app.is_dir())
      order.append('greeter')
    def stopped(locations):
      self.assertEqual(order, ['greeter'])
      order.append('shell')
    with patch.object(install_greeter, 'uninstall_user', create=True, side_effect=restored), \
        patch.object(remover, 'stop_runtime', side_effect=stopped), \
        patch.object(remover.recovery, 'run'), contextlib.redirect_stdout(io.StringIO()):
      remover.uninstall(self.locations)
    self.assertEqual(order, ['greeter', 'shell'])
    self.assertFalse(self.locations.app.exists())
    self.assertTrue((self.locations.config / 'settings.json').is_file())

  def test_dry_run_plans_both_components_without_removing_files(self):
    with patch.object(install_greeter, 'uninstall_user', create=True) as greeter, \
        patch.object(remover, 'stop_runtime') as stop, contextlib.redirect_stdout(io.StringIO()):
      remover.uninstall(self.locations, dry_run=True)
    greeter.assert_called_once_with(dry_run=True)
    stop.assert_not_called()
    self.assertTrue(self.locations.app.is_dir())
    self.assertTrue(self.locations.executable.is_file())

  def test_isolated_prefix_never_controls_the_real_greeter(self):
    with patch.object(install_greeter, 'uninstall_user', create=True) as greeter:
      remover.remove_optional_greeter(self.isolated, dry_run=False)
    greeter.assert_not_called()

  def test_standalone_greeter_can_be_removed_after_core_was_already_removed(self):
    import shutil
    shutil.rmtree(self.locations.app)
    with patch.object(install_greeter, 'uninstall_user', create=True) as greeter, \
        contextlib.redirect_stdout(io.StringIO()):
      remover.uninstall(self.locations)
    greeter.assert_called_once_with(dry_run=False)


if __name__ == '__main__':
  unittest.main()
