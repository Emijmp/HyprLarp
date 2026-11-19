#!/usr/bin/env python3
"""Install the optional HyprLarp appearance bridge for Noctalia Greeter/greetd."""

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import pwd
import shlex
import shutil
import subprocess
import sys
import tempfile
import tomllib

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
from backend.greeter import DEFAULT_GREETER, HELPER, GREETER_STATE, GREETER_UI, PREFERENCES, atomic_write, dump_toml

UNIT = 'hyprlarp-greeter-sync'
SYNC_FILES = ['backend/greeter.py', 'backend/theme_context.py', 'config/palettes.json']
DYNAMIC_APPEARANCE = {'theme_mode', 'corner_radius_scale', 'font_family', 'palette', 'wallpaper', 'wallpapers'}
UI_LAUNCHER = Path('/usr/local/libexec/hyprlarp-greeter-ui')
SESSION_LAUNCHER = Path('/usr/local/bin/hyprlarp-greeter-session')


def session_launcher(ui=UI_LAUNCHER):
  # noctalia-greeter-session derives GREETER_BIN from NOCTALIA_GREETER_BIN.
  # Exporting GREETER_BIN alone is overwritten by the upstream launcher.
  return '#!/bin/sh\nexport NOCTALIA_GREETER_BIN=' + shlex.quote(str(ui)) + '\nexec /usr/bin/noctalia-greeter-session "$@"\n'


def run(args, **kwargs):
  result = subprocess.run(args, capture_output=True, text=True, timeout=60, **kwargs)
  if result.returncode:
    raise RuntimeError((result.stderr or result.stdout).strip()[-2000:] or 'Falló: ' + args[0])
  return result.stdout.strip()


def no_symlinks(path):
  for candidate in [path, *path.parents]:
    if candidate.is_symlink():
      raise ValueError('No se escribe a través de enlaces simbólicos: ' + str(candidate))


def merge_greeter(current):
  result = {**current}
  appearance = {key: value for key, value in current.get('appearance', {}).items() if key not in DYNAMIC_APPEARANCE}
  result['appearance'] = {**appearance, **DEFAULT_GREETER['appearance']}
  result['clock'] = {**DEFAULT_GREETER['clock'], **current.get('clock', {})}
  return result


def unit_argument(value):
  value = str(value).replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%').replace('$', '$$')
  return '"' + value + '"'


def user_units(app, config):
  arguments = ['/usr/bin/python3', app / 'backend/greeter.py', 'sync', '--settings', config / 'hyprlarp/settings.json',
    '--waypaper', config / 'waypaper/config.ini']
  service = '[Unit]\nDescription=Sincronizar greetd con HyprLarp\nStartLimitIntervalSec=0\n\n[Service]\nType=oneshot\n'
  service += 'UMask=0077\nNice=10\nTimeoutStartSec=45\nExecStartPre=/usr/bin/sleep 1\n'
  service += 'ExecStart=' + ' '.join(unit_argument(value) for value in arguments) + '\n'
  watcher = '[Unit]\nDescription=Observar el fondo y la apariencia de HyprLarp\n\n[Path]\n'
  for path in [config / 'hyprlarp/settings.json', config / 'waypaper/config.ini']:
    watcher += 'PathChanged=' + str(path).replace('%', '%%') + '\n'
  watcher += 'Unit=' + UNIT + '.service\n\n[Install]\nWantedBy=default.target\n'
  return {UNIT + '.service': service, UNIT + '.path': watcher}


