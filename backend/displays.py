"""Native monitor layouts with an independent, short-lived revert guardian."""

import copy
from contextlib import contextmanager
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import selectors
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time

if __package__:
  from .greeter import atomic_write
  from .safety import private_directory, read_json
  from .shortcuts import lua_value
else:
  sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
  from backend.greeter import atomic_write
  from backend.safety import private_directory, read_json
  from backend.shortcuts import lua_value

NAME = re.compile(r'[A-Za-z0-9_.:-]{1,128}')
MODE = re.compile(r'(\d{2,5})x(\d{2,5})@([0-9]+(?:\.[0-9]+)?)(?:Hz)?')
PLAN_KEYS = {'name', 'enabled', 'mode', 'scale', 'transform', 'x', 'y', 'mirror'}
CONFIRM_SECONDS = 20


@contextmanager
def transaction_lock(directory):
  descriptor = os.open(directory / 'test.lock', os.O_CREAT | os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600)
  try:
    fcntl.flock(descriptor, fcntl.LOCK_EX)
    yield
  finally:
    os.close(descriptor)


def native(args):
  result = subprocess.run(['hyprctl', *args], capture_output=True, text=True, timeout=8)
  if result.returncode or result.stdout.lstrip().startswith(('error:', 'Error', 'ERR')):
    raise RuntimeError((result.stderr or result.stdout).strip()[:500] or 'Hyprland no respondió')
  return result.stdout


def mode_parts(value):
  match = MODE.fullmatch(value) if isinstance(value, str) else None
  if not match:
    raise ValueError('Modo de pantalla inválido')
  width, height, refresh = int(match[1]), int(match[2]), float(match[3])
  if not (64 <= width <= 16384 and 64 <= height <= 16384 and 1 <= refresh <= 1000):
    raise ValueError('Modo de pantalla fuera del rango admitido')
  return width, height, refresh


def canonical_mode(value):
  width, height, refresh = mode_parts(value)
  return f'{width}x{height}@{refresh:g}'


def normalize(raw):
  if not isinstance(raw, list) or len(raw) > 32:
    raise ValueError('Hyprland devolvió una lista de pantallas inválida')
  names = {entry.get('id'): entry.get('name') for entry in raw if isinstance(entry, dict)}
  result = []
  for entry in raw:
    if not isinstance(entry, dict) or not isinstance(entry.get('name'), str) or not NAME.fullmatch(entry['name']):
      continue
    if entry['name'] == 'FALLBACK':
      continue
    modes = []
    for value in entry.get('availableModes', [])[:256]:
      try:
        mode = canonical_mode(value)
        if mode not in modes:
          modes.append(mode)
      except (ValueError, TypeError):
        continue
    width, height = entry.get('width', 0), entry.get('height', 0)
    refresh = entry.get('refreshRate', 60)
    try:
      current = canonical_mode(f'{width}x{height}@{float(refresh):g}')
      if current not in modes:
        modes.append(current)
    except (ValueError, TypeError):
      current = modes[0] if modes else 'preferred'
    mirror = entry.get('mirrorOf', '')
    if isinstance(mirror, str) and mirror.isdecimal():
      mirror = int(mirror)
    mirror = names.get(mirror, '') if isinstance(mirror, int) else mirror
    if mirror in {'none', '-1'} or mirror not in names.values():
      mirror = ''
    name = entry['name']
    result.append({'name': name, 'description': str(entry.get('description', name))[:256],
      'identity': '|'.join(str(entry.get(key, ''))[:128] for key in ('name', 'make', 'model', 'serial')),
      'internal': name.startswith(('eDP', 'LVDS', 'DSI')), 'enabled': not bool(entry.get('disabled')),
      'mode': current, 'modes': modes, 'width': width, 'height': height,
      'refreshRate': refresh, 'scale': entry.get('scale', 1) or 1,
      'transform': entry.get('transform', 0), 'x': entry.get('x', 0), 'y': entry.get('y', 0),
      'mirror': mirror, 'focused': bool(entry.get('focused'))})
  return result


def query():
  return normalize(json.loads(native(['-j', 'monitors', 'all'])))


def plan_for(outputs):
  return [{key: copy.deepcopy(output[key]) for key in PLAN_KEYS} for output in outputs]


def topology(outputs):
  return hashlib.sha256(json.dumps(sorted(output['identity'] for output in outputs)).encode()).hexdigest()


def logical_size(entry, outputs):
  source = next(output for output in outputs if output['name'] == entry['name'])
  mode = source['modes'][0] if entry['mode'] == 'preferred' and source['modes'] else entry['mode']
  width, height, _ = mode_parts(mode)
  if entry['transform'] in {1, 3, 5, 7}:
    width, height = height, width
  return width / entry['scale'], height / entry['scale']


