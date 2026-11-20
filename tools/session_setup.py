"""Transactional per-user integration for an immutable system package."""

from contextlib import contextmanager
import base64
import copy
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import signal
import stat
import subprocess
import tempfile
import uuid

from backend import recovery
from backend.persistence import atomic_bytes
from backend.safety import idle_processes, read_json, read_regular
from backend.service import Store, lua_string
from backend.version import read_version
from .deployment import Locations, MARKER, absolute, load_manifest, no_symlinks
from .integration import contents

PACKAGE_MARKER = '.hyprlarp-package.json'
SESSION_MARKER = '.hyprlarp-session.json'
ROLES = frozenset({'settings', 'bindings', 'gaps', 'idle', 'prelude', 'session', 'service', 'launcher'})
ACTIVE = frozenset({'settings', 'bindings', 'gaps', 'idle'})
FILE_LIMIT = 2 * 1024 * 1024
TOTAL_LIMIT = 8 * 1024 * 1024
MARKER_LIMIT = 12 * 1024 * 1024


def checksum(data):
  return hashlib.sha256(data).hexdigest()


def valid_hash(value):
  return isinstance(value, str) and len(value) == 64 and all(char in '0123456789abcdef' for char in value)


def package_metadata(root):
  """Validate package metadata without writing files or requiring a session."""
  root = absolute(root)
  no_symlinks(root)
  marker = root / PACKAGE_MARKER
  no_symlinks(marker)
  if not marker.exists():
    return None
  document = read_json(marker, limit=4 * 1024 * 1024)
  if (not isinstance(document, dict) or document.get('type') != 'hyprlarp-package'
      or type(document.get('version')) is not int or document['version'] != 1
      or not isinstance(document.get('files'), dict) or not 1 <= len(document['files']) <= 4096):
    raise ValueError('El manifiesto del paquete de HyprLarp no es válido')
  for name, value in document['files'].items():
    if not isinstance(name, str) or not name or '\\' in name or any(ord(char) < 32 for char in name):
      raise ValueError('Ruta no válida en el manifiesto del paquete')
    path = Path(name)
    if not path.parts or path.is_absolute() or '..' in path.parts or path.as_posix() != name or not valid_hash(value):
      raise ValueError('Ruta o hash no válido en el manifiesto del paquete')
  no_symlinks(root / 'VERSION')
  if (document.get('release') != read_version(root)
      or document['files'].get('VERSION') != checksum(read_regular(root / 'VERSION', 128))):
    raise ValueError('La versión del paquete no coincide con su manifiesto')
  return document


def _targets(locations):
  managed = locations.managed()
  return {role: managed[role] for role in ROLES - {'settings'}} | {'settings': locations.config / 'settings.json'}


def _record(path):
  """Take bounded data, without following links or opening a special file."""
  no_symlinks(path)
  if not path.exists():
    return None
  info = path.stat()
  if not stat.S_ISREG(info.st_mode) or info.st_size > FILE_LIMIT:
    raise ValueError('El destino debe ser un archivo regular de hasta 2 MiB: ' + str(path))
  return {'data': base64.b64encode(read_regular(path, FILE_LIMIT)).decode('ascii'), 'mode': stat.S_IMODE(info.st_mode)}


def _data(record):
  return base64.b64decode(record['data'], validate=True)


def _matches(record, owned, mode):
  return record is not None and checksum(_data(record)) == owned and record['mode'] == mode