def install_ui(backup, stamp):
  for path in [GREETER_UI, UI_LAUNCHER, SESSION_LAUNCHER]:
    no_symlinks(path)
  GREETER_UI.parent.mkdir(parents=True, exist_ok=True)
  stage = Path(tempfile.mkdtemp(prefix='.hyprlarp-greeter-ui-', dir=GREETER_UI.parent))
  try:
    stage.chmod(0o755)
    (stage / 'greeter').mkdir(mode=0o755)
    (stage / 'greeter').chmod(0o755)
    (stage / 'assets').mkdir(mode=0o755)
    (stage / 'assets').chmod(0o755)
    files = list((ROOT / 'greeter').glob('*.qml')) + [ROOT / 'greeter/model.py', ROOT / 'greeter/branding.js']
    if not any(path.name == 'shell.qml' for path in files):
      raise ValueError('Falta la interfaz de HyprLarp Greeter en el paquete')
    for source in files:
      if source.is_symlink() or not source.is_file():
        raise ValueError('Archivo de interfaz no válido: ' + str(source))
      destination = stage / 'greeter' / source.name
      shutil.copyfile(source, destination)
      destination.chmod(0o644)
    for name in ['hyprlarp.svg', 'error.svg', 'application.svg']:
      source = ROOT / 'assets' / name
      if source.is_symlink() or not source.is_file():
        raise ValueError('Recurso de identidad no válido: ' + str(source))
      destination = stage / 'assets' / name
      shutil.copyfile(source, destination)
      destination.chmod(0o644)
    if GREETER_UI.exists():
      shutil.copytree(GREETER_UI, backup / 'ui', symlinks=True)
      GREETER_UI.rename(GREETER_UI.with_name(GREETER_UI.name + '.backup-' + stamp))
    stage.rename(GREETER_UI)
  finally:
    if stage.exists():
      shutil.rmtree(stage)
  contents = {
    UI_LAUNCHER: '#!/bin/sh\nexport QT_QPA_PLATFORM=wayland\nexport QT_QUICK_CONTROLS_STYLE=Basic\n'
      'exec /usr/bin/quickshell --path ' + shlex.quote(str(GREETER_UI / 'greeter/shell.qml')) + '\n',
    SESSION_LAUNCHER: session_launcher(),
  }
  for target, text in contents.items():
    existed = target.parent.exists()
    target.parent.mkdir(parents=True, exist_ok=True)
    if not existed:
      target.parent.chmod(0o755)
    if target.exists():
      shutil.copy2(target, backup / target.name)
    atomic_write(target, text.encode())
    target.chmod(0o755)


def prepare_preferences(account, greeter, backup):
  no_symlinks(PREFERENCES)
  folder = PREFERENCES.parent
  if folder.exists():
    shutil.copytree(folder, backup / 'preferences', symlinks=True)
  folder.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
  os.chown(folder.parent, 0, 0)
  folder.parent.chmod(0o755)
  folder.mkdir(exist_ok=True)
  os.chown(folder, account.pw_uid, greeter.pw_gid)
  # New atomic files inherit the greeter group; other users cannot read the directory.
  folder.chmod(0o2750)
  if PREFERENCES.exists():
    if not PREFERENCES.is_file():
      raise ValueError('Las preferencias deben ser un archivo regular')
    os.chown(PREFERENCES, account.pw_uid, greeter.pw_gid)
    PREFERENCES.chmod(0o640)


def system_setup(username):
  if os.geteuid() != 0:
    raise ValueError('La preparación del sistema necesita permisos de administrador')
  account = pwd.getpwnam(username)
  if account.pw_uid == 0:
    raise ValueError('Elige el usuario del escritorio, no root')
  if run([str(HELPER), '--supports', 'secure-sync-v1']) != 'secure-sync-v1':
    raise RuntimeError('El helper instalado no admite la sincronización restringida')
  greetd = Path('/etc/greetd/config.toml')
  current_greetd = tomllib.loads(greetd.read_text()) if greetd.is_file() else {'terminal': {'vt': 1}}
  greeter_name = current_greetd.get('default_session', {}).get('user', 'greeter')
  greeter = pwd.getpwnam(greeter_name)
  stamp = datetime.now().strftime('%Y%m%d-%H%M%S-%f')
  backup = Path('/var/backups/hyprlarp-greeter') / stamp
  backup.mkdir(parents=True, mode=0o700)
  backup.parent.chmod(0o700)
  if greetd.exists():
    shutil.copy2(greetd, backup / 'greetd.toml')
  if GREETER_STATE.exists():
    shutil.copytree(GREETER_STATE, backup / 'state', symlinks=True)
  run([str(HELPER), '--setup-system'], env={**os.environ, 'GREETER_USER': greeter_name})
  target = GREETER_STATE / 'greeter.toml'
  no_symlinks(target)
  current = tomllib.loads(target.read_text()) if target.is_file() else {}
  updated = dump_toml(merge_greeter(current))
  tomllib.loads(updated)
  atomic_write(target, updated.encode())
  os.chown(target, greeter.pw_uid, greeter.pw_gid)
  target.chmod(0o644)
  install_ui(backup, stamp)
  prepare_preferences(account, greeter, backup)
  wanted = {'command': str(SESSION_LAUNCHER), 'user': greeter_name}
  if current_greetd.get('default_session') != wanted:
    no_symlinks(greetd)
    greetd.parent.mkdir(parents=True, exist_ok=True)
    current_greetd['default_session'] = wanted
    atomic_write(greetd, dump_toml(current_greetd).encode())
    greetd.chmod(0o644)
  # Upstream grants only its constrained appearance action to this active user.
  run(['/usr/bin/noctalia-greeter', 'passwordless-sync', 'enable', username])
  return {'backup': str(backup), 'greeter_user': greeter_name,
    'authorization': run(['/usr/bin/noctalia-greeter', 'passwordless-sync', 'status', username])}


