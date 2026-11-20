#!/usr/bin/env python3
"""Internal lifecycle probe, invoked only by clean_check inside its sandbox."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import pwd
import stat
import subprocess
import sys

APP = Path('/usr/share/hyprlarp')
HOME = Path(os.environ.get('HOME', '/home/qa'))
CONFIG = HOME / '.config/hyprlarp'
STATE = HOME / '.hyprlarp-clean-check.json'
PREFIX = 'HYPRLARP_CLEAN_RESULT '
GREETER_FILES = ['/etc/greetd/config.toml', '/usr/local/bin/hyprlarp-greeter-session',
  '/usr/local/libexec/hyprlarp-greeter-ui', '/var/lib/hyprlarp-greeter/lifecycle.json']


def command(arguments, *, check=True, timeout=300, cwd=None):
  result = subprocess.run(arguments, capture_output=True, text=True, timeout=timeout, cwd=cwd)
  if result.stdout:
    print(result.stdout, end='' if result.stdout.endswith('\n') else '\n', flush=True)
  if result.stderr:
    print(result.stderr, end='' if result.stderr.endswith('\n') else '\n', file=sys.stderr, flush=True)
  if check and result.returncode:
    raise RuntimeError('Falló ' + arguments[0] + ': ' + str(result.returncode))
  return result


def snapshot(paths, *, relative=None):
  result = {}
  for path in paths:
    path = Path(path)
    name = str(path.relative_to(relative)) if relative else str(path)
    if not path.exists() and not path.is_symlink():
      result[name] = None
      continue
    if path.is_symlink() or not path.is_file():
      raise RuntimeError('Se esperaba un archivo regular: ' + str(path))
    value = path.stat()
    result[name] = {'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
      'mode': stat.S_IMODE(value.st_mode), 'inode': value.st_ino}
  return result


def tree_state(root):
  return {str(path.relative_to(root)): {'mode': stat.S_IMODE(path.lstat().st_mode),
    'kind': 'link' if path.is_symlink() else 'directory' if path.is_dir() else 'file',
    'content': os.readlink(path) if path.is_symlink() else hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else ''}
    for path in sorted(root.rglob('*'))}


def state():
  return json.loads(STATE.read_text())


def verify_preserved(original, *, names=None):
  selected = {name: value for name, value in original.items() if names is None or name in names}
  actual = snapshot([CONFIG / name for name in selected], relative=CONFIG)
  if actual != selected:
    raise RuntimeError('Los ajustes o binds activos cambiaron: ' + ', '.join(name for name in selected if actual[name] != selected[name]))
  return actual


def versions(expected):
  result = {}
  for name, arguments in [('shell', ['/usr/bin/hyprlarp', '--version']),
    ('backend', ['/usr/bin/python3', str(APP / 'backend/service.py'), '--version']),
    ('greeter', ['/usr/bin/hyprlarp-greeter', '--version'])]:
    result[name] = command(arguments, timeout=15).stdout.strip()
    if not result[name].endswith(' ' + expected):
      raise RuntimeError('La versión de ' + name + ' no coincide con el paquete')
  return result


def package_phase(phase, package):
  if os.geteuid() != 0:
    raise RuntimeError('La fase de pacman necesita root dentro del aislamiento')
  before_greeter = snapshot(map(Path, GREETER_FILES))
  if phase == 'install':
    if command(['pacman', '-Q', 'hyprlarp'], check=False).returncode == 0:
      raise RuntimeError('La raíz de prueba ya tiene HyprLarp instalado')
    try:
      pwd.getpwuid(1000)
    except KeyError:
      # A bootstrap rootfs has only system accounts. Ownership checks need a
      # real passwd identity even when the UID runs inside a user namespace.
      command(['useradd', '--uid', '1000', '--user-group', '--no-create-home',
        '--home-dir', '/home/qa', '--shell', '/usr/bin/bash', 'hyprlarp-qa'])
    dependencies = command(['pacman', '-Q']).stdout.splitlines()
    command(['pacman', '-U', '--noconfirm', '--needed', package])
    result = {'packages_before': dependencies, 'installed': command(['pacman', '-Q', 'hyprlarp']).stdout.strip()}
  elif phase == 'upgrade':
    before = command(['pacman', '-Q', 'hyprlarp']).stdout.strip()
    command(['pacman', '-U', '--noconfirm', package])
    after = command(['pacman', '-Q', 'hyprlarp']).stdout.strip()
    comparison = int(command(['vercmp', after.split()[1], before.split()[1]]).stdout.strip())
    if comparison < 0:
      raise RuntimeError('La prueba no admite una degradación de paquete')
    result = {'before': before, 'installed': after, 'kind': 'upgrade' if comparison > 0 else 'same-version-reinstall'}
  else:
    command(['pacman', '-Qkk', 'hyprlarp'])
    command(['pacman', '-R', '--noconfirm', 'hyprlarp'])
    if command(['pacman', '-Q', 'hyprlarp'], check=False).returncode == 0 or APP.exists():
      raise RuntimeError('El paquete no se retiró completamente')
    result = {'packages_after': command(['pacman', '-Q']).stdout.splitlines(), 'removed': True}
  if snapshot(map(Path, GREETER_FILES)) != before_greeter:
    raise RuntimeError('La operación modificó la integración del greeter')
  result['greeter_unchanged'] = True
  return result


def setup(expected):
  if os.geteuid() != 1000:
    raise RuntimeError('La integración debe probarse con el usuario 1000')
  if CONFIG.exists():
    raise RuntimeError('HOME debe empezar sin configuración de HyprLarp')
  current_versions = versions(expected)
  original_home = tree_state(HOME)
  command(['/usr/bin/hyprlarp', 'setup', '--dry-run'])
  if tree_state(HOME) != original_home:
    raise RuntimeError('El plan de setup escribió en HOME')
  command(['/usr/bin/hyprlarp', 'setup'])
  marker = CONFIG / '.hyprlarp-session.json'
  document = json.loads(marker.read_text())
  if document.get('type') != 'hyprlarp-session' or document.get('first_run') is not True:
    raise RuntimeError('La instalación nueva no quedó identificada para el asistente')
  if (HOME / '.local/share/hyprlarp/shell.qml').exists() or (HOME / '.local/bin/hyprlarp').exists():
    raise RuntimeError('setup duplicó o sustituyó el programa global dentro de HOME')
  if stat.S_IMODE(CONFIG.stat().st_mode) != 0o700:
    raise RuntimeError('La carpeta de ajustes no es privada')
  sys.path.insert(0, str(APP))
  from backend.service import Store
  store = Store(CONFIG)
  shortcuts = {**store.settings['shortcuts'], 'lock': 'SUPER SHIFT, L'}
  store.update({'font': 'Sans Serif', 'shortcuts': shortcuts})
  bindings = CONFIG / 'bindings.lua'
  bindings.write_text('-- clean-check: keep the active personal binding\n' + bindings.read_text())
  personal = CONFIG / 'qa-personal.txt'
  personal.write_text('Keep personal configuration\n')
  personal.chmod(0o600)
  names = ['settings.json', 'settings-history.json', 'bindings.lua', 'window-gaps.conf', 'hypridle.conf', 'qa-personal.txt']
  original = snapshot([CONFIG / name for name in names], relative=CONFIG)
  if any(value is None for value in original.values()):
    raise RuntimeError('Faltan archivos de integración del usuario')
  STATE.write_text(json.dumps({'protected': original}) + '\n')
  STATE.chmod(0o600)
  command(['/usr/bin/hyprlarp', 'setup'])
  verify_preserved(original)
  return {'versions': current_versions, 'first_run': True, 'no_application_copy': True,
    'settings_private': True, 'protected': original, 'repeat_setup_preserves_active_files': True}


def verify_user(expected, *, backend_tests=True):
  original = state()['protected']
  verify_preserved(original)
  current_versions = versions(expected)
  command(['/usr/bin/hyprlarp', 'setup'])
  verify_preserved(original)
  checks = {'backend': 'skipped by explicit option'}
  if backend_tests:
    command(['/usr/bin/python3', 'tools/check.py', '--backend-only'], cwd=APP, timeout=900)
    checks['backend'] = 'passed'
  command(['dbus-run-session', '--', '/usr/bin/python3', 'tools/check.py', '--ui-only'], cwd=APP, timeout=180)
  checks['interface'] = 'passed'
  verify_preserved(original)
  return {'versions': current_versions, 'preserved_after_package_upgrade': True, 'checks': checks}


def teardown():
  original = state()['protected']
  before = tree_state(CONFIG)
  command(['/usr/bin/hyprlarp', 'teardown', '--dry-run'])
  if tree_state(CONFIG) != before:
    raise RuntimeError('El plan de retirada cambió archivos del usuario')
  command(['/usr/bin/hyprlarp', 'teardown'])
  retained = ['settings.json', 'settings-history.json', 'bindings.lua', 'qa-personal.txt']
  verify_preserved(original, names=retained)
  if (CONFIG / '.hyprlarp-session.json').exists():
    raise RuntimeError('La integración del usuario sigue registrada')
  return {'preserved_preferences_and_history': True, 'preserved_modified_bindings': True,
    'preserved_personal_file': True, 'retained': retained}


def final():
  retained = ['settings.json', 'settings-history.json', 'bindings.lua', 'qa-personal.txt']
  preserved = verify_preserved(state()['protected'], names=retained)
  if Path('/usr/bin/hyprlarp').exists() or APP.exists():
    raise RuntimeError('El programa global sigue instalado')
  return {'preserved_after_package_removal': preserved}


def main():
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument('--internal', action='store_true')
  parser.add_argument('phase', choices=['install', 'upgrade', 'setup', 'verify', 'teardown', 'remove', 'final'])
  parser.add_argument('--package')
  parser.add_argument('--release')
  parser.add_argument('--skip-backend-tests', action='store_true')
  args = parser.parse_args()
  if not args.internal or os.environ.get('HYPRLARP_CLEAN_GUEST') != '1':
    parser.error('Este helper solo se ejecuta mediante tools/clean_check.py dentro del aislamiento')
  try:
    HOME.mkdir(parents=True, exist_ok=True)
    Path(os.environ['XDG_RUNTIME_DIR']).mkdir(parents=True, exist_ok=True, mode=0o700)
    if args.phase in {'install', 'upgrade', 'remove'}:
      result = package_phase(args.phase, args.package)
    elif args.phase == 'setup':
      result = setup(args.release)
    elif args.phase == 'verify':
      result = verify_user(args.release, backend_tests=not args.skip_backend_tests)
    elif args.phase == 'teardown':
      result = teardown()
    else:
      result = final()
    print(PREFIX + json.dumps({'ok': True, 'phase': args.phase, 'result': result}), flush=True)
  except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
    print(PREFIX + json.dumps({'ok': False, 'phase': args.phase, 'error': str(error)}), flush=True)
    raise SystemExit(1)


if __name__ == '__main__':
  main()
