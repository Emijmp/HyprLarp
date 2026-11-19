#!/usr/bin/env python3
"""Install the optional HyprLarp appearance bridge for Noctalia Greeter/greetd."""

import argparse
import copy
import hashlib
import re
import uuid
from datetime import datetime
import json
import os
from pathlib import Path
import pwd
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import tomllib

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
from backend.greeter import DEFAULT_GREETER, HELPER, GREETER_STATE, GREETER_UI, PREFERENCES, atomic_write, dump_toml
from backend.version import VERSION
from tools.greeter_lifecycle import Snapshot, locked, fingerprint

UNIT = 'hyprlarp-greeter-sync'
SYNC_FILES = ['backend/greeter.py', 'backend/theme_context.py', 'config/palettes.json',
  'tools/install_greeter.py', 'tools/greeter_lifecycle.py']
UI_FILES = ['greeter/' + name for name in ['shell.qml', 'BrandIcon.qml', 'ControlButton.qml', 'Controller.qml',
  'GreeterView.qml', 'SessionChoice.qml', 'model.py', 'branding.js']] + ['assets/' + name for name in
  ['hyprlarp.svg', 'error.svg', 'application.svg']] + ['VERSION', 'backend/__init__.py', 'backend/version.py']
SYNC_FILES += UI_FILES
DYNAMIC_APPEARANCE = {'theme_mode', 'corner_radius_scale', 'font_family', 'palette', 'wallpaper', 'wallpapers'}
UI_LAUNCHER = Path('/usr/local/libexec/hyprlarp-greeter-ui')
SESSION_LAUNCHER = Path('/usr/local/bin/hyprlarp-greeter-session')
GREETD = Path('/etc/greetd/config.toml')
BACKUPS = Path('/var/backups/hyprlarp-greeter')
SYSTEM_MANIFEST = Path('/var/lib/hyprlarp-greeter/lifecycle.json')
POLKIT_RULE = Path('/etc/polkit-1/rules.d/49-noctalia-greeter-passwordless-sync.rules')


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
    for name in ['greeter', 'assets', 'backend']:
      (stage / name).mkdir(mode=0o755)
      (stage / name).chmod(0o755)
    if not (ROOT / 'greeter/shell.qml').is_file():
      raise ValueError('Falta la interfaz de HyprLarp Greeter en el paquete')
    for relative in UI_FILES:
      source = ROOT / relative
      if source.is_symlink() or not source.is_file():
        raise ValueError('Archivo de interfaz no válido: ' + str(source))
      destination = stage / relative
      shutil.copyfile(source, destination)
      destination.chmod(0o644)
    if GREETER_UI.exists():
      # Keep unrelated files in place across an upgrade.
      for source in GREETER_UI.rglob('*'):
        no_symlinks(source)
        relative = source.relative_to(GREETER_UI)
        destination = stage / relative
        if source.is_file() and not destination.exists():
          destination.parent.mkdir(parents=True, exist_ok=True)
          shutil.copy2(source, destination)
      Snapshot.remove(GREETER_UI)
    stage.rename(GREETER_UI)
  finally:
    if stage.exists():
      shutil.rmtree(stage)
  contents = {
    UI_LAUNCHER: '#!/bin/sh\nexport QT_QPA_PLATFORM=wayland\nexport QT_QUICK_CONTROLS_STYLE=Basic\n'
      'exec /usr/bin/quickshell --path ' + shlex.quote(str(GREETER_UI / 'greeter/shell.qml')) + '\n',
    SESSION_LAUNCHER: session_launcher(UI_LAUNCHER),
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


def system_targets():
  return {'greetd': GREETD, 'state': GREETER_STATE, 'ui': GREETER_UI,
    'ui-launcher': UI_LAUNCHER, 'session-launcher': SESSION_LAUNCHER,
    'preferences': PREFERENCES.parent, 'polkit': POLKIT_RULE, 'manifest': SYSTEM_MANIFEST}


def identity(username):
  if os.geteuid() != 0:
    raise ValueError('La preparación del sistema necesita permisos de administrador')
  account = pwd.getpwnam(username)
  if account.pw_uid == 0:
    raise ValueError('Elige el usuario del escritorio, no root')
  return account


def load_system(username):
  if not SYSTEM_MANIFEST.exists():
    return None
  no_symlinks(SYSTEM_MANIFEST)
  if SYSTEM_MANIFEST.stat().st_uid != os.geteuid():
    raise ValueError('El manifiesto del greeter tiene un propietario inválido')
  data = json.loads(SYSTEM_MANIFEST.read_text())
  if data.get('type') != 'hyprlarp-greeter-system' or data.get('version') != 1 or data.get('user') != username:
    raise ValueError('El greeter está gestionado por otro usuario o su manifiesto es inválido')
  for name in ['baseline', 'owned', 'expected']:
    if name in data:
      path = Path(data[name])
      if not path.is_relative_to(BACKUPS) or '..' in path.parts:
        raise ValueError('Ruta de respaldo del greeter inválida')
      no_symlinks(path)
  return data


def save_system(data):
  SYSTEM_MANIFEST.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
  atomic_write(SYSTEM_MANIFEST, (json.dumps(data, indent=2) + '\n').encode())
  SYSTEM_MANIFEST.chmod(0o600)


def authorization(username):
  value = run(['/usr/bin/noctalia-greeter', 'passwordless-sync', 'status', username])
  return ': enabled ' in value or ': enabled\n' in value or value.endswith(': enabled')


def operation(username, action):
  token = uuid.uuid4().hex
  directory = BACKUPS / token
  no_symlinks(directory)
  directory.mkdir(parents=True, mode=0o700)
  BACKUPS.chmod(0o700)
  before = Snapshot.capture(directory / 'before', system_targets())
  atomic_write(directory / 'operation.json', (json.dumps({'type': 'hyprlarp-greeter-operation', 'version': 1,
    'user': username, 'action': action, 'token': token}) + '\n').encode())
  return token, directory, before


def original_snapshot(directory, targets, sources):
  """Import a legacy, root-owned backup without touching its live destinations."""
  snapshot = Snapshot.capture(directory, sources)
  document = json.loads((directory / 'snapshot.json').read_text())
  for name, path in targets.items():
    document['targets'][name]['path'] = str(path)
  atomic_write(directory / 'snapshot.json', (json.dumps(document, indent=2) + '\n').encode())
  return Snapshot(directory, targets)


def legacy_baseline(directory, greeter):
  for backup in sorted(BACKUPS.iterdir()):
    if not backup.is_dir() or not re.fullmatch(r'\d{8}-\d{6}-\d{6}', backup.name):
      continue
    no_symlinks(backup)
    if backup.stat().st_uid != os.geteuid():
      continue
    config = backup / 'greetd.toml'
    if not config.is_file():
      continue
    no_symlinks(config)
    previous = tomllib.loads(config.read_text())
    command = previous.get('default_session', {}).get('command', '')
    if not isinstance(command, str) or 'hyprlarp-greeter' in command:
      continue
    missing = directory / 'not-present'
    sources = {'greetd': config, 'state': backup / 'state', 'ui': backup / 'ui',
      'ui-launcher': backup / UI_LAUNCHER.name, 'session-launcher': backup / SESSION_LAUNCHER.name,
      'preferences': backup / 'preferences', 'polkit': POLKIT_RULE, 'manifest': missing}
    snapshot = original_snapshot(directory / 'baseline', system_targets(), sources)
    # Old copytree backups retained modes but their copies were owned by root.
    record = snapshot.records['state']
    if record['kind'] != 'missing':
      record.update(uid=greeter.pw_uid, gid=greeter.pw_gid)
      for item in record['entries'].values():
        item.update(uid=greeter.pw_uid, gid=greeter.pw_gid)
      document = json.loads((snapshot.directory / 'snapshot.json').read_text())
      document['targets'] = snapshot.records
      atomic_write(snapshot.directory / 'snapshot.json', (json.dumps(document, indent=2) + '\n').encode())
    return snapshot, str(backup)
  raise ValueError('No se encontró una copia anterior a HyprLarp; se conserva el greeter sin modificarlo')


def reject_ui_edits(manifest):
  if not manifest:
    return
  owned = Snapshot(Path(manifest['owned']), system_targets())
  for name in ['ui', 'ui-launcher', 'session-launcher']:
    root = system_targets()[name]
    for relative, item in owned.records[name]['entries'].items():
      if item['kind'] != 'file':
        continue
      path = root if relative == '.' else root / relative
      expected = {key: item[key] for key in ['sha256', 'mode', 'uid', 'gid']}
      if fingerprint(path) != expected:
        raise ValueError('Se conserva un archivo del greeter modificado; resuelve el cambio antes de actualizar: ' + str(path))


def record_hash(item):
  return {key: item[key] for key in ['sha256', 'mode', 'uid', 'gid']} if item and item['kind'] == 'file' else None


def snapshot_matches(snapshot, names):
  for name in names:
    target, record = snapshot.targets[name], snapshot.records[name]
    if target.is_symlink():
      return False
    if record['kind'] == 'missing':
      if target.exists():
        return False
      continue
    if record['kind'] == 'file':
      if not target.is_file() or fingerprint(target) != record_hash(record['entries'].get('.')):
        return False
      continue
    if not target.is_dir():
      return False
    info = target.stat()
    if any(value != record[key] for key, value in [('mode', stat.S_IMODE(info.st_mode)), ('uid', info.st_uid), ('gid', info.st_gid)]):
      return False
    actual = set()
    for path in target.rglob('*'):
      if path.is_symlink():
        return False
      relative = path.relative_to(target).as_posix()
      actual.add(relative)
      item = record['entries'].get(relative)
      if item is None or (path.is_dir() != (item['kind'] == 'directory')):
        return False
      if path.is_file() and fingerprint(path) != record_hash(item):
        return False
      if path.is_dir():
        info = path.stat()
        if any(value != item[key] for key, value in [('mode', stat.S_IMODE(info.st_mode)), ('uid', info.st_uid), ('gid', info.st_gid)]):
          return False
    if actual != set(record['entries']):
      return False
  return True


def keep_entries(record, allowed):
  files = {name: item for name, item in record['entries'].items() if item['kind'] == 'file' and name in allowed}
  parents = {parent.as_posix() for name in files for parent in Path(name).parents if parent.as_posix() != '.'}
  record['entries'] = {**files, **{name: item for name, item in record['entries'].items()
    if item['kind'] == 'directory' and name in parents}}


def restrict_system_owned(snapshot, *, previous=None, before=None, legacy=False):
  allowed_ui = set(UI_FILES)
  keep_entries(snapshot.records['ui'], allowed_ui)
  known_state = {'greeter.toml', 'sync.toml'}
  for name in snapshot.records['state']['entries']:
    path = Path(name)
    if (name.startswith('wallpapers/') or '/' not in name) and path.name.startswith('wallpaper') and path.suffix.lower() in {'.png', '.jpg', '.jpeg', '.webp', '.bmp', '.jxl'}:
      known_state.add(name)
  keep_entries(snapshot.records['state'], known_state)
  keep_entries(snapshot.records['preferences'], {'layout.json'})
  if legacy:
    # A legacy marker contains no old owned hashes. Only adopt verifiable UI.
    for name, item in list(snapshot.records['ui']['entries'].items()):
      if item['kind'] == 'file':
        source = ROOT / name
        if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest() != item['sha256']:
          snapshot.records['ui']['entries'].pop(name)
    expected = {UI_LAUNCHER: '#!/bin/sh\nexport QT_QPA_PLATFORM=wayland\nexport QT_QUICK_CONTROLS_STYLE=Basic\n'
      'exec /usr/bin/quickshell --path ' + shlex.quote(str(GREETER_UI / 'greeter/shell.qml')) + '\n',
      SESSION_LAUNCHER: session_launcher(UI_LAUNCHER)}
    for name, path in [('ui-launcher', UI_LAUNCHER), ('session-launcher', SESSION_LAUNCHER)]:
      if snapshot.data(name) != expected[path].encode():
        snapshot.records[name]['entries'] = {}
  if previous and before:
    old = Snapshot(Path(previous['owned']), system_targets())
    for name in ['state', 'preferences']:
      for relative, item in list(snapshot.records[name]['entries'].items()):
        previous_item = old.records[name]['entries'].get(relative)
        before_item = before.records[name]['entries'].get(relative)
        # Do not turn an earlier administrator change into our ownership on update.
        if item['kind'] == 'file' and previous_item and record_hash(before_item) != record_hash(previous_item):
          blob = str(1000000 + len(list((snapshot.directory / 'files').iterdir())))
          shutil.copyfile(old.directory / 'files' / previous_item['blob'], snapshot.directory / 'files' / blob)
          snapshot.records[name]['entries'][relative] = {**previous_item, 'blob': blob}
  document = json.loads((snapshot.directory / 'snapshot.json').read_text())
  document['targets'] = snapshot.records
  atomic_write(snapshot.directory / 'snapshot.json', (json.dumps(document, indent=2) + '\n').encode())


def reject_user_edits(installed, targets):
  owned = Snapshot(Path(installed['owned']), targets)
  for name, target in targets.items():
    for relative, item in owned.records[name]['entries'].items():
      if item['kind'] != 'file':
        continue
      path = target if relative == '.' else target / relative
      if not path.is_file() or fingerprint(path) != record_hash(item):
        raise ValueError('Se conserva un archivo de usuario modificado; resuelve el cambio antes de actualizar: ' + str(path))


def system_setup(username):
  account = identity(username)
  with locked(BACKUPS / '.lifecycle.lock'):
    manifest = load_system(username)
    if manifest and manifest.get('pending'):
      rollback_operation(username, manifest['operation'], strict=True)
      manifest = load_system(username)
    if manifest and not manifest.get('installed'):
      manifest = None
    no_symlinks(GREETD)
    if run([str(HELPER), '--supports', 'secure-sync-v1']) != 'secure-sync-v1':
      raise RuntimeError('El helper instalado no admite la sincronización restringida')
    current_greetd = tomllib.loads(GREETD.read_text()) if GREETD.is_file() else {'terminal': {'vt': 1}}
    greeter_name = current_greetd.get('default_session', {}).get('user', 'greeter')
    greeter = pwd.getpwnam(greeter_name)
    if manifest and current_greetd.get('default_session', {}).get('command') != str(SESSION_LAUNCHER):
      raise ValueError('greetd fue cambiado por el administrador; se conserva sin reactivar HyprLarp')
    reject_ui_edits(manifest)
    token, directory, before = operation(username, 'install')
    try:
      legacy = None
      if manifest:
        baseline = Path(manifest['baseline'])
        authorized = manifest['previous_authorization']
      elif 'hyprlarp-greeter' in current_greetd.get('default_session', {}).get('command', ''):
        imported, legacy = legacy_baseline(directory, greeter)
        baseline, authorized = imported.directory, None
      else:
        baseline, authorized = before.directory, authorization(username)
      run([str(HELPER), '--setup-system'], env={**os.environ, 'GREETER_USER': greeter_name})
      target = GREETER_STATE / 'greeter.toml'
      no_symlinks(target)
      current = tomllib.loads(target.read_text()) if target.is_file() else {}
      updated = dump_toml(merge_greeter(current))
      tomllib.loads(updated)
      if not manifest and not legacy:
        atomic_write(target, updated.encode())
        os.chown(target, greeter.pw_uid, greeter.pw_gid)
        target.chmod(0o644)
      install_ui(directory, token)
      prepare_preferences(account, greeter, directory)
      wanted = {'command': str(SESSION_LAUNCHER), 'user': greeter_name}
      if not manifest and not legacy and current_greetd.get('default_session') != wanted:
        no_symlinks(GREETD)
        GREETD.parent.mkdir(parents=True, exist_ok=True)
        current_greetd['default_session'] = {**current_greetd.get('default_session', {}), **wanted}
        atomic_write(GREETD, dump_toml(current_greetd).encode())
        GREETD.chmod(0o644)
      run(['/usr/bin/noctalia-greeter', 'passwordless-sync', 'enable', username])
      result = {'type': 'hyprlarp-greeter-system', 'version': 1, 'release': VERSION, 'user': username,
        'baseline': str(baseline), 'owned': str(directory / 'owned'), 'previous_authorization': authorized,
        'legacy_backup': manifest.get('legacy_backup') if manifest else legacy,
        'installed': True, 'pending': True, 'operation': token, 'expected': str(directory / 'expected')}
      save_system(result)
      expected = Snapshot.capture(directory / 'expected', system_targets())
      shutil.copytree(expected.directory, directory / 'owned')
      owned = Snapshot(directory / 'owned', system_targets())
      restrict_system_owned(owned, previous=manifest, before=before)
      return {'backup': str(directory), 'transaction': token, 'greeter_user': greeter_name,
        'authorization': run(['/usr/bin/noctalia-greeter', 'passwordless-sync', 'status', username]),
        'legacy_authorization_preserved': authorized is None}
    except BaseException:
      before.restore()
      raise


def operation_record(username, token):
  if not isinstance(token, str) or not re.fullmatch(r'[a-f0-9]{32}', token):
    raise ValueError('Identificador de operación inválido')
  directory = BACKUPS / token
  no_symlinks(directory)
  data = json.loads((directory / 'operation.json').read_text())
  if data.get('type') != 'hyprlarp-greeter-operation' or data.get('user') != username or data.get('token') != token:
    raise ValueError('La operación no pertenece a este usuario')
  return directory, data


def rollback_operation(username, token, *, strict=False):
  directory, data = operation_record(username, token)
  manifest = load_system(username)
  if not manifest or manifest.get('operation') != token or not manifest.get('pending'):
    raise ValueError('La operación ya no está pendiente; no se restaura sobre cambios posteriores')
  expected = Snapshot(Path(manifest['expected']), system_targets())
  names = set(system_targets()) - {'manifest'} if strict else {'greetd', 'ui', 'ui-launcher', 'session-launcher', 'polkit'}
  if not snapshot_matches(expected, names):
    raise ValueError('Se conservan cambios posteriores en el greeter; la restauración automática no puede sobrescribirlos')
  Snapshot(directory / 'before', system_targets()).restore()
  return {'status': 'rolled-back', 'transaction': token}


def system_rollback(username, token):
  identity(username)
  with locked(BACKUPS / '.lifecycle.lock'):
    return rollback_operation(username, token)


def system_commit(username, token):
  identity(username)
  with locked(BACKUPS / '.lifecycle.lock'):
    directory, data = operation_record(username, token)
    manifest = load_system(username)
    if not manifest or manifest.get('operation') != token or not manifest.get('pending'):
      raise ValueError('La operación ya no está pendiente')
    # Capture the initial sync as managed data too, after the user service finishes.
    if data['action'] == 'install':
      committed = directory / 'committed'
      owned = Snapshot.capture(committed, system_targets())
      before = Snapshot(directory / 'before', system_targets())
      old_manifest = json.loads(before.data('manifest').decode()) if before.data('manifest') else None
      restrict_system_owned(owned, previous=old_manifest if old_manifest and old_manifest.get('installed') else None, before=before)
      manifest['owned'] = str(committed)
    manifest['pending'] = False
    save_system(manifest)
    return {'status': 'committed', 'transaction': token}


def restore_greetd(baseline, owned):
  old_data = baseline.data('greetd')
  old = tomllib.loads(old_data.decode()) if old_data else {}
  current = tomllib.loads(GREETD.read_text()) if GREETD.is_file() else {}
  actual_metadata = fingerprint(GREETD) if GREETD.is_file() else None
  installed_metadata = record_hash(owned.records['greetd']['entries'].get('.'))
  previous_metadata = record_hash(baseline.records['greetd']['entries'].get('.'))
  if old_data is not None and actual_metadata == installed_metadata:
    atomic_write(GREETD, old_data)
    Snapshot.metadata(GREETD, previous_metadata)
    return {'restored': [str(GREETD)], 'preserved': []}
  command = current.get('default_session', {}).get('command', '')
  if command != str(SESSION_LAUNCHER):
    if isinstance(command, str) and str(SESSION_LAUNCHER) in command:
      raise ValueError('El comando personalizado de greetd todavía usa HyprLarp; se conserva la instalación para evitar un inicio de sesión roto')
    return {'preserved': [str(GREETD)]}
  installed_data = owned.data('greetd')
  installed = tomllib.loads(installed_data.decode()) if installed_data else {}
  previous_session = old.get('default_session', {})
  installed_session = installed.get('default_session', {})
  session = current.get('default_session', {})
  preserved = []
  for key in set(previous_session) | set(installed_session):
    if session.get(key) != installed_session.get(key):
      preserved.append(str(GREETD) + ':default_session.' + key)
    elif key in previous_session:
      session[key] = copy.deepcopy(previous_session[key])
    else:
      session.pop(key, None)
  if session:
    current['default_session'] = session
  else:
    current.pop('default_session', None)
  if old_data is None and not current:
    GREETD.unlink(missing_ok=True)
  else:
    metadata = {}
    for key in ['mode', 'uid', 'gid']:
      value = actual_metadata[key]
      if installed_metadata and previous_metadata and value == installed_metadata[key]:
        value = previous_metadata[key]
      metadata[key] = value
    atomic_write(GREETD, dump_toml(current).encode())
    Snapshot.metadata(GREETD, metadata)
  return {'restored': [str(GREETD)], 'preserved': preserved}


def system_uninstall(username):
  identity(username)
  with locked(BACKUPS / '.lifecycle.lock'):
    manifest = load_system(username)
    if manifest and manifest.get('pending'):
      rollback_operation(username, manifest['operation'], strict=True)
      manifest = load_system(username)
    no_symlinks(GREETD)
    if not manifest:
      # Adopt an old installation, retaining its earliest pre-HyprLarp backup.
      current = tomllib.loads(GREETD.read_text()) if GREETD.is_file() else {}
      if current.get('default_session', {}).get('command') != str(SESSION_LAUNCHER):
        return {'status': 'not-installed'}
      greeter = pwd.getpwnam(current['default_session'].get('user', 'greeter'))
      token, directory, before = operation(username, 'uninstall')
      imported, legacy = legacy_baseline(directory, greeter)
      owned = Snapshot.capture(directory / 'legacy-owned', system_targets())
      restrict_system_owned(owned, legacy=True)
      manifest = {'type': 'hyprlarp-greeter-system', 'version': 1, 'user': username,
        'baseline': str(imported.directory), 'owned': str(owned.directory),
        'previous_authorization': None, 'installed': True, 'legacy_backup': legacy}
    elif not manifest.get('installed'):
      return {'status': 'not-installed'}
    else:
      token, directory, before = operation(username, 'uninstall')
    try:
      baseline = Snapshot(Path(manifest['baseline']), system_targets())
      owned = Snapshot(Path(manifest['owned']), system_targets())
      restored_greetd = restore_greetd(baseline, owned)
      result = baseline.restore_owned(owned, skip={'greetd', 'polkit', 'manifest'})
      for key, values in restored_greetd.items():
        result.setdefault(key, []).extend(values)
      if manifest['previous_authorization'] is False:
        run(['/usr/bin/noctalia-greeter', 'passwordless-sync', 'disable', username])
      manifest.update(installed=False, pending=True, operation=token, expected=str(directory / 'expected'))
      save_system(manifest)
      Snapshot.capture(directory / 'expected', system_targets())
      return {'status': 'uninstalled', 'transaction': token, 'backup': str(directory),
        'legacy_authorization_preserved': manifest['previous_authorization'] is None, **result}
    except BaseException:
      before.restore()
      raise


def user_locations():
  home = Path.home()
  data = Path(os.environ.get('XDG_DATA_HOME', home / '.local/share'))
  config = Path(os.environ.get('XDG_CONFIG_HOME', home / '.config'))
  state = Path(os.environ.get('XDG_STATE_HOME', home / '.local/state')) / 'hyprlarp-greeter'
  app = data / 'hyprlarp-greeter'
  launcher = home / '.local/bin/hyprlarp-greeter'
  units = config / 'systemd/user'
  return {'app': app, 'launcher': launcher, 'service': units / (UNIT + '.service'),
    'path': units / (UNIT + '.path')}, config, state


def unit_state():
  result = {}
  for suffix in ['path', 'service']:
    unit = UNIT + '.' + suffix
    result[suffix] = {}
    for name, action in [('enabled', 'is-enabled'), ('active', 'is-active')]:
      response = subprocess.run(['systemctl', '--user', action, unit], capture_output=True, text=True, timeout=5)
      value = response.stdout.strip()
      result[suffix][name] = value in ({'enabled', 'enabled-runtime'} if name == 'enabled' else {'active', 'activating'})
      if name == 'enabled':
        result[suffix]['present'] = value not in {'', 'not-found'}
        result[suffix]['runtime'] = value == 'enabled-runtime'
  return result


def stop_units():
  current = unit_state()
  if current['path'].get('present') or current['path']['active']:
    run(['systemctl', '--user', 'disable', '--now', UNIT + '.path'])
  if current['service'].get('present') or current['service']['active']:
    run(['systemctl', '--user', 'stop', UNIT + '.service'])


def restore_units(previous):
  stop_units()
  run(['systemctl', '--user', 'daemon-reload'])
  for suffix in ['path', 'service']:
    unit = UNIT + '.' + suffix
    # service is static; only enable units that were explicitly enabled.
    if previous[suffix]['enabled']:
      run(['systemctl', '--user', 'enable', *(['--runtime'] if previous[suffix].get('runtime') else []), unit])
    if previous[suffix]['active']:
      run(['systemctl', '--user', 'start', unit])


def ensure_privileges():
  result = subprocess.run(['sudo', '-n', 'true'], capture_output=True, text=True, timeout=5)
  if result.returncode:
    raise RuntimeError('Se requieren permisos de administrador antes de cambiar el greeter. '
      'Ejecuta en tu terminal: sudo -v; después repite la operación del greeter.')


def privileged(flag, username, token=None, *, script=None):
  # A missing sudo credential is a concrete error, never an authentication dialog.
  command = ['/usr/bin/python3', str(script or Path(__file__).resolve()), flag, username]
  if token:
    command += ['--transaction', token]
  result = subprocess.run(['sudo', '-n', *command], capture_output=True, text=True, timeout=90)
  if result.returncode:
    raise RuntimeError((result.stderr or result.stdout).strip()[-1500:] +
      '\nSe requieren permisos de administrador. Ejecuta en tu terminal: sudo -v; después repite la operación del greeter.')
  return json.loads(result.stdout)


def load_user(targets, state):
  path = targets['app'] / 'installation.json'
  if not path.is_file():
    return None
  no_symlinks(path)
  data = json.loads(path.read_text())
  if data.get('type') == 'hyprlarp-greeter-user' and data.get('version') == 1:
    for key in ['baseline', 'owned']:
      directory = Path(data[key])
      if not directory.is_relative_to(state) or '..' in directory.parts:
        raise ValueError('Ruta de respaldo de usuario inválida')
      no_symlinks(directory)
    return data
  if isinstance(data, dict) and isinstance(data.get('backup'), str):
    return {'legacy': True, 'setup': data}
  raise ValueError('El manifiesto de instalación del greeter es inválido')


def missing_baseline(directory, targets):
  missing = {name: directory / ('missing-' + name) for name in targets}
  return original_snapshot(directory / 'baseline', targets, missing)


def restrict_owned(snapshot):
  # Legacy directories may contain unrelated files: they are never owned by us.
  allowed = set(SYNC_FILES) | {'installation.json'}
  record = snapshot.records['app']
  keep_entries(record, allowed)
  document = json.loads((snapshot.directory / 'snapshot.json').read_text())
  document['targets'] = snapshot.records
  atomic_write(snapshot.directory / 'snapshot.json', (json.dumps(document, indent=2) + '\n').encode())


def stage_user(directory, targets):
  stage = directory / 'stage'
  if targets['app'].is_dir():
    no_symlinks(targets['app'])
    for entry in targets['app'].rglob('*'):
      no_symlinks(entry)
    shutil.copytree(targets['app'], stage, symlinks=False)
  else:
    stage.mkdir()
  for name in SYNC_FILES:
    source = ROOT / name
    no_symlinks(source)
    if not source.is_file():
      raise ValueError('Falta un archivo de la integración del greeter: ' + name)
    destination = stage / name
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
  return stage


def install_user(*, dry_run=False):
  if os.geteuid() == 0:
    raise ValueError('Ejecuta el instalador como tu usuario, sin sudo')
  targets, config, state = user_locations()
  contents = user_units(targets['app'], config)
  for path in targets.values():
    no_symlinks(path)
    print(path)
  if not (config / 'hyprlarp/settings.json').is_file():
    raise ValueError('No se encontraron los ajustes de HyprLarp')
  if not HELPER.is_file():
    raise ValueError('Instala noctalia-greeter con su helper antes de continuar')
  if dry_run:
    print('Interfaz propia: ' + str(GREETER_UI))
    print('Sistema: instalación transaccional, respaldo original conservado y autorización restringida')
    return
  ensure_privileges()
  with locked(state / 'install.lock'):
    installed = load_user(targets, state)
    if installed and not installed.get('legacy'):
      reject_user_edits(installed, targets)
    directory = state / 'installations' / uuid.uuid4().hex
    before = Snapshot.capture(directory / 'before', targets)
    stage = stage_user(directory, targets)
    previous = unit_state()
    baseline = Path(installed['baseline']) if installed and not installed.get('legacy') else (
      missing_baseline(directory, targets).directory if installed else before.directory)
    original_units = installed['previous_units'] if installed and not installed.get('legacy') else (
      {'path': {'enabled': False, 'active': False}, 'service': {'enabled': False, 'active': False}} if installed else previous)
    username = pwd.getpwuid(os.getuid()).pw_name
    setup = None
    committed = False
    try:
      stop_units()
      setup = privileged('--system', username)
      document = {'type': 'hyprlarp-greeter-user', 'version': 1, 'release': VERSION, 'user': username,
        'baseline': str(baseline), 'owned': str(directory / 'owned'), 'previous_units': original_units,
        'setup': setup}
      atomic_write(stage / 'installation.json', (json.dumps(document, indent=2) + '\n').encode())
      Snapshot.remove(targets['app'])
      targets['app'].parent.mkdir(parents=True, exist_ok=True)
      stage.rename(targets['app'])
      targets['launcher'].parent.mkdir(parents=True, exist_ok=True)
      atomic_write(targets['launcher'], ('#!/bin/sh\nexec /usr/bin/python3 ' + shlex.quote(str(targets['app'] / 'backend/greeter.py')) + ' "$@"\n').encode())
      targets['launcher'].chmod(0o755)
      for role, name in [('service', UNIT + '.service'), ('path', UNIT + '.path')]:
        targets[role].parent.mkdir(parents=True, exist_ok=True)
        atomic_write(targets[role], contents[name].encode())
      owned = Snapshot.capture(directory / 'owned', targets)
      restrict_owned(owned)
      run(['systemctl', '--user', 'daemon-reload'])
      run(['systemctl', '--user', 'enable', '--now', UNIT + '.path'])
      run(['systemctl', '--user', 'start', UNIT + '.service'])
      status = run([str(targets['launcher']), 'status'])
      privileged('--system-commit', username, setup['transaction'])
      committed = True
      result = {'status': 'installed', **setup}
      print(json.dumps(result, ensure_ascii=False, indent=2))
      print(status)
      return result
    except BaseException as error:
      if committed:
        raise
      failures = []
      try:
        stop_units()
      except BaseException as failure:
        failures.append(str(failure))
      try:
        before.restore()
        restore_units(previous)
      except BaseException as failure:
        failures.append(str(failure))
      if setup:
        try:
          privileged('--system-rollback', username, setup['transaction'])
        except BaseException as failure:
          failures.append(str(failure))
      if failures:
        raise RuntimeError(str(error) + '\nRestauración incompleta: ' + '; '.join(failures)) from error
      raise


def uninstall_user(*, dry_run=False):
  if os.geteuid() == 0:
    raise ValueError('Ejecuta la desinstalación como tu usuario, sin sudo')
  targets, config, state = user_locations()
  installed = load_user(targets, state)
  if not installed:
    result = {'status': 'not-installed'}
    print(json.dumps(result))
    return result
  if dry_run:
    result = {'status': 'dry-run', 'action': 'uninstall', 'targets': list(map(str, targets.values())),
      'system': 'Restaurar greetd y los archivos propios sin reiniciar el servicio; conservar archivos modificados'}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result
  ensure_privileges()
  with locked(state / 'install.lock'):
    directory = state / 'installations' / uuid.uuid4().hex
    before = Snapshot.capture(directory / 'before', targets)
    previous = unit_state()
    username = pwd.getpwuid(os.getuid()).pw_name
    if installed.get('legacy'):
      baseline = missing_baseline(directory, targets)
      owned = Snapshot.capture(directory / 'legacy-owned', targets)
      restrict_owned(owned)
      original_units = {'path': {'enabled': False, 'active': False}, 'service': {'enabled': False, 'active': False}}
    else:
      baseline = Snapshot(Path(installed['baseline']), targets)
      owned = Snapshot(Path(installed['owned']), targets)
      original_units = installed['previous_units']
    # This private copy survives removal of the standalone appearance bridge.
    with tempfile.TemporaryDirectory(prefix='hyprlarp-greeter-control-') as temporary:
      control = Path(temporary)
      for name in SYNC_FILES:
        target = control / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, target)
      script = control / 'tools/install_greeter.py'
      setup = None
      committed = False
      try:
        stop_units()
        setup = privileged('--system-uninstall', username, script=script)
        result = baseline.restore_owned(owned)
        restore_units(original_units)
        if setup.get('transaction'):
          privileged('--system-commit', username, setup['transaction'], script=script)
        committed = True
        report = {'status': 'uninstalled', 'system': setup, **result}
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return report
      except BaseException as error:
        if committed:
          raise
        failures = []
        try:
          before.restore()
          restore_units(previous)
        except BaseException as failure:
          failures.append(str(failure))
        if setup and setup.get('transaction'):
          try:
            privileged('--system-rollback', username, setup['transaction'], script=script)
          except BaseException as failure:
            failures.append(str(failure))
        if failures:
          raise RuntimeError(str(error) + '\nRestauración incompleta: ' + '; '.join(failures)) from error
        raise