def install_user(*, dry_run=False):
  if os.geteuid() == 0:
    raise ValueError('Ejecuta el instalador como tu usuario, sin sudo')
  home = Path.home()
  data = Path(os.environ.get('XDG_DATA_HOME', home / '.local/share'))
  config = Path(os.environ.get('XDG_CONFIG_HOME', home / '.config'))
  app = data / 'hyprlarp-greeter'
  launcher = home / '.local/bin/hyprlarp-greeter'
  units = config / 'systemd/user'
  contents = user_units(app, config)
  for path in [app, launcher, *[units / name for name in contents]]:
    no_symlinks(path)
    print(path)
  if not (config / 'hyprlarp/settings.json').is_file():
    raise ValueError('No se encontraron los ajustes de HyprLarp')
  if not HELPER.is_file():
    raise ValueError('Instala noctalia-greeter con su helper antes de continuar')
  if dry_run:
    print('Interfaz propia: ' + str(GREETER_UI))
    print('Preferencia de diseño: ' + str(PREFERENCES))
    print('Sistema: apariencia de greetd y autorización restringida para ' + pwd.getpwuid(os.getuid()).pw_name)
    print('Activar: ' + UNIT + '.path')
    return

  username = pwd.getpwuid(os.getuid()).pw_name
  command = ['/usr/bin/python3', str(Path(__file__).resolve()), '--system', username]
  cached = subprocess.run(['sudo', '-n', 'true'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
  prefix = ['sudo', '-n'] if cached else ['/usr/bin/pkexec']
  setup = json.loads(run(prefix + command))

  stamp = datetime.now().strftime('%Y%m%d-%H%M%S-%f')
  app.parent.mkdir(parents=True, exist_ok=True)
  stage = Path(tempfile.mkdtemp(prefix='.hyprlarp-greeter-stage-', dir=app.parent))
  try:
    for name in SYNC_FILES:
      source = ROOT / name
      if source.is_symlink():
        raise ValueError('El paquete contiene un enlace simbólico')
      destination = stage / name
      destination.parent.mkdir(parents=True, exist_ok=True)
      shutil.copy2(source, destination)
    atomic_write(stage / 'installation.json', (json.dumps(setup, indent=2) + '\n').encode())
    if app.exists():
      app.rename(app.with_name(app.name + '.backup-' + stamp))
    stage.rename(app)
  finally:
    if stage.exists():
      shutil.rmtree(stage)
  launcher.parent.mkdir(parents=True, exist_ok=True)
  if launcher.exists():
    shutil.copy2(launcher, launcher.with_name(launcher.name + '.backup-' + stamp))
  atomic_write(launcher, ('#!/bin/sh\nexec /usr/bin/python3 ' + shlex.quote(str(app / 'backend/greeter.py')) + ' "$@"\n').encode())
  launcher.chmod(0o755)
  units.mkdir(parents=True, exist_ok=True)
  for name, content in contents.items():
    target = units / name
    if target.exists():
      shutil.copy2(target, target.with_name(target.name + '.backup-' + stamp))
    atomic_write(target, content.encode())
  run(['systemctl', '--user', 'daemon-reload'])
  run(['systemctl', '--user', 'enable', '--now', UNIT + '.path'])
  run(['systemctl', '--user', 'start', UNIT + '.service'])
  print(json.dumps({'status': 'installed', **setup}, ensure_ascii=False, indent=2))
  print(run([str(launcher), 'status']))


def main():
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument('--dry-run', action='store_true')
  parser.add_argument('--system', metavar='USER', help=argparse.SUPPRESS)
  args = parser.parse_args()
  try:
    if args.system:
      print(json.dumps(system_setup(args.system)))
    else:
      install_user(dry_run=args.dry_run)
  except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
    parser.exit(1, str(error) + '\n')


if __name__ == '__main__':
  main()