def _load(locations, root):
  marker = locations.config / SESSION_MARKER
  no_symlinks(marker)
  if not marker.exists():
    return None
  document = read_json(marker, limit=MARKER_LIMIT)
  allowed = {'type', 'version', 'root', 'release', 'prefix', 'first_run', 'owned', 'modes', 'baseline'}
  if (not isinstance(document, dict) or set(document) != allowed
      or document.get('type') != 'hyprlarp-session' or type(document.get('version')) is not int
      or document['version'] != 1 or document.get('root') != str(root)
      or document.get('prefix') != locations.prefix or type(document.get('first_run')) is not bool
      or not isinstance(document.get('release'), str) or not 1 <= len(document['release']) <= 128):
    raise ValueError('El estado de integración del usuario es inválido o pertenece a otra versión/ruta; se ha conservado')
  owned, modes, baseline = (document.get(key) for key in ('owned', 'modes', 'baseline'))
  if (not all(isinstance(value, dict) for value in (owned, modes, baseline))
      or set(owned) - ROLES or set(modes) != set(owned) or set(baseline) != set(owned)
      or any(not valid_hash(value) for value in owned.values())
      or any(type(value) is not int or not 0 <= value <= 0o7777 for value in modes.values())):
    raise ValueError('Propiedad de archivos de integración inválida; se ha conservado')
  total = 0
  for record in baseline.values():
    if record is None:
      continue
    if (not isinstance(record, dict) or set(record) != {'data', 'mode'}
        or type(record['mode']) is not int or not 0 <= record['mode'] <= 0o7777
        or not isinstance(record['data'], str) or len(record['data']) > 4 * ((FILE_LIMIT + 2) // 3)):
      raise ValueError('Copia de integración inválida; se ha conservado')
    try:
      data = _data(record)
    except (ValueError, UnicodeError) as error:
      raise ValueError('Copia de integración inválida; se ha conservado') from error
    total += len(data)
    if len(data) > FILE_LIMIT or total > TOTAL_LIMIT:
      raise ValueError('La copia de integración supera su límite; se ha conservado')
  return document


def _locations(root, prefix):
  root = absolute(root)
  locations = Locations.create(prefix)
  locations.validate()
  for path in _targets(locations).values():
    no_symlinks(path)
    if root == path or root.is_relative_to(path) or path.is_relative_to(root):
      raise ValueError('La integración del usuario no puede escribir dentro del paquete')
  no_symlinks(locations.config / SESSION_MARKER)
  return root, locations


def ready(root, prefix=None):
  try:
    root, locations = _locations(root, prefix)
    metadata = package_metadata(root)
    document = _load(locations, root)
    return bool(metadata and document and document['release'] == metadata['release']
      and all(path.is_file() for role, path in _targets(locations).items() if role != 'launcher'))
  except (OSError, ValueError, TypeError):
    return False


@contextmanager
def _locked(locations):
  no_symlinks(locations.config)
  locations.config.mkdir(parents=True, exist_ok=True, mode=0o700)
  if locations.config.stat().st_uid != os.getuid():
    raise ValueError('La configuración pertenece a otro usuario')
  locations.config.chmod(0o700)
  path = locations.config / '.hyprlarp-session.lock'
  no_symlinks(path)
  descriptor = os.open(path, os.O_CREAT | os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
  try:
    if not stat.S_ISREG(os.fstat(descriptor).st_mode):
      raise ValueError('El bloqueo debe ser un archivo regular')
    try:
      fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
      raise RuntimeError('Ya hay otra integración de HyprLarp en curso') from None
    yield
  finally:
    os.close(descriptor)


def _legacy(locations):
  marker = locations.app / MARKER
  no_symlinks(marker)
  if not marker.exists():
    return None
  try:
    return load_manifest(locations)
  except (OSError, ValueError):
    print('Conservar instalación local no reconocida: ' + str(locations.app))
    return None


def _settings(record):
  with tempfile.TemporaryDirectory(prefix='hyprlarp-session-settings-') as temporary:
    folder = Path(temporary)
    if record is not None:
      (folder / 'settings.json').write_bytes(_data(record))
    store = Store(folder)
    if store.warning:
      print(store.warning)
    return store.settings


def _plan(root, locations, metadata):
  targets = _targets(locations)
  current = {role: _record(path) for role, path in targets.items()}
  previous = _load(locations, root)
  legacy = _legacy(locations)
  executable = root.parents[1] / 'bin/hyprlarp'
  generated = contents(root, locations.config, executable, _settings(current['settings']))
  generated['launcher'] = ('#!/bin/sh\nexec ' + shlex.quote(str(executable)) + ' "$@"\n').encode()
  owned = dict(previous['owned']) if previous else {}
  modes = dict(previous['modes']) if previous else {}
  baseline = copy.deepcopy(previous['baseline']) if previous else {}
  changes = {}
  for role, record in current.items():
    old_hash = owned.get(role)
    old_mode = modes.get(role)
    legacy_hash = (legacy or {}).get('managed', {}).get(role)
    ours = old_hash is not None and _matches(record, old_hash, old_mode)
    recognized = previous is None and record is not None and legacy_hash is not None and checksum(_data(record)) == legacy_hash
    if role == 'launcher':
      # The global command already exists. Only retire our own legacy wrapper
      # when it would otherwise shadow that command in the user's PATH.
      if record is None or not (ours or recognized):
        if record is not None:
          print('Conservar lanzador local; usa ' + str(executable) + ' explícitamente: ' + str(targets[role]))
        continue
    elif record is not None and (role in ACTIVE or not (ours or recognized)):
      print('Conservar configuración activa: ' + str(targets[role]))
      continue
    if role not in baseline:
      baseline[role] = record
    mode = record['mode'] if record is not None else 0o600
    if role == 'launcher' and record is None:
      mode = 0o755
    data = generated[role]
    if record is None or _data(record) != data:
      changes[role] = (data, mode)
    owned[role], modes[role] = checksum(data), mode
  first_run = previous['first_run'] if previous else (legacy.get('first_run', False) if legacy else current['settings'] is None)
  document = {'type': 'hyprlarp-session', 'version': 1, 'root': str(root), 'release': metadata['release'],
    'prefix': locations.prefix, 'first_run': bool(first_run), 'owned': owned, 'modes': modes, 'baseline': baseline}
  return targets, current, document, changes, legacy


def _marker_change(locations, targets, current, changes, document):
  marker = locations.config / SESSION_MARKER
  targets['_marker'], current['_marker'] = marker, _record_marker(marker)
  if document is not None and sum(len(_data(record)) for record in document['baseline'].values() if record) > TOTAL_LIMIT:
    raise ValueError('La copia de integración supera su límite de tamaño')
  data = None if document is None else (json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + '\n').encode()
  if data is not None and len(data) > MARKER_LIMIT:
    raise ValueError('El estado de integración supera su límite de tamaño')
  if data is None or current['_marker'] is None or current['_marker']['data'] != data:
    changes['_marker'] = (data, 0o600)


def _record_marker(path):
  no_symlinks(path)
  if not path.exists():
    return None
  info = path.stat()
  if not stat.S_ISREG(info.st_mode):
    raise ValueError('El estado debe ser un archivo regular')
  return {'data': read_regular(path, MARKER_LIMIT), 'mode': stat.S_IMODE(info.st_mode)}


def _transaction(targets, current, changes, activate=None):
  """Keep same-filesystem originals until writes and activation both succeed."""
  backups, touched = {}, []
  try:
    for role in changes:
      actual = _record_marker(targets[role]) if role == '_marker' else _record(targets[role])
      if actual != current[role]:
        raise ValueError('El archivo cambió durante la preparación: ' + str(targets[role]))
    for role, (data, mode) in changes.items():
      target = targets[role]
      no_symlinks(target)
      target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
      if target.exists():
        backup = target.with_name('.' + target.name + '.hyprlarp-' + uuid.uuid4().hex + '.bak')
        target.rename(backup)
        backups[target] = backup
      touched.append(target)
      if data is not None:
        atomic_bytes(target, data)
        target.chmod(mode)
    if activate:
      activate()
  except BaseException:
    for target in reversed(touched):
      no_symlinks(target)
      target.unlink(missing_ok=True)
    for target, backup in backups.items():
      backup.rename(target)
    raise
  else:
    for backup in backups.values():
      try:
        backup.unlink()
      except OSError:
        print('Respaldo retenido: ' + str(backup))


def _active_root(root, locations, binary, legacy=None):
  if locations.prefix or not binary:
    return None
  candidates = [root] + ([locations.app] if legacy else [])
  own_unit = False
  # An automatic setup called by ExecStart must not stop its own supervisor.
  if os.environ.get('HYPRLARP_SUPERVISOR') == '1':
    result = recovery.run(['systemctl', '--user', 'show', recovery.UNIT, '-p', 'MainPID', '--value'], check=False)
    own_unit = result.returncode == 0 and result.stdout.strip() == str(os.getpid())
  for candidate in candidates:
    renderers = bool(recovery.running_pids(candidate) or recovery.running_pids(candidate, 'recovery.qml'))
    if own_unit:
      if renderers:
        raise RuntimeError('Ejecuta hyprlarp setup desde tu sesión antes de reiniciar el servicio; se conserva la instancia anterior')
      continue
    if renderers or recovery.service_running(candidate, locations.managed()['service']):
      return candidate
  return None


def _restore_runtime(active, locations, binary, executable):
  recovery.run(['systemctl', '--user', 'daemon-reload'], check=False)
  unit = locations.managed()['service']
  if unit.is_file():
    previous = read_regular(unit, FILE_LIMIT).decode()
    if previous == recovery.render_unit(executable, active):
      recovery.start(active, executable, binary, destination=unit)
    elif previous.startswith('# HyprLarp managed: ' + str(active) + '\n'):
      # A package may have changed its unit template. Its restored predecessor
      # is still our verified original; don't replace it with the failed one
      # merely to satisfy the new version's exact-template startup check.
      recovery.run(['systemctl', '--user', 'reset-failed', recovery.UNIT], check=False)
      recovery.run(['systemctl', '--user', 'start', recovery.UNIT], timeout=65)
      recovery.wait_ready(active, binary)
    else:
      raise RuntimeError('Se restauró la configuración, pero el servicio anterior no se reconoce; se ha conservado sin iniciarlo')
  else:
    subprocess.Popen([str(active / 'bin/hyprlarp'), 'run'], stdout=subprocess.DEVNULL,
      stderr=subprocess.DEVNULL, start_new_session=True)
    recovery.wait_ready(active, binary)


def _setup(root, locations, metadata, *, dry_run=False):
  targets, current, document, changes, legacy = _plan(root, locations, metadata)
  _marker_change(locations, targets, current, changes, document)
  for role in changes:
    print('Preparar: ' + str(targets[role]))
  if dry_run:
    return document
  binary = shutil.which('quickshell') or shutil.which('qs')
  active = _active_root(root, locations, binary, legacy)
  executable = root.parents[1] / 'bin/hyprlarp'
  previous_signature = os.environ.get('HYPRLAND_INSTANCE_SIGNATURE')

  def activate():
    try:
      recovery.start(root, executable, binary, destination=targets['service'])
    except BaseException:
      recovery.stop(root, binary, destination=targets['service'])
      raise

  try:
    if active:
      final_service = changes['service'][0] if 'service' in changes else (_data(current['service']) if current['service'] else None)
      if final_service != recovery.render_unit(executable, root).encode():
        raise RuntimeError('El servicio fue personalizado y se ha conservado; detén esa instancia y revisa su integración antes de migrar')
      environment = recovery.current_session()
      os.environ['HYPRLAND_INSTANCE_SIGNATURE'] = environment['HYPRLAND_INSTANCE_SIGNATURE']
      recovery.stop(active, binary, destination=targets['service'])
    try:
      _transaction(targets, current, changes, activate if active else None)
    except BaseException:
      if active:
        previous_executable = locations.executable if active == locations.app else executable
        _restore_runtime(active, locations, binary, previous_executable)
      raise
  finally:
    if previous_signature is None:
      os.environ.pop('HYPRLAND_INSTANCE_SIGNATURE', None)
    else:
      os.environ['HYPRLAND_INSTANCE_SIGNATURE'] = previous_signature
  print('Integración preparada. Los archivos del paquete y la configuración principal de Hyprland se conservan.')
  return document


def setup(root, prefix=None, dry_run=False):
  root, locations = _locations(root, prefix)
  metadata = package_metadata(root)
  if metadata is None:
    raise ValueError('No se encontró un paquete global de HyprLarp válido')
  if dry_run:
    return _setup(root, locations, metadata, dry_run=True)
  with _locked(locations):
    return _setup(root, locations, metadata)


def _detach_runtime(root, locations, *, stop_idle=False):
  if locations.prefix:
    return
  try:
    environment = recovery.current_session()
    owned = lua_string(str(root / 'config/bindings-runtime.lua'))
    expression = 'if HyprLarpBinds and HyprLarpBinds.runtimePath == ' + owned + ' then HyprLarpBinds.stop() end'
    recovery.run(['hyprctl', '--instance', environment['HYPRLAND_INSTANCE_SIGNATURE'], 'eval', expression], check=False)
  except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError):
    pass
  if stop_idle:
    expected = str(locations.config / 'hypridle.conf')
    for pid, arguments in idle_processes(expected):
      try:
        descriptor = os.pidfd_open(pid)
        try:
          if (Path('/proc') / str(pid) / 'cmdline').read_bytes().split(b'\0') == arguments:
            signal.pidfd_send_signal(descriptor, signal.SIGTERM)
        finally:
          os.close(descriptor)
      except (OSError, ValueError):
        continue


def _teardown(root, locations, *, dry_run=False, stop=True, purge=False):
  document = _load(locations, root)
  if document is None:
    if purge:
      raise ValueError('Sin un estado de integración válido no se borran ajustes; se han conservado')
    print('No hay integración de usuario de este paquete. Los ajustes se conservan.')
    return
  targets = _targets(locations)
  current = {role: _record(path) for role, path in targets.items()}
  stop_idle = 'idle' in document['owned'] and _matches(current['idle'], document['owned']['idle'], document['modes']['idle'])
  changes = {}
  for role, owned in document['owned'].items():
    if role == 'settings':
      continue
    if not _matches(current[role], owned, document['modes'][role]):
      print('Conservar archivo modificado o retirado: ' + str(targets[role]))
      continue
    original = document['baseline'][role]
    data, mode = (_data(original), original['mode']) if original else (None, 0o600)
    if current[role] != original:
      changes[role] = (data, mode)
      print(('Restaurar: ' if original else 'Quitar: ') + str(targets[role]))
  _marker_change(locations, targets, current, changes, None)
  print(('Quitar carpeta de ajustes completa: ' if purge else 'Conservar ajustes e historial: ') + str(locations.config))
  if dry_run:
    return
  binary = shutil.which('quickshell') or shutil.which('qs')
  active = _active_root(root, locations, binary) if stop else None
  if active:
    recovery.stop(active, binary, destination=targets['service'])
  try:
    _transaction(targets, current, changes)
  except BaseException:
    if active:
      _restore_runtime(active, locations, binary, root.parents[1] / 'bin/hyprlarp')
    raise
  if stop and not locations.prefix:
    _detach_runtime(root, locations, stop_idle=stop_idle)
    recovery.run(['systemctl', '--user', 'daemon-reload'], check=False)
  if purge:
    no_symlinks(locations.config)
    shutil.rmtree(locations.config)
  print('Integración retirada. El paquete y la instalación local anterior se conservan.')


def teardown(root, prefix=None, dry_run=False, stop=True, purge=False):
  root, locations = _locations(root, prefix)
  if package_metadata(root) is None:
    raise ValueError('No se encontró un paquete global de HyprLarp válido')
  # A missing state is a read-only no-op, including when its folder is absent.
  if dry_run or not (locations.config / SESSION_MARKER).exists():
    return _teardown(root, locations, dry_run=dry_run, stop=stop, purge=purge)
  with _locked(locations):
    return _teardown(root, locations, stop=stop, purge=purge)