def main():
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument('--version', action='version', version='HyprLarp Greeter ' + VERSION)
  parser.add_argument('--dry-run', action='store_true')
  parser.add_argument('--uninstall', action='store_true', help='Restaurar el greeter anterior y retirar la integración opcional')
  modes = parser.add_mutually_exclusive_group()
  modes.add_argument('--system', metavar='USER', help=argparse.SUPPRESS)
  modes.add_argument('--system-uninstall', metavar='USER', help=argparse.SUPPRESS)
  modes.add_argument('--system-rollback', metavar='USER', help=argparse.SUPPRESS)
  modes.add_argument('--system-commit', metavar='USER', help=argparse.SUPPRESS)
  parser.add_argument('--transaction', help=argparse.SUPPRESS)
  args = parser.parse_args()
  try:
    if args.dry_run and any([args.system, args.system_uninstall, args.system_rollback, args.system_commit]):
      raise ValueError('La vista previa se ejecuta como usuario, sin acciones privilegiadas')
    if args.system:
      print(json.dumps(system_setup(args.system)))
    elif args.system_uninstall:
      print(json.dumps(system_uninstall(args.system_uninstall)))
    elif args.system_rollback:
      print(json.dumps(system_rollback(args.system_rollback, args.transaction)))
    elif args.system_commit:
      print(json.dumps(system_commit(args.system_commit, args.transaction)))
    elif args.uninstall:
      uninstall_user(dry_run=args.dry_run)
    else:
      install_user(dry_run=args.dry_run)
  except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
    parser.exit(1, str(error) + '\n')


if __name__ == '__main__':
  main()