def validate(plan, outputs):
  if not isinstance(plan, list) or not 1 <= len(plan) <= 32:
    raise ValueError('Selecciona al menos una pantalla')
  by_name = {output['name']: output for output in outputs}
  if len(plan) != len(by_name) or {entry.get('name') for entry in plan if isinstance(entry, dict)} != set(by_name):
    raise ValueError('Las pantallas conectadas cambiaron. Actualiza y vuelve a probar')
  result = []
  for value in plan:
    if not isinstance(value, dict) or set(value) != PLAN_KEYS:
      raise ValueError('Configuración de pantalla inválida')
    entry = copy.deepcopy(value)
    source = by_name[entry['name']]
    if not isinstance(entry['enabled'], bool):
      raise ValueError('Estado de pantalla inválido')
    if entry['mode'] != 'preferred':
      entry['mode'] = canonical_mode(entry['mode'])
      width, height, refresh = mode_parts(entry['mode'])
      if not any(width == w and height == h and abs(refresh - r) < .1 for w, h, r in map(mode_parts, source['modes'])):
        raise ValueError('La pantalla no anuncia la resolución o frecuencia elegida')
    scale = entry['scale']
    if isinstance(scale, bool) or not isinstance(scale, (int, float)) or not math.isfinite(scale) or not .5 <= scale <= 4:
      raise ValueError('La escala debe estar entre 50 % y 400 %')
    if isinstance(entry['transform'], bool) or not isinstance(entry['transform'], int) or entry['transform'] not in range(8):
      raise ValueError('Orientación de pantalla inválida')
    for axis in ('x', 'y'):
      if isinstance(entry[axis], bool) or not isinstance(entry[axis], int) or not -32768 <= entry[axis] <= 32768:
        raise ValueError('La posición debe usar números enteros entre -32768 y 32768')
    if not isinstance(entry['mirror'], str) or (entry['mirror'] and (entry['mirror'] not in by_name or entry['mirror'] == entry['name'])):
      raise ValueError('Elige otra pantalla como origen de la duplicación')
    if entry['enabled']:
      try:
        size = logical_size(entry, outputs)
        if any(abs(dimension - round(dimension)) > .02 for dimension in size):
          raise ValueError('Esta escala no encaja con la resolución. Prueba otra escala o resolución')
      except ValueError:
        if source['modes']:
          raise
    result.append(entry)
  by_name = {entry['name']: entry for entry in result}
  if not any(entry['enabled'] and not entry['mirror'] for entry in result):
    raise ValueError('Debe quedar al menos una pantalla activa sin duplicación')
  for entry in result:
    if entry['enabled'] and entry['mirror']:
      target = by_name[entry['mirror']]
      if not target['enabled'] or target['mirror']:
        raise ValueError('El origen de una duplicación debe estar activo y no duplicar otra pantalla')
  roots = [entry for entry in result if entry['enabled'] and not entry['mirror']]
  for index, left in enumerate(roots):
    lw, lh = logical_size(left, outputs)
    for right in roots[index + 1:]:
      rw, rh = logical_size(right, outputs)
      if min(left['x'] + lw, right['x'] + rw) - max(left['x'], right['x']) > 1 and min(left['y'] + lh, right['y'] + rh) - max(left['y'], right['y']) > 1:
        raise ValueError('Las pantallas extendidas se superponen. Sepáralas o selecciona Duplicar')
  return result


def preset(mode, outputs, primary=None, secondary=None):
  if mode not in {'internal-only', 'duplicate', 'extend', 'external-only'}:
    raise ValueError('Modo de proyección desconocido')
  if not outputs:
    raise ValueError('No hay pantallas conectadas')
  primary = next((output for output in outputs if output['name'] == primary), None) or next((output for output in outputs if output['internal']), outputs[0])
  external = [output for output in outputs if output['name'] != primary['name']]
  secondary = next((output for output in external if output['name'] == secondary), None) or (external[0] if external else None)
  if mode != 'internal-only' and secondary is None:
    raise ValueError('Conecta un proyector u otra pantalla para usar este modo')
  result = plan_for(outputs)
  offset = 0
  ordered = sorted(result, key=lambda entry: entry['name'] != primary['name'])
  for entry in ordered:
    entry.update(enabled=True, mirror='', x=0, y=0)
    if mode == 'internal-only':
      entry['enabled'] = entry['name'] == primary['name']
    elif mode == 'external-only':
      entry['enabled'] = entry['name'] == secondary['name']
    elif mode == 'duplicate':
      if entry['name'] != primary['name']:
        entry['mirror'] = primary['name']
    elif mode == 'extend':
      entry['x'] = offset
      offset += round(logical_size(entry, outputs)[0])
  return validate(ordered, outputs)


