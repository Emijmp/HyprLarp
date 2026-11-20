#!/usr/bin/env python3
"""Exercise a real Arch package in a private rootfs or an explicit CI container."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
GUEST = Path(__file__).resolve().with_name('clean_guest.py')
RESULT_PREFIX = 'HYPRLARP_CLEAN_RESULT '
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))


def absolute(value):
  path = Path(value).expanduser().absolute()
  if any(ord(character) < 32 for character in str(path)):
    raise ValueError('La ruta contiene caracteres de control')
  return path


def container_allowed():
  return os.geteuid() == 0 and (Path('/.dockerenv').is_file() or Path('/run/.containerenv').is_file())


def validate_rootfs(rootfs, output):
  path = absolute(rootfs).resolve()
  output = absolute(output).resolve()
  if path == Path('/') or ROOT.is_relative_to(path) or path == Path.home().resolve():
    raise ValueError('La raíz de prueba debe ser un rootfs privado, nunca el sistema anfitrión')
  if path.is_relative_to(output) or output.is_relative_to(path):
    raise ValueError('El rootfs y la carpeta de resultados deben estar separados')
  if not all((path / name).is_file() for name in ['usr/bin/python3', 'usr/bin/pacman', 'etc/os-release']):
    raise ValueError('La raíz de prueba no contiene Python, pacman y os-release')
  return path


def environment(home, *, uid):
  return {'PATH': '/usr/bin:/bin', 'HOME': str(home), 'USER': 'qa' if uid else 'root',
    'LOGNAME': 'qa' if uid else 'root', 'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8',
    'XDG_CONFIG_HOME': str(home / '.config'), 'XDG_DATA_HOME': str(home / '.local/share'),
    'XDG_CACHE_HOME': str(home / '.cache'), 'XDG_STATE_HOME': str(home / '.local/state'),
    'XDG_RUNTIME_DIR': str(home / '.runtime'), 'PYTHONDONTWRITEBYTECODE': '1',
    'QT_QPA_PLATFORM': 'offscreen', 'QT_QUICK_BACKEND': 'software', 'HYPRLARP_CLEAN_GUEST': '1'}


def bubble_command(rootfs, package, home, phase, *, uid, release, backend_tests=True):
  binary = shutil.which('bwrap')
  if not binary:
    raise ValueError('Falta bubblewrap para aislar la prueba')
  guest_home = Path('/home/qa') if uid else Path('/tmp/hyprlarp-root')
  arguments = [binary, '--unshare-all', '--die-with-parent', '--new-session', '--uid', str(uid), '--gid', str(uid),
    '--bind' if uid == 0 else '--ro-bind', str(rootfs), '/', '--proc', '/proc', '--dev', '/dev',
    '--tmpfs', '/tmp', '--tmpfs', '/run', '--tmpfs', '/home', '--dir', '/home/qa',
    '--bind', str(home), '/home/qa', '--ro-bind', str(GUEST), '/tmp/hyprlarp-clean-guest.py']
  if package is not None:
    arguments += ['--ro-bind', str(package), '/tmp/hyprlarp-input.pkg.tar.zst']
  arguments += ['--chdir', '/tmp', '--clearenv']
  for key, value in environment(guest_home, uid=uid).items():
    arguments += ['--setenv', key, value]
  arguments += ['/usr/bin/python3', '/tmp/hyprlarp-clean-guest.py', '--internal', phase, '--release', release]
  if package is not None:
    arguments += ['--package', '/tmp/hyprlarp-input.pkg.tar.zst']
  if not backend_tests:
    arguments.append('--skip-backend-tests')
  return arguments


def container_command(package, home, phase, *, uid, release, username, backend_tests=True):
  arguments = []
  if uid:
    arguments += ['runuser', '-u', username, '--']
  arguments += ['/usr/bin/env', '-i']
  for key, value in environment(home if uid else Path('/tmp/hyprlarp-root'), uid=uid).items():
    arguments.append(key + '=' + value)
  arguments += ['/usr/bin/python3', str(GUEST), '--internal', phase, '--release', release]
  if package is not None:
    arguments += ['--package', str(package)]
  if not backend_tests:
    arguments.append('--skip-backend-tests')
  return arguments


def phase_result(output):
  records = [line[len(RESULT_PREFIX):] for line in output.splitlines() if line.startswith(RESULT_PREFIX)]
  if len(records) != 1:
    raise RuntimeError('La fase no devolvió un resultado inequívoco; revisa su registro')
  result = json.loads(records[0])
  if not isinstance(result, dict):
    raise RuntimeError('La fase devolvió un resultado con formato inválido')
  if result.get('ok') is not True:
    raise RuntimeError(result.get('error', 'Falló la comprobación dentro del aislamiento'))
  if not isinstance(result.get('result'), dict):
    raise RuntimeError('La fase no incluyó sus comprobaciones')
  return result['result']


def run_phase(arguments, output, name, *, timeout):
  started = time.monotonic()
  try:
    result = subprocess.run(arguments, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
      timeout=timeout)
  except subprocess.TimeoutExpired as error:
    content = error.stdout or ''
    if isinstance(content, bytes):
      content = content.decode(errors='replace')
    (output / (name + '.log')).write_text(content, encoding='utf-8')
    raise RuntimeError(name + ': se superó el límite de ' + str(timeout) + ' segundos; revisa su registro') from error
  (output / (name + '.log')).write_text(result.stdout, encoding='utf-8')
  if result.returncode:
    try:
      phase_result(result.stdout)
    except (RuntimeError, ValueError) as error:
      raise RuntimeError(name + ': ' + str(error)) from error
    raise RuntimeError(name + ': el proceso terminó con código ' + str(result.returncode))
  return {'status': 'passed', 'seconds': round(time.monotonic() - started, 2), 'result': phase_result(result.stdout)}


def check(package, output, *, rootfs=None, upgrade_package=None, use_rootfs_workspace=False,
    container=False, backend_tests=True, timeout=1200, keep_workspace=False,
    rootfs_id=None, rootfs_sha256=None):
  if container:
    if rootfs is not None or use_rootfs_workspace:
      raise ValueError('--container no admite --rootfs ni --use-rootfs-workspace')
    if not container_allowed():
      raise ValueError('--container solo se admite como root en un contenedor identificado explícitamente')
  elif rootfs is None:
    raise ValueError('Proporciona --rootfs; no se instala nada en el anfitrión')
  if not 30 <= timeout <= 3600:
    raise ValueError('El límite por fase debe estar entre 30 y 3600 segundos')
  if rootfs_sha256 is not None and not re.fullmatch('[0-9a-f]{64}', rootfs_sha256):
    raise ValueError('La suma del rootfs debe ser un SHA-256 válido')
  output = absolute(output)
  if output.is_symlink():
    raise ValueError('La carpeta de resultados no puede ser un enlace simbólico')
  selected_root = None if container else validate_rootfs(rootfs, output)
  package = absolute(package)
  upgrade = absolute(upgrade_package) if upgrade_package else package
  for path in {package, upgrade}:
    if path.is_symlink() or not path.is_file():
      raise ValueError('El paquete debe ser un archivo regular')
  from tools.package import verify
  package_info = verify(package)
  upgrade_info = verify(upgrade)
  output.mkdir(parents=True, exist_ok=True)
  report = {'type': 'hyprlarp-clean-validation', 'version': 1,
    'started': datetime.now(timezone.utc).isoformat(), 'ok': False,
    'isolation': 'explicit CI container' if container else 'bubblewrap; private rootfs; no network',
    'rootfs': {'id': rootfs_id or 'pre-provisioned Arch rootfs', 'provisioned_archive_sha256': rootfs_sha256},
    'package': package_info, 'upgrade_package': upgrade_info, 'steps': {}}
  work = Path(tempfile.mkdtemp(prefix='clean-work-', dir=output))
  home = work / 'home'
  home.mkdir(mode=0o700)
  installed = removed = False
  username = None
  try:
    if container:
      try:
        username = pwd.getpwuid(1000).pw_name
      except KeyError:
        subprocess.run(['useradd', '--uid', '1000', '--user-group', '--no-create-home', 'hyprlarp-qa'], check=True)
        username = 'hyprlarp-qa'
      os.chown(home, 1000, pwd.getpwnam(username).pw_gid)
      # The unprivileged probe must traverse its disposable work directory.
      work.chmod(0o755)
      current_root = None
    elif use_rootfs_workspace:
      current_root = selected_root
    else:
      current_root = work / 'rootfs'
      shutil.copytree(selected_root, current_root, symlinks=True)
    def invoke(name, *, uid, selected_package=None, release=None):
      arguments = container_command(selected_package, home, name, uid=uid,
        release=release or upgrade_info['release'], username=username, backend_tests=backend_tests) if container else \
        bubble_command(current_root, selected_package, home, name, uid=uid,
          release=release or upgrade_info['release'], backend_tests=backend_tests)
      value = run_phase(arguments, output, name, timeout=timeout)
      report['steps'][name] = value
      print('CLEAN ' + name + ' passed', flush=True)
      return value['result']
    initial = invoke('install', uid=0, selected_package=package, release=package_info['release'])
    installed = True
    invoke('setup', uid=1000, release=package_info['release'])
    transition = invoke('upgrade', uid=0, selected_package=upgrade)
    if upgrade_package and transition['kind'] != 'upgrade':
      raise RuntimeError('--upgrade-package no produjo una actualización de versión o pkgrel')
    invoke('verify', uid=1000)
    invoke('teardown', uid=1000)
    final_packages = invoke('remove', uid=0)
    removed = True
    if set(initial['packages_before']) != set(final_packages['packages_after']):
      raise RuntimeError('La retirada alteró paquetes ajenos a HyprLarp')
    invoke('final', uid=1000)
    report['dependencies_preserved'] = True
    report['upgrade_kind'] = transition['kind']
    report['ok'] = True
  except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
    report['error'] = str(error)
    if installed and not removed:
      try:
        invoke('remove', uid=0)
        report['removed_after_failure'] = True
      except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as cleanup_error:
        report['cleanup_error'] = str(cleanup_error)
  finally:
    report['finished'] = datetime.now(timezone.utc).isoformat()
    report['workspace_kept'] = keep_workspace
    (output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    if not keep_workspace:
      shutil.rmtree(work)
  return report


def main():
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument('--rootfs', type=Path)
  parser.add_argument('--package', required=True, type=Path)
  parser.add_argument('--upgrade-package', type=Path)
  parser.add_argument('--output', required=True, type=Path)
  parser.add_argument('--use-rootfs-workspace', action='store_true', help='Usar y modificar el rootfs privado dado en vez de copiarlo')
  parser.add_argument('--container', action='store_true', help='Ejecutar únicamente dentro de un contenedor CI explícito, con uid0')
  parser.add_argument('--skip-backend-tests', action='store_true')
  parser.add_argument('--keep-workspace', action='store_true')
  parser.add_argument('--timeout', type=int, default=1200, help='Límite por fase, en segundos')
  parser.add_argument('--rootfs-id')
  parser.add_argument('--rootfs-sha256')
  args = parser.parse_args()
  try:
    result = check(args.package, args.output, rootfs=args.rootfs, upgrade_package=args.upgrade_package,
      use_rootfs_workspace=args.use_rootfs_workspace, container=args.container,
      backend_tests=not args.skip_backend_tests, timeout=args.timeout, keep_workspace=args.keep_workspace,
      rootfs_id=args.rootfs_id, rootfs_sha256=args.rootfs_sha256)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return int(not result['ok'])
  except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
    parser.exit(1, str(error) + '\n')


if __name__ == '__main__':
  raise SystemExit(main())
