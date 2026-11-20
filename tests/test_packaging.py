"""Archives and staged Arch payloads preserve provenance without host changes."""

import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from tools import package


class PackagingTests(unittest.TestCase):
  def setUp(self):
    self.temporary = tempfile.TemporaryDirectory(prefix='hyprlarp-packaging-test-')
    self.addCleanup(self.temporary.cleanup)
    self.base = Path(self.temporary.name)

  def test_staged_payload_runs_version_and_contains_no_active_configuration(self):
    destination = self.base / 'payload'
    document = package.stage(destination)
    app = destination / package.APP_PATH
    self.assertEqual(document['release'], (package.ROOT / 'VERSION').read_text().strip())
    self.assertEqual(json.loads((app / package.PACKAGE_MARKER).read_text()), document)
    self.assertFalse((destination / 'etc').exists())
    self.assertFalse((destination / 'var').exists())
    self.assertFalse((destination / 'usr/lib/systemd').exists())
    self.assertTrue((app / 'tools/install_greeter.py').is_file())
    self.assertNotIn(package.PACKAGE_MARKER, document['files'])
    for name, checksum in document['files'].items():
      self.assertEqual(hashlib.sha256((app / name).read_bytes()).hexdigest(), checksum)
    for name in ['bin/hyprlarp', 'bin/hyprlarp-greeter']:
      result = subprocess.run([sys.executable, str(app / name), '--version'],
        capture_output=True, text=True, timeout=5, env={**os.environ, 'PATH': '/nonexistent'})
      self.assertEqual(result.returncode, 0, result.stderr)
      self.assertTrue(result.stdout.strip().endswith(document['release']))
    self.assertEqual((destination / 'usr/bin/hyprlarp').stat().st_mode & 0o777, 0o755)
    self.assertEqual((app / package.PACKAGE_MARKER).stat().st_mode & 0o777, 0o644)

  def test_staging_refuses_nonempty_destinations_and_symlink_parents(self):
    destination = self.base / 'payload'
    destination.mkdir()
    (destination / 'foreign').write_text('preserve')
    with self.assertRaises(ValueError):
      package.stage(destination)
    self.assertEqual((destination / 'foreign').read_text(), 'preserve')
    link = self.base / 'link'
    link.symlink_to(destination, target_is_directory=True)
    with self.assertRaises(ValueError):
      package.stage(link / 'child')
    with self.assertRaises(ValueError):
      package.stage(package.ROOT / '.runtime/unsafe-package')

  def test_source_installation_keeps_packaging_and_workflows_with_the_same_policy(self):
    from tools import deployment
    locations = deployment.Locations.create(self.base / 'installed')
    locations.app.mkdir(parents=True)
    selected = deployment.copy_sources(locations.app)
    self.assertEqual(set(selected), set(package.files()))
    for name in ['CHANGELOG.md', 'packaging/arch/PKGBUILD.in', 'packaging/arch/Containerfile.qa',
      '.github/workflows/check.yml']:
      self.assertIn(name, selected)
    manifest = {'type': 'hyprlarp-install', 'version': 1, 'prefix': locations.prefix,
      'files': selected, 'managed': {}}
    marker = locations.app / deployment.MARKER
    marker.write_text(json.dumps(manifest))
    self.assertEqual(deployment.load_manifest(locations), manifest)
    manifest['files']['.github/private.yml'] = '0' * 64
    marker.write_text(json.dumps(manifest))
    with self.assertRaises(ValueError):
      deployment.load_manifest(locations)

  def test_source_archive_is_reproducible_and_excludes_local_state(self):
    root = self.base / 'source'
    (root / 'backend').mkdir(parents=True)
    (root / 'VERSION').write_text('1.2.3\n')
    (root / 'backend/sample.py').write_text('print("fixture")\n')
    for name in ['.runtime/secrets.json', '.codex/config.json', 'private.txt',
      'backend/__pycache__/cache.pyc', 'backend/test.py.backup-date', 'backend/debug.log']:
      path = root / name
      path.parent.mkdir(parents=True, exist_ok=True)
      path.write_text('not a release file')
    (root / '.github/workflows').mkdir(parents=True)
    (root / '.github/workflows/check.yml').write_text('name: fixture\n')
    (root / '.github/workflows/private.json').write_text('{"local":"state"}')
    (root / 'packaging/arch').mkdir(parents=True)
    (root / 'packaging/arch/Containerfile.qa').write_text('FROM archlinux:base\n')
    first = package.source_archive(self.base / 'first.tar.gz', root=root, epoch=1234567890)
    os.utime(root / 'backend/sample.py', (100, 100))
    second = package.source_archive(self.base / 'second.tar.gz', root=root, epoch=1234567890)
    self.assertEqual(first.read_bytes(), second.read_bytes())
    with tarfile.open(first) as archive:
      self.assertEqual(archive.getnames(), ['hyprlarp-1.2.3/.github/workflows/check.yml',
        'hyprlarp-1.2.3/VERSION', 'hyprlarp-1.2.3/backend/sample.py',
        'hyprlarp-1.2.3/packaging/arch/Containerfile.qa'])
      for item in archive.getmembers():
        self.assertEqual(item.uid, 0)
        self.assertEqual(item.gid, 0)
        self.assertEqual(item.mtime, 1234567890)

  def test_source_archive_rejects_links_inside_allowed_source_directories(self):
    root = self.base / 'source'
    (root / 'backend').mkdir(parents=True)
    (root / 'VERSION').write_text('1.2.3\n')
    (root / 'backend/leak.py').symlink_to(package.ROOT / 'backend/service.py')
    with self.assertRaises(ValueError):
      package.source_archive(self.base / 'source.tar.gz', root=root)

  def test_prepare_pins_the_source_hash_and_honors_source_date_epoch(self):
    destination = self.base / 'prepared'
    with patch.dict(os.environ, {'SOURCE_DATE_EPOCH': '1234567890'}):
      metadata = package.prepare(destination)
    source = destination / metadata['source']
    self.assertEqual(metadata['sha256'], hashlib.sha256(source.read_bytes()).hexdigest())
    self.assertIn(metadata['sha256'], (destination / 'PKGBUILD').read_text())
    self.assertNotIn('@SHA256@', (destination / 'PKGBUILD').read_text())
    self.assertNotIn('SKIP', (destination / 'PKGBUILD').read_text())
    self.assertNotIn(str(Path.home()), (destination / 'build-info.json').read_text())
    with tarfile.open(source) as archive:
      self.assertTrue(all(item.mtime == 1234567890 for item in archive.getmembers()))
      self.assertIn('hyprlarp-' + metadata['release'] + '/packaging/arch/PKGBUILD.in', archive.getnames())

  def test_arch_version_keeps_common_prereleases_below_the_final_release(self):
    self.assertEqual(package.arch_version('1.2.3+arch.1'), '1.2.3')
    for release in ['1.2.3-rc.1', '1.2.3-beta.2', '1.2.3-1']:
      version = package.arch_version(release)
      self.assertNotIn('-', version)
      if shutil.which('vercmp'):
        compared = subprocess.check_output(['vercmp', version, '1.2.3'], text=True)
        self.assertEqual(compared.strip(), '-1')
    for value in [-1, 0x100000000]:
      with self.assertRaises(ValueError):
        package.epoch_value(value)

  def test_build_never_installs_dependencies_and_refuses_root(self):
    with patch.object(package.os, 'getuid', return_value=0):
      with self.assertRaises(ValueError):
        package.build(self.base / 'output')
    recipe = (package.ROOT / 'packaging/arch/PKGBUILD.in').read_text()
    self.assertNotIn('install=', recipe)
    self.assertNotIn('post_install', recipe)
    self.assertNotIn('systemctl', recipe)
    self.assertIn('noctalia-greeter:', recipe)
    self.assertIn('greetd:', recipe)
    self.assertIn('hyprpicker:', recipe)
    self.assertIn('inter-font', package.DEPENDENCIES)
    self.assertIn('ttf-jetbrains-mono', package.DEPENDENCIES)
    self.assertIn('qt6-imageformats', package.DEPENDENCIES)
    self.assertIn('python-pillow', package.DEPENDENCIES)
    self.assertIn('ttf-dejavu', package.DEPENDENCIES)
    self.assertNotIn('inter-font:', recipe)
    self.assertNotIn('ttf-jetbrains-mono:', recipe)

  def test_package_revision_is_independent_of_the_application_version(self):
    first = package.prepare(self.base / 'one', pkgrel=1)
    second = package.prepare(self.base / 'two', pkgrel=2)
    self.assertEqual(first['release'], second['release'])
    self.assertEqual(first['sha256'], second['sha256'])
    self.assertIn('pkgrel=2\n', (self.base / 'two/PKGBUILD').read_text())
    for value in [0, -1, True, '1', 2147483648]:
      with self.subTest(value=value), self.assertRaises(ValueError):
        package.prepare(self.base / 'bad', pkgrel=value)

  def archive(self, *, mutate=None, pkgrel=1, modes=None):
    prefix = package.APP_PATH + '/'
    names = ['VERSION', 'LICENSE', 'HyprLarp.qml', 'shell.qml', 'backend/service.py',
      'backend/version.py', 'bin/hyprlarp', 'bin/hyprlarp-greeter', 'core/qmldir',
      'assets/hyprlarp-desktop.svg']
    contents = {prefix + name: b'fixture\n' for name in names}
    contents[prefix + 'VERSION'] = b'1.2.3\n'
    marker = {'type': 'hyprlarp-package', 'version': 1, 'release': '1.2.3',
      'files': {name: package.digest(contents[prefix + name]) for name in names}}
    contents[prefix + package.PACKAGE_MARKER] = json.dumps(marker).encode()
    contents['.PKGINFO'] = ('pkgname = hyprlarp\npkgver = 1.2.3-' + str(pkgrel) + '\n'
      + ''.join('depend = ' + value + '\n' for value in package.DEPENDENCIES)).encode()
    contents['.BUILDINFO'] = contents['.MTREE'] = b'fixture\n'
    for command in ['hyprlarp', 'hyprlarp-greeter']:
      contents['usr/bin/' + command] = ('#!/bin/sh\nexec /usr/share/hyprlarp/bin/' + command + ' "$@"\n').encode()
    contents['usr/share/applications/hyprlarp-settings.desktop'] = package.DESKTOP_ENTRY
    contents['usr/share/icons/hicolor/scalable/apps/hyprlarp.svg'] = contents[prefix + 'assets/hyprlarp-desktop.svg']
    contents['usr/share/licenses/hyprlarp/LICENSE'] = contents[prefix + 'LICENSE']
    if mutate:
      mutate(contents)
    target = self.base / 'fixture.pkg.tar.gz'
    with tarfile.open(target, 'w:gz') as archive:
      for name, data in contents.items():
        info = tarfile.TarInfo(name)
        info.size = len(data)
        info.mode = (modes or {}).get(name, 0o755 if name.startswith('usr/bin/') else 0o644)
        archive.addfile(info, io.BytesIO(data))
    return target

  @unittest.skipUnless(shutil.which('bsdtar'), 'bsdtar unavailable')
  def test_verifier_checks_hashes_metadata_dependencies_modes_and_global_paths(self):
    report = package.verify(self.archive(pkgrel=2))
    self.assertTrue(report['ok'])
    self.assertEqual(report['pkgrel'], 2)
    mutations = [
      lambda data: data.__setitem__(package.APP_PATH + '/backend/service.py', b'changed'),
      lambda data: data.__setitem__('etc/greetd/config.toml', b'foreign'),
      lambda data: data.__setitem__('../../outside', b'escape'),
      lambda data: data.__setitem__('usr/bin/hyprlarp', b'other command'),
      lambda data: data.__setitem__('usr/share/applications/hyprlarp-settings.desktop', b'other entry'),
      lambda data: data.__setitem__('.PKGINFO', b'pkgname = hyprlarp\npkgver = 1.2.3-1\n'),
    ]
    for index, mutate in enumerate(mutations):
      with self.subTest(index=index), self.assertRaises(ValueError):
        package.verify(self.archive(mutate=mutate))
    for mode in [0o644, 0o777, 0o4755]:
      with self.subTest(mode=mode), self.assertRaises(ValueError):
        package.verify(self.archive(modes={'usr/bin/hyprlarp': mode}))


if __name__ == '__main__':
  unittest.main()