def apply(plan):
  # Enable the destination before disabling an old source; mirrors come second.
  ordered = sorted(plan, key=lambda entry: (not entry['enabled'], bool(entry['mirror'])))
  expressions = []
  for entry in ordered:
    rule = {'output': entry['name'], 'disabled': not entry['enabled'], 'mode': entry['mode'],
      'scale': entry['scale'], 'transform': entry['transform'], 'position': f"{entry['x']}x{entry['y']}", 'mirror': entry['mirror']}
    # lua_value intentionally supports only safe data; numeric fields are validated.
    parts = [key + ' = ' + (str(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else lua_value(value)) for key, value in rule.items()]
    expressions.append('hl.monitor({ ' + ', '.join(parts) + ' })')
  native(['eval', '; '.join(expressions)])


def matches(plan, outputs):
  actual = {output['name']: output for output in outputs}
  for entry in plan:
    current = actual.get(entry['name'])
    if not current or current['enabled'] != entry['enabled']:
      return False
    if not entry['enabled']:
      continue
    if current['mirror'] != entry['mirror']:
      return False
    if entry['mode'] != 'preferred':
      w, h, r = mode_parts(entry['mode'])
      aw, ah, ar = mode_parts(current['mode'])
      if (w, h) != (aw, ah) or abs(r - ar) > .1:
        return False
    if not entry['mirror'] and (abs(current['scale'] - entry['scale']) > .01 or current['transform'] != entry['transform'] or (current['x'], current['y']) != (entry['x'], entry['y'])):
      return False
  return True


def wait_applied(plan, timeout=5):
  deadline = time.monotonic() + timeout
  actual = []
  while time.monotonic() < deadline:
    actual = query()
    if matches(plan, actual):
      return
    time.sleep(.15)
  summary = '; '.join(f"{entry['name']}: {entry['mode']}, escala {entry['scale']}, posición {entry['x']},{entry['y']}, espejo {entry['mirror'] or 'no'}, activa {entry['enabled']}" for entry in actual)
  raise RuntimeError('Hyprland no pudo aplicar el modo elegido; se recuperará la configuración anterior. ' + summary)


def restore(before):
  outputs = query()
  by_name = {entry['name']: entry for entry in before}
  plan = []
  for output in outputs:
    entry = copy.deepcopy(by_name.get(output['name'], plan_for([output])[0]))
    if entry['mirror'] not in {item['name'] for item in outputs}:
      entry['mirror'] = ''
    if entry['mode'] != 'preferred' and entry['mode'] not in output['modes']:
      entry.update(mode='preferred', scale=1)
    plan.append(entry)
  if plan and not any(entry['enabled'] and not entry['mirror'] for entry in plan):
    primary = next((entry for entry in plan if entry['name'].startswith(('eDP', 'LVDS', 'DSI'))), plan[0])
    primary.update(enabled=True, mirror='', mode='preferred', scale=1, x=0, y=0)
  if plan:
    apply(plan)
    wait_applied(plan)


def read_profiles(path):
  try:
    document = read_json(path)
    if document.get('version') == 1 and isinstance(document.get('profiles'), dict):
      return document
  except (OSError, ValueError, AttributeError):
    pass
  return {'version': 1, 'profiles': {}, 'fallbacks': {}}


def save_profile(metadata):
  path = Path(metadata['profiles'])
  document = read_profiles(path)
  profiles = document['profiles']
  profiles[metadata['topology']] = {'outputs': metadata['after'], 'updated': time.time()}
  while len(profiles) > 20:
    del profiles[min(profiles, key=lambda key: profiles[key].get('updated', 0))]
  fallbacks = document.setdefault('fallbacks', {})
  for output in metadata['connected']:
    previous = next(entry for entry in metadata['before'] if entry['name'] == output['name'])
    if previous['enabled'] and not previous['mirror']:
      fallbacks[output['identity']] = previous
  atomic_write(path, (json.dumps(document, ensure_ascii=False, indent=2) + '\n').encode())


def request(folder, command):
  with socket.socket(socket.AF_UNIX) as connection:
    connection.settimeout(10 if command in {'confirm', 'revert'} else 2)
    connection.connect(str(folder / 'control'))
    connection.sendall((json.dumps({'command': command}) + '\n').encode())
    data = connection.recv(4096)
  result = json.loads(data)
  if result.get('error'):
    raise RuntimeError(result['error'])
  return result


def guardian(folder):
  metadata = read_json(folder / 'transaction.json')
  server = socket.socket(socket.AF_UNIX)
  server.bind(str(folder / 'control'))
  server.listen(4)
  deadline = time.monotonic() + CONFIRM_SECONDS + 10
  status = {'token': folder.name, 'status': 'pending', 'deadline': time.time() + CONFIRM_SECONDS + 10}
  print('ready', flush=True)
  with server, selectors.DefaultSelector() as selector:
    selector.register(server, selectors.EVENT_READ)
    while status['status'] == 'pending':
      remaining = deadline - time.monotonic()
      if remaining <= 0:
        try:
          restore(metadata['before'])
          status.update(status='reverted', reason='timeout')
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
          status.update(status='error', error=str(error))
        break
      if not selector.select(remaining):
        continue
      connection, _ = server.accept()
      with connection:
        connection.settimeout(2)
        try:
          _, uid, _ = struct.unpack('3i', connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
          if uid != os.getuid():
            raise ValueError('Usuario de confirmación inválido')
          message = json.loads(connection.recv(1024))
          command = message.get('command')
          if command == 'arm':
            deadline = time.monotonic() + CONFIRM_SECONDS
            status['deadline'] = time.time() + CONFIRM_SECONDS
          elif command == 'confirm':
            current = query()
            if topology(current) != metadata['topology']:
              raise ValueError('Las pantallas conectadas cambiaron; recupera la configuración anterior')
            if not matches(metadata['after'], current):
              raise ValueError('La imagen actual no coincide con la prueba; recupera la configuración anterior')
            save_profile(metadata)
            status.update(status='confirmed')
          elif command == 'revert':
            restore(metadata['before'])
            status.update(status='reverted', reason='cancelled')
          elif command != 'status':
            raise ValueError('Acción de confirmación desconocida')
          if status['status'] != 'pending':
            atomic_write(folder / 'result.json', (json.dumps(status) + '\n').encode())
          connection.sendall(json.dumps(status).encode())
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
          try:
            connection.sendall(json.dumps({'error': str(error)[:500]}).encode())
          except OSError:
            pass
  atomic_write(folder / 'result.json', (json.dumps(status) + '\n').encode())


class Displays:
  def __init__(self, service, api):
    self.s, self.api = service, api
    self.lock = threading.RLock()
    self.profiles = service.store.directory / 'display-profiles.json'
    self.last_topology = ''
    self.timer = None
    self.folder = None
    self.state = {'available': False, 'outputs': [], 'pending': None, 'error': '', 'notice': ''}

  def runtime(self):
    runtime = Path(os.environ.get('XDG_RUNTIME_DIR', '/run/user/' + str(os.getuid())))
    session = hashlib.sha256(os.environ.get('HYPRLAND_INSTANCE_SIGNATURE', '').encode()).hexdigest()[:8]
    return private_directory(runtime / 'hyprlarp/d' / session)

  def pending(self):
    try:
      current = read_json(self.runtime() / 'current.json')
      if (current.get('signature') != os.environ.get('HYPRLAND_INSTANCE_SIGNATURE')
          or current.get('profiles') != str(self.profiles) or not re.fullmatch(r'[a-z0-9_]{8,32}', current.get('token', ''))):
        return None
      folder = self.runtime() / current['token']
      try:
        status = read_json(folder / 'result.json')
      except FileNotFoundError:
        status = request(folder, 'status')
      self.folder = folder
      if status['status'] == 'pending':
        return status
      self.state['notice'] = 'Pantallas guardadas' if status['status'] == 'confirmed' else 'Se recuperó la configuración anterior'
      if status['status'] == 'error':
        self.state['error'] = status.get('error', 'No se pudo recuperar la imagen')
      (self.runtime() / 'current.json').unlink(missing_ok=True)
    except (OSError, ValueError, KeyError, RuntimeError):
      pass
    return None

  def refresh(self, reason='manual'):
    with self.lock:
      try:
        outputs = query()
        self.state['error'] = ''
        pending = self.pending() if not self.s.preview else None
        key = topology(outputs)
        document = read_profiles(self.profiles)
        if not self.s.preview and not pending and outputs:
          if reason == 'startup' or reason == 'configreloaded' or (reason == 'event' and key != self.last_topology):
            profile = document['profiles'].get(key)
            if profile:
              try:
                desired = validate(profile['outputs'], outputs)
                if not matches(desired, outputs):
                  apply(desired)
                  outputs = query()
              except (ValueError, TypeError, KeyError):
                self.state['notice'] = 'El diseño guardado ya no es compatible. Revisa los modos disponibles'
            elif not any(output['enabled'] and not output['mirror'] for output in outputs):
              before = [document.get('fallbacks', {}).get(output['identity'], plan_for([output])[0]) for output in outputs]
              restore(before)
              outputs = query()
        self.last_topology = key
        self.state.update(available=True, outputs=outputs, pending=pending)
        if pending and self.timer is None:
          self.timer = threading.Timer(max(.5, pending['deadline'] - time.time() + .3), self.refresh)
          self.timer.daemon = True
          self.timer.start()
      except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError) as error:
        self.state.update(available=False, error=str(error)[:500])
      self.s.emit('displays', copy.deepcopy(self.state))

  def test(self, plan):
    if self.s.preview:
      raise RuntimeError('La vista previa no cambia las pantallas')
    with transaction_lock(self.runtime()):
      return self._test(plan)

  def _test(self, plan):
    with self.lock:
      if self.s.preview:
        raise RuntimeError('La vista previa no cambia las pantallas')
      if self.pending():
        raise ValueError('Confirma o recupera la prueba de pantalla en curso')
      outputs = query()
      after = validate(plan, outputs)
      # Keep a bounded recent diagnostic trail without touching active trials.
      history = sorted((path for path in self.runtime().glob('test_*') if path.is_dir() and not path.is_symlink() and (path / 'result.json').is_file()), key=lambda path: path.stat().st_mtime, reverse=True)
      for old in history[9:]:
        for name in ('transaction.json', 'result.json', 'guardian.log', 'control'):
          (old / name).unlink(missing_ok=True)
        try:
          old.rmdir()
        except OSError:
          pass
      folder = Path(tempfile.mkdtemp(prefix='test_', dir=self.runtime()))
      folder.chmod(0o700)
      metadata = {'before': plan_for(outputs), 'after': after, 'connected': outputs,
        'profiles': str(self.profiles), 'topology': topology(outputs)}
      atomic_write(folder / 'transaction.json', (json.dumps(metadata) + '\n').encode())
      with (folder / 'guardian.log').open('wb') as log:
        child = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), 'guard', str(folder)],
          stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=log, start_new_session=True)
      try:
        with selectors.DefaultSelector() as selector:
          selector.register(child.stdout, selectors.EVENT_READ)
          if not selector.select(3) or child.stdout.readline().strip() != b'ready':
            child.stdout.close()
            child.terminate()
            child.wait(timeout=2)
            detail = (folder / 'guardian.log').read_text()[-350:]
            raise RuntimeError('No se pudo preparar la recuperación automática de imagen: ' + detail)
        child.stdout.close()
        threading.Thread(target=child.wait, daemon=True, name='display-guardian-reaper').start()
        atomic_write(self.runtime() / 'current.json', (json.dumps({'token': folder.name,
          'signature': os.environ.get('HYPRLAND_INSTANCE_SIGNATURE'), 'profiles': str(self.profiles)}) + '\n').encode())
        apply(after)
        wait_applied(after)
        status = request(folder, 'arm')
        self.folder = folder
        self.state.update(pending=status, error='', notice='')
        if self.timer:
          self.timer.cancel()
        self.timer = threading.Timer(CONFIRM_SECONDS + .3, self.refresh)
        self.timer.daemon = True
        self.timer.start()
        self.refresh()
      except BaseException:
        try:
          request(folder, 'revert')
        except (OSError, ValueError, RuntimeError):
          restore(metadata['before'])
        raise

  def handle(self, action, data):
    if action not in {'displays-refresh', 'displays-event', 'displays-test', 'displays-preset', 'displays-confirm', 'displays-revert'}:
      return False
    if action in {'displays-refresh', 'displays-event'}:
      self.refresh('configreloaded' if data.get('reason') == 'configreloaded' else 'event' if action == 'displays-event' else 'manual')
    elif action in {'displays-confirm', 'displays-revert'}:
      with self.lock:
        pending = self.pending()
        if not pending or data.get('token') != pending['token']:
          raise ValueError('La prueba de pantalla ya terminó')
        request(self.folder, 'confirm' if action == 'displays-confirm' else 'revert')
        if self.timer:
          self.timer.cancel()
        self.refresh()
    else:
      if action == 'displays-test':
        self.test(data.get('outputs'))
      else:
        outputs = query()
        self.test(preset(data.get('mode'), outputs, data.get('primary'), data.get('secondary')))
    return True


if __name__ == '__main__':
  if len(sys.argv) != 3 or sys.argv[1] != 'guard':
    raise SystemExit('Internal display guardian')
  guardian(Path(sys.argv[2]))
