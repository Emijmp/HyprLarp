"""Code updates must not apply pending settings or adopt personal files."""

import contextlib
import io
import json
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch

from backend.service import ROOT

sys.path.insert(0, str(ROOT / 'tools'))
import deployment
import install as installer
from uninstall import uninstall


class UpdatePreservationTests(unittest.TestCase):
  def setUp(self):
    self.temporary = tempfile.TemporaryDirectory(prefix='hyprlarp-update-')
    self.addCleanup(self.temporary.cleanup)
    self.root = Path(self.temporary.name)
    self.locations = deployment.Locations.create(self.root / 'prefix')

  def install(self):
    with contextlib.redirect_stdout(io.StringIO()):
      installer.install(self.locations)

  def uninstall(self):
    with contextlib.redirect_stdout(io.StringIO()):
      uninstall(self.locations, stop=False)

  def manifest(self):
    return json.loads((self.locations.app / deployment.MARKER).read_text())

  @staticmethod
  def snapshot(paths):
    return {path: (path.read_bytes(), stat.S_IMODE(path.stat().st_mode), path.stat().st_ino)
      for path in paths}

  def assert_preserved(self, before):
    for path, (content, mode, inode) in before.items():
      with self.subTest(path=path):
        self.assertEqual(path.read_bytes(), content)
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), mode)
        self.assertEqual(path.stat().st_ino, inode)

  def test_update_preserves_active_files_when_saved_settings_have_pending_changes(self):
    self.install()
    settings_path = self.locations.config / 'settings.json'
    settings = json.loads(settings_path.read_text())
    settings['shortcuts']['lock'] = 'SUPER SHIFT, L'
    settings['windowGapsEnabled'] = True
    settings['windowGapsIn'] = 37
    # The unusual formatting is intentional: upgrades preserve the actual file,
    # rather than replacing it with an equivalent reserialized document.
    settings_path.write_text(json.dumps(settings, indent=4) + '\n\n')
    idle = self.locations.managed()['idle']
    idle.write_text(idle.read_text() + 'listener { timeout = 777 }\n')
    history = self.locations.config / 'settings-history.json'
    history.write_bytes(b'personal history is not an installer input\n')
    paths = [settings_path, history] + [self.locations.managed()[name] for name in ['bindings', 'gaps', 'idle']]
    for path in paths:
      path.chmod(0o640)
    before = self.snapshot(paths)
    old_code = (self.locations.app / 'backend/__init__.py').read_bytes()
    original_copy = installer.copy_sources
    def candidate(stage):
      files = original_copy(stage)
      path = stage / 'backend/__init__.py'
      path.write_bytes(path.read_bytes() + b'\n# candidate release\n')
      files['backend/__init__.py'] = deployment.digest(path)
      return files
    with patch.object(installer, 'copy_sources', side_effect=candidate):
      self.install()
    self.assert_preserved(before)
    self.assertNotEqual((self.locations.app / 'backend/__init__.py').read_bytes(), old_code)
    self.assertIn('["chord"] = "SUPER, L"', self.locations.managed()['bindings'].read_text())
    self.assertNotIn('["id"] = "shell-lock", ["name"] = "lock", ["chord"] = "SUPER SHIFT, L"',
      self.locations.managed()['bindings'].read_text())

  def test_owned_unmodified_service_updates_without_rewriting_other_managed_files(self):
    self.install()
    service = self.locations.managed()['service']
    unit = service.read_bytes() + b'# candidate release\n'
    unchanged = self.snapshot([target for role, target in self.locations.managed().items() if role != 'service']
      + [self.locations.config / 'settings.json'])
    with patch.object(installer.recovery, 'render_unit', return_value=unit.decode()):
      self.install()
    self.assertEqual(service.read_bytes(), unit)
    self.assertEqual(self.manifest()['managed']['service'], deployment.digest(service))
    self.assert_preserved(unchanged)

  def test_modified_generated_integrations_survive_update_and_removal(self):
    self.install()
    owned = self.manifest()['managed']
    roles = ['launcher', 'prelude', 'session', 'service', 'desktop', 'icon']
    paths = [self.locations.managed()[role] for role in roles]
    for index, path in enumerate(paths):
      path.write_bytes(path.read_bytes() + ('\n# personal integration ' + str(index) + '\n').encode())
      path.chmod(0o750 if roles[index] == 'launcher' else 0o640)
    before = self.snapshot(paths)
    self.install()
    self.assert_preserved(before)
    for role in roles:
      self.assertEqual(self.manifest()['managed'].get(role), owned[role])
    self.uninstall()
    self.assert_preserved(before)

  def test_modified_source_and_unowned_files_survive_update_and_removal(self):
    self.install()
    name = 'core/Theme.qml'
    old_owned_hash = self.manifest()['files'][name]
    modified = self.locations.app / name
    modified.write_bytes(modified.read_bytes() + b'\n// personal theme extension\n')
    modified.chmod(0o640)
    foreign = self.locations.app / 'personal/notes.txt'
    foreign.parent.mkdir()
    foreign.write_text('personal data\n')
    foreign.chmod(0o600)
    before = {path: (path.read_bytes(), stat.S_IMODE(path.stat().st_mode)) for path in [modified, foreign]}
    self.install()
    self.assertEqual(self.manifest()['files'].get(name), old_owned_hash)
    self.assertNotIn('personal/notes.txt', self.manifest()['files'])
    self.uninstall()
    for path, (contents, mode) in before.items():
      self.assertEqual(path.read_bytes(), contents)
      self.assertEqual(stat.S_IMODE(path.stat().st_mode), mode)

  def test_first_install_keeps_existing_personal_settings_and_does_not_adopt_foreign_integrations(self):
    self.locations.config.mkdir(parents=True)
    settings = self.locations.config / 'settings.json'
    settings.write_text('{"version":3,"font":"Personal font"}\n\n')
    prelude = self.locations.managed()['prelude']
    prelude.write_text('-- personal prelude which predates this installation\n')
    prelude.chmod(0o640)
    before = self.snapshot([settings, prelude])
    self.install()
    self.assert_preserved(before)
    self.assertNotIn('prelude', self.manifest()['managed'])
    self.assertTrue(self.locations.managed()['bindings'].is_file())
    self.uninstall()
    self.assert_preserved(before)

  def test_commit_subset_never_moves_unselected_managed_files(self):
    self.install()
    targets = {**self.locations.managed(), 'settings': self.locations.config / 'settings.json'}
    untouched = self.snapshot([path for name, path in targets.items() if name != 'service'])
    stage = self.root / 'candidate'
    stage.mkdir()
    deployment.copy_sources(stage)
    manifest = (self.locations.app / deployment.MARKER).read_bytes()
    deployment.commit(self.locations, stage, {'service': b'candidate unit\n'}, manifest)
    self.assertEqual(targets['service'].read_bytes(), b'candidate unit\n')
    self.assert_preserved(untouched)
    for path in untouched:
      self.assertEqual(list(path.parent.glob(path.name + '.backup-*')), [])

  def test_failed_subset_activation_restores_updated_code_and_keeps_unselected_files(self):
    self.install()
    targets = {**self.locations.managed(), 'settings': self.locations.config / 'settings.json'}
    before = self.snapshot(list(targets.values()))
    marker = (self.locations.app / deployment.MARKER).read_bytes()
    source = (self.locations.app / 'backend/__init__.py').read_bytes()
    stage = self.root / 'candidate'
    stage.mkdir()
    deployment.copy_sources(stage)
    (stage / 'backend/__init__.py').write_bytes(b'# unhealthy release\n')
    def unhealthy():
      raise RuntimeError('candidate backend did not become ready')
    with self.assertRaisesRegex(RuntimeError, 'did not become ready'):
      deployment.commit(self.locations, stage, {'service': b'candidate unit\n'}, marker, activate=unhealthy)
    self.assert_preserved(before)
    self.assertEqual((self.locations.app / deployment.MARKER).read_bytes(), marker)
    self.assertEqual((self.locations.app / 'backend/__init__.py').read_bytes(), source)


if __name__ == '__main__':
  unittest.main()
