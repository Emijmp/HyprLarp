#!/usr/bin/env python3
"""Prepare, build and inspect an Arch package without installing on the host."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
from backend.version import read_version

PACKAGE_MARKER = '.hyprlarp-package.json'
APP_PATH = 'usr/share/hyprlarp'
DEPENDENCIES = ('python>=3.11', 'quickshell>=0.3.2', 'hyprland>=0.57', 'qt6-declarative',
  'qt6-svg', 'qt6-wayland', 'qt6-imageformats', 'python-gobject', 'libnm', 'systemd',
  'inter-font', 'ttf-jetbrains-mono', 'ttf-dejavu', 'python-pillow')
DESKTOP_ENTRY = (b'[Desktop Entry]\nType=Application\nName=HyprLarp Settings\nName[es]=Configuraci\xc3\xb3n de HyprLarp\n'
  b'Comment=Personaliza tu escritorio\nExec=/usr/bin/hyprlarp settings\nIcon=hyprlarp\nTerminal=false\nCategories=Settings;DesktopSettings;\n')
SOURCE_DIRS = {'assets', 'backend', 'bin', 'components', 'config', 'core', 'panels',
  'widgets', 'tools', 'tests', 'docs', 'greeter', 'packaging', '.github'}
SOURCE_FILES = {'VERSION', 'LICENSE', 'README.md', 'CHANGELOG.md', 'Makefile', 'install.sh',
  'uninstall.sh', '.editorconfig', '.qmlformat.ini', 'HyprLarp.qml', 'shell.qml',
  'recovery.qml', 'preview.qml', 'settings.qml', 'accessibility-check.qml',
  'resilience-check.qml', 'performance-check.qml', 'visual-check.qml', 'native-types.qml'}
SOURCE_SUFFIXES = {'.qml', '.py', '.js', '.json', '.lua', '.svg', '.png', '.wav', '.md',
  '.sh', '.conf', '.yml', '.yaml'}
EXECUTABLES = {'bin/hyprlarp', 'bin/hyprlarp-greeter', 'install.sh', 'uninstall.sh'}
EXTRAS = {'usr/bin/hyprlarp', 'usr/bin/hyprlarp-greeter',
  'usr/share/applications/hyprlarp-settings.desktop',
  'usr/share/icons/hicolor/scalable/apps/hyprlarp.svg',
  'usr/share/licenses/hyprlarp/LICENSE'}


def arch_version(release):
  """Keep a prerelease below its final Arch version; metadata stays in VERSION."""
  core, separator, prerelease = release.split('+', 1)[0].partition('-')
  return core + ('pre.' + prerelease if separator else '')


def epoch_value(value=None):
  value = int(os.environ.get('SOURCE_DATE_EPOCH', '0')) if value is None else int(value)
  if not 0 <= value <= 0xffffffff:
    raise ValueError('SOURCE_DATE_EPOCH debe estar entre 0 y 4294967295')
  return value


def package_release(value):
  if type(value) is not int or not 1 <= value <= 2147483647:
    raise ValueError('pkgrel debe ser un entero positivo entre 1 y 2147483647')
  return value


def digest(data):
  return hashlib.sha256(data).hexdigest()


def files(root=ROOT):
  """A fixed source policy omits home state, VCS, caches and unrelated files."""
  root = Path(root).resolve()
  result = {}
  for entry in sorted(root.iterdir()):
    if entry.name not in SOURCE_DIRS | SOURCE_FILES:
      continue
    if entry.is_symlink():
      raise ValueError('El paquete no admite enlaces simbólicos: ' + str(entry))
    candidates = [entry] if entry.is_file() else sorted(entry.rglob('*'))
    for path in candidates:
      relative = path.relative_to(root)
      if any(part == '__pycache__' or (part.startswith('.') and not (index == 0 and part == '.github'))
        for index, part in enumerate(relative.parts) if len(relative.parts) > 1):
        continue
      if any('.backup-' in part or part.endswith(('.bak', '.tmp', '.log', '.pyc')) for part in relative.parts):
        continue
      if path.is_symlink():
        raise ValueError('El paquete no admite enlaces simbólicos: ' + str(relative))
      if not path.is_file():
        continue
      name = relative.as_posix()
      if path.suffix not in SOURCE_SUFFIXES and name not in SOURCE_FILES | EXECUTABLES \
        and path.name != 'qmldir' and name not in {'packaging/arch/PKGBUILD.in', 'packaging/arch/Containerfile.qa'}:
        continue
      if relative.parts[0] == '.github' and (relative.parts[:2] != ('.github', 'workflows')
        or path.suffix not in {'.yml', '.yaml'}):
        continue
      result[name] = path
  return result


def source_archive(destination, *, root=ROOT, epoch=0):
  """Write a reproducible source tar.gz to the specified filename."""
  root, destination = Path(root).resolve(), Path(destination)
  version = read_version(root)
  timestamp = epoch_value(epoch)
  selected = files(root)
  destination.parent.mkdir(parents=True, exist_ok=True)
  # Stage the archive next to its destination so an interrupted build leaves
  # the previous archive intact and cannot archive its own temporary output.
  descriptor, temporary = tempfile.mkstemp(prefix='.hyprlarp-source-', dir=destination.parent)
  try:
    with os.fdopen(descriptor, 'wb') as target:
      with gzip.GzipFile(filename='', fileobj=target, mode='wb', mtime=timestamp) as compressed:
        with tarfile.open(fileobj=compressed, mode='w', format=tarfile.PAX_FORMAT) as archive:
          for name, path in selected.items():
            content = path.read_bytes()
            entry = tarfile.TarInfo('hyprlarp-' + version + '/' + name)
            entry.size, entry.mtime = len(content), timestamp
            entry.mode = 0o755 if name in EXECUTABLES else 0o644
            entry.uid = entry.gid = 0
            entry.uname = entry.gname = ''
            archive.addfile(entry, io.BytesIO(content))
    os.replace(temporary, destination)
  finally:
    Path(temporary).unlink(missing_ok=True)
  return destination


def verify_source_archive(source, *, root=ROOT):
  """Check a prepared source without changing its gzip stream or timestamps."""
  root = Path(root).resolve()
  release = read_version(root)
  selected = files(root)
  prefix = 'hyprlarp-' + release + '/'
  seen, timestamp = set(), None
  # Leave room for PAX headers, block padding and the final tar records, while
  # bounding any additional gzip members hidden after the end of the tar.
  budget = sum(path.stat().st_size for path in selected.values()) + len(selected) * 8192 + 2 * tarfile.RECORDSIZE
  try:
    with gzip.open(source, 'rb') as compressed:
      with tarfile.open(fileobj=compressed, mode='r|') as archive:
        for entry in archive:
          name = entry.name.removeprefix(prefix)
          if (not entry.name.startswith(prefix) or name not in selected or name in seen
              or not entry.isfile() or entry.mode != (0o755 if name in EXECUTABLES else 0o644)):
            raise ValueError('El archivo fuente contiene entradas ajenas o no válidas')
          expected = selected[name]
          if entry.size != expected.stat().st_size:
            raise ValueError('Las fuentes preparadas no coinciden con el árbol actual; reconstruye el paquete')
          with archive.extractfile(entry) as content, expected.open('rb') as current:
            if hashlib.file_digest(content, 'sha256').digest() != hashlib.file_digest(current, 'sha256').digest():
              raise ValueError('Las fuentes preparadas no coinciden con el árbol actual; reconstruye el paquete')
          epoch = epoch_value(entry.mtime)
          if timestamp is not None and timestamp != epoch:
            raise ValueError('Las fuentes preparadas contienen fechas inconsistentes')
          timestamp = epoch
          seen.add(name)
      remaining = budget - compressed.tell()
      while remaining >= 0:
        extra = compressed.read(min(64 * 1024, remaining + 1))
        if not extra:
          break
        remaining -= len(extra)
      if remaining < 0:
        raise ValueError('El archivo fuente contiene demasiados datos adicionales')
  except (tarfile.TarError, EOFError, gzip.BadGzipFile, zlib.error) as error:
    raise ValueError('El archivo fuente preparado no es un tar.gz válido') from error
  if seen != selected.keys():
    raise ValueError('Faltan archivos en las fuentes preparadas; reconstruye el paquete')
  return {'release': release, 'files': len(seen), 'source_date_epoch': timestamp}


def atomic_text(destination, content):
  descriptor, temporary = tempfile.mkstemp(prefix='.hyprlarp-artifact-', dir=destination.parent)
  try:
    with os.fdopen(descriptor, 'w', encoding='utf-8') as target:
      target.write(content)
    os.chmod(temporary, 0o644)
    os.replace(temporary, destination)
  finally:
    Path(temporary).unlink(missing_ok=True)


def write(destination, content, mode=0o644):
  destination.parent.mkdir(parents=True, exist_ok=True)
  destination.write_bytes(content)
  destination.chmod(mode)


def stage(destdir, *, root=ROOT):
  """Populate a disposable DESTDIR. No package scripts or services are run."""
  root, destination = Path(root).resolve(), Path(destdir).absolute()
  if destination == Path('/') or destination == root or root.is_relative_to(destination) or destination.is_relative_to(root):
    raise ValueError('DESTDIR debe estar fuera del árbol de fuentes y no puede ser /')
  for path in [destination, *destination.parents]:
    if path.is_symlink():
      raise ValueError('DESTDIR no puede atravesar enlaces simbólicos')
  if destination.exists() and any(destination.iterdir()):
    raise ValueError('DESTDIR debe estar vacío')
  selected = files(root)
  required = {'VERSION', 'LICENSE', 'HyprLarp.qml', 'shell.qml', 'settings.qml',
    'preview.qml', 'recovery.qml', 'bin/hyprlarp', 'bin/hyprlarp-greeter',
    'backend/service.py', 'backend/version.py', 'config/defaults.json', 'core/qmldir',
    'greeter/model.py', 'tools/install_greeter.py', 'assets/hyprlarp-desktop.svg'}
  if required - selected.keys():
    raise ValueError('Faltan archivos de ejecución: ' + ', '.join(sorted(required - selected.keys())))
  app = destination / APP_PATH
  owned = {}
  for name, source in selected.items():
    content = source.read_bytes()
    write(app / name, content, 0o755 if name in EXECUTABLES else 0o644)
    owned[name] = digest(content)
  document = {'type': 'hyprlarp-package', 'version': 1, 'release': read_version(root), 'files': owned}
  write(app / PACKAGE_MARKER, (json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode())
  for command in ('hyprlarp', 'hyprlarp-greeter'):
    write(destination / 'usr/bin' / command,
      ('#!/bin/sh\nexec /usr/share/hyprlarp/bin/' + command + ' "$@"\n').encode(), 0o755)
  write(destination / 'usr/share/applications/hyprlarp-settings.desktop',
    DESKTOP_ENTRY)
  write(destination / 'usr/share/icons/hicolor/scalable/apps/hyprlarp.svg', (root / 'assets/hyprlarp-desktop.svg').read_bytes())
  write(destination / 'usr/share/licenses/hyprlarp/LICENSE', (root / 'LICENSE').read_bytes())
  for folder in destination.rglob('*'):
    if folder.is_dir():
      folder.chmod(0o755)
  return document


def prepare(output, *, root=ROOT, epoch=None, pkgrel=1):
  root, output = Path(root).resolve(), Path(output).absolute()
  pkgrel = package_release(pkgrel)
  version = read_version(root)
  for path in [output, *output.parents, output / 'PKGBUILD', output / 'build-info.json',
      output / ('hyprlarp-' + version + '.tar.gz')]:
    if path.is_symlink():
      raise ValueError('La preparación no escribe a través de enlaces simbólicos: ' + str(path))
  for name in ['PKGBUILD', 'build-info.json']:
    path = output / name
    if path.exists() and not path.is_file():
      raise ValueError('El artefacto debe ser un archivo regular: ' + str(path))
  output.mkdir(parents=True, exist_ok=True)
  archive = source_archive(output / ('hyprlarp-' + version + '.tar.gz'), root=root, epoch=epoch_value(epoch))
  checksum = digest(archive.read_bytes())
  recipe = (root / 'packaging/arch/PKGBUILD.in').read_text()
  for token, value in {'@PKGVER@': arch_version(version), '@PKGREL@': str(pkgrel), '@RELEASE@': version,
    '@ARCHIVE@': archive.name, '@SHA256@': checksum,
    '@DEPENDS@': ' '.join(shlex.quote(item) for item in DEPENDENCIES)}.items():
    recipe = recipe.replace(token, value)
  if re.search(r'@[A-Z]+@', recipe):
    raise ValueError('La plantilla PKGBUILD contiene variables desconocidas')
  atomic_text(output / 'PKGBUILD', recipe)
  metadata = {'release': version, 'pkgver': arch_version(version), 'pkgrel': pkgrel,
    'source': archive.name, 'sha256': checksum}
  atomic_text(output / 'build-info.json', json.dumps(metadata, indent=2) + '\n')
  return metadata


def build(output, *, root=ROOT, nodeps=False, nocheck=False, epoch=None, pkgrel=1):
  if os.getuid() == 0:
    raise ValueError('makepkg debe ejecutarse como un usuario sin privilegios')
  binary = shutil.which('makepkg')
  if not binary:
    raise ValueError('Falta makepkg; prepara las fuentes en Arch/CachyOS para construir el paquete')
  output = Path(output).absolute()
  timestamp = epoch_value(epoch)
  metadata = prepare(output, root=root, epoch=timestamp, pkgrel=pkgrel)
  arguments = [binary, '--force', '--cleanbuild', '--noconfirm']
  if nodeps:
    arguments.append('--nodeps')
  if nocheck:
    arguments.append('--nocheck')
  # A private temporary build tree avoids stale objects and never needs sudo.
  with tempfile.TemporaryDirectory(prefix='hyprlarp-makepkg-') as folder:
    recipe = Path(folder) / 'recipe'
    recipe.mkdir()
    shutil.copy2(output / 'PKGBUILD', recipe / 'PKGBUILD')
    shutil.copy2(output / metadata['source'], recipe / metadata['source'])
    environment = {**os.environ, 'BUILDDIR': str(Path(folder) / 'build'), 'PKGDEST': str(output),
      'SOURCE_DATE_EPOCH': str(timestamp), 'PYTHONDONTWRITEBYTECODE': '1'}
    subprocess.run(arguments, cwd=recipe, env=environment, check=True)
  package = output / ('hyprlarp-' + metadata['pkgver'] + '-' + str(metadata['pkgrel']) + '-any.pkg.tar.zst')
  if not package.is_file():
    raise ValueError('makepkg no produjo el paquete esperado: ' + package.name)
  verify(package)
  return package


def verify(package):
  """Inspect an archive without extracting paths or executing its contents."""
  package = Path(package).absolute()
  binary = shutil.which('bsdtar')
  if not binary:
    raise ValueError('Falta bsdtar (libarchive) para comprobar el paquete')
  def command(*arguments):
    result = subprocess.run([binary, *arguments, str(package)] if arguments[-1] == '-f' else [binary, *arguments],
      capture_output=True, check=True, timeout=30)
    if len(result.stdout) > 8 * 1024 * 1024:
      raise ValueError('El contenido inspeccionado supera el límite permitido')
    return result.stdout
  names = command('-t', '-f').decode().splitlines()
  modes = command('-t', '-v', '-f').decode().splitlines()
  if any(line and (len(line) < 10 or line[0] not in {'-', 'd'} or line[5] == 'w' or line[8] == 'w'
    or any(char in line[:10] for char in 'sStT')) for line in modes):
    raise ValueError('El paquete contiene enlaces, tipos especiales o permisos inseguros')
  for command_name in ('hyprlarp', 'hyprlarp-greeter'):
    if not any(line.startswith('-rwxr-xr-x') and line.endswith(' usr/bin/' + command_name) for line in modes):
      raise ValueError('El comando global no es ejecutable con permisos seguros')
  normalized = []
  for name in names:
    name = name.removeprefix('./')
    if not name or name == '.':
      continue
    path = PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts or any(ord(c) < 32 for c in name):
      raise ValueError('El paquete contiene una ruta no válida')
    if not name.endswith('/'):
      normalized.append(name)
  if len(normalized) > 4096 or len(set(normalized)) != len(normalized):
    raise ValueError('El paquete contiene entradas duplicadas o demasiados archivos')
  def content(name):
    return command('-x', '-O', '-f', str(package), name)
  marker = APP_PATH + '/' + PACKAGE_MARKER
  if marker not in normalized:
    raise ValueError('Falta el manifiesto del paquete')
  document = json.loads(content(marker))
  if not isinstance(document, dict) or document.get('type') != 'hyprlarp-package' or type(document.get('version')) is not int or document['version'] != 1 or not isinstance(document.get('files'), dict):
    raise ValueError('El manifiesto del paquete no es válido')
  if {'VERSION', 'shell.qml', 'HyprLarp.qml', 'backend/service.py', 'backend/version.py',
    'bin/hyprlarp', 'bin/hyprlarp-greeter', 'core/qmldir'} - document['files'].keys():
    raise ValueError('El paquete no incluye todos sus puntos de entrada')
  expected = {marker, '.PKGINFO', '.BUILDINFO', '.MTREE'} | EXTRAS
  for name, checksum in document['files'].items():
    path = PurePosixPath(name)
    if not name or path.is_absolute() or '..' in path.parts or not re.fullmatch('[0-9a-f]{64}', str(checksum)):
      raise ValueError('El manifiesto contiene una ruta o hash no válido')
    target = APP_PATH + '/' + name
    expected.add(target)
    if digest(content(target)) != checksum:
      raise ValueError('Hash de archivo incorrecto: ' + name)
  if set(normalized) != expected:
    raise ValueError('El paquete contiene archivos ausentes o ajenos: ' + ', '.join(sorted(set(normalized) ^ expected)))
  release = content(APP_PATH + '/VERSION').decode().strip()
  if release != document.get('release'):
    raise ValueError('La versión del paquete no coincide con VERSION')
  info = content('.PKGINFO').decode()
  versions = [line.removeprefix('pkgver = ') for line in info.splitlines() if line.startswith('pkgver = ')]
  match = re.fullmatch(re.escape(arch_version(release)) + r'-([1-9][0-9]*)', versions[0]) if len(versions) == 1 else None
  if '\npkgname = hyprlarp\n' not in '\n' + info or not match:
    raise ValueError('El nombre o versión Arch no coincide con VERSION')
  pkgrel = package_release(int(match[1]))
  dependencies = {line.removeprefix('depend = ') for line in info.splitlines() if line.startswith('depend = ')}
  if dependencies != set(DEPENDENCIES):
    raise ValueError('Las dependencias del paquete no coinciden con la receta')
  for name in ('hyprlarp', 'hyprlarp-greeter'):
    expected_wrapper = ('#!/bin/sh\nexec /usr/share/hyprlarp/bin/' + name + ' "$@"\n').encode()
    if content('usr/bin/' + name) != expected_wrapper:
      raise ValueError('El comando global no apunta al paquete')
  if content('usr/share/applications/hyprlarp-settings.desktop') != DESKTOP_ENTRY:
    raise ValueError('La entrada de configuración no apunta al paquete')
  for installed, original in [('usr/share/icons/hicolor/scalable/apps/hyprlarp.svg', 'assets/hyprlarp-desktop.svg'),
    ('usr/share/licenses/hyprlarp/LICENSE', 'LICENSE')]:
    if content(installed) != content(APP_PATH + '/' + original):
      raise ValueError('El recurso global no coincide con el paquete: ' + installed)
  return {'type': 'hyprlarp-package-check', 'release': release, 'pkgrel': pkgrel, 'files': len(document['files']),
    'sha256': digest(package.read_bytes()), 'ok': True}


def main():
  parser = argparse.ArgumentParser(description=__doc__)
  commands = parser.add_subparsers(dest='command', required=True)
  for name in ('prepare', 'build'):
    child = commands.add_parser(name)
    child.add_argument('--output', type=Path, required=True)
    child.add_argument('--source', type=Path, default=ROOT)
    child.add_argument('--epoch', type=int)
    child.add_argument('--pkgrel', type=int, default=1, help='Revisión del empaquetado Arch, independiente de VERSION')
    if name == 'build':
      child.add_argument('--nodeps', action='store_true', help='No comprobar dependencias; nunca las instala')
      child.add_argument('--nocheck', action='store_true', help='Omitir check() de makepkg')
  child = commands.add_parser('stage')
  child.add_argument('--destdir', type=Path, required=True)
  child.add_argument('--source', type=Path, default=ROOT)
  child = commands.add_parser('verify')
  child.add_argument('package', type=Path)
  args = parser.parse_args()
  try:
    if args.command == 'prepare':
      result = prepare(args.output, root=args.source, epoch=args.epoch, pkgrel=args.pkgrel)
    elif args.command == 'build':
      result = {'package': str(build(args.output, root=args.source, nodeps=args.nodeps,
        nocheck=args.nocheck, epoch=args.epoch, pkgrel=args.pkgrel))}
    elif args.command == 'stage':
      document = stage(args.destdir, root=args.source)
      result = {'release': document['release'], 'files': len(document['files'])}
    else:
      result = verify(args.package)
    print(json.dumps(result, ensure_ascii=False, indent=2))
  except (OSError, ValueError, subprocess.SubprocessError, tarfile.TarError) as error:
    parser.exit(1, str(error) + '\n')


if __name__ == '__main__':
  main()
