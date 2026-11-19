"""On-demand measurements of the shell's own processes, with bounded history."""

from collections import deque
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import threading
import time
import uuid

try:
  from .persistence import atomic_json
  from .safety import read_json
  from .theme_context import effective_name
except ImportError:
  from persistence import atomic_json
  from safety import read_json
  from theme_context import effective_name

TICKS = os.sysconf('SC_CLK_TCK')
PAGE = os.sysconf('SC_PAGE_SIZE')
MIB = 1024 ** 2
HISTORY_LIMIT = 20


def finite(value, low=0, high=10 ** 12):
  return type(value) in {int, float} and math.isfinite(value) and low <= value <= high


def process_stat(pid, proc=Path('/proc')):
  path = proc / str(pid)
  if path.stat().st_uid != os.getuid():
    raise ValueError('El proceso pertenece a otro usuario')
  with (path / 'stat').open() as source:
    fields = source.read(8192).rsplit(') ', 1)[1].split()
  if fields[0] in {'Z', 'X'}:
    raise ValueError('El proceso ya terminó')
  return {'pid': pid, 'parent': int(fields[1]), 'ticks': int(fields[11]) + int(fields[12]),
    'threads': int(fields[17]), 'start': int(fields[19]), 'rssBytes': max(0, int(fields[21])) * PAGE}


class ProcessSampler:
  """Only renderer, backend and verified parent supervisor; never launched apps."""
  def __init__(self, root, *, proc=Path('/proc'), clock=time.monotonic, pids=None):
    self.root, self.proc, self.clock = Path(root), proc, clock
    self.targets = {}
    if pids is None:
      pids = {'backend': os.getpid()}
      parent = os.getppid()
      try:
        if (proc / str(parent) / 'exe').readlink().name in {'quickshell', 'qs'}:
          pids['interface'] = parent
          grandparent = process_stat(parent, proc)['parent']
          arguments = (proc / str(grandparent) / 'cmdline').read_bytes().split(b'\0')
          if os.fsencode(self.root / 'bin/hyprlarp') in arguments:
            pids['supervisor'] = grandparent
      except (OSError, ValueError, IndexError):
        pass
    for role, pid in pids.items():
      try:
        self.targets[role] = process_stat(pid, proc)
      except (OSError, ValueError, IndexError):
        pass
    self.previous = None
    self.pss = {}
    self.pss_at = -math.inf

  def reset(self):
    self.previous = None

  def sample(self):
    now = self.clock()
    current = {}
    for role, target in self.targets.items():
      try:
        item = process_stat(target['pid'], self.proc)
        if item['start'] == target['start']:
          current[role] = item
      except (OSError, ValueError, IndexError):
        continue
    if not current:
      raise RuntimeError('No se encontraron los procesos de HyprLarp')
    if now - self.pss_at >= 8 or set(current) != set(self.pss):
      self.pss = {}
      for role, item in current.items():
        try:
          with (self.proc / str(item['pid']) / 'smaps_rollup').open() as source:
            lines = source.read(65536).splitlines()
          self.pss[role] = next(int(line.split()[1]) * 1024 for line in lines if line.startswith('Pss:'))
        except (OSError, ValueError, StopIteration):
          self.pss[role] = None
      self.pss_at = now
    elapsed = now - self.previous[0] if self.previous else 0
    complete = self.previous is not None and set(current) == set(self.previous[1]) and elapsed > 0
    parts = []
    cpu_seconds = 0
    for role, item in current.items():
      delta = None
      if complete:
        previous = self.previous[1][role]
        delta = max(0, item['ticks'] - previous['ticks']) / TICKS
        cpu_seconds += delta
      parts.append({'role': role, 'pid': item['pid'], 'cpuPercent': round(100 * delta / elapsed, 2) if delta is not None else None,
        'rssMiB': round(item['rssBytes'] / MIB, 2),
        'pssMiB': round(self.pss[role] / MIB, 2) if self.pss.get(role) is not None else None, 'threads': item['threads']})
    self.previous = (now, current)
    pss = sum(self.pss.values()) / MIB if all(value is not None for value in self.pss.values()) else None
    return {'time': round(now, 3), 'cpuPercent': round(cpu_seconds / elapsed * 100, 2) if complete else None,
      'rssMiB': round(sum(item['rssBytes'] for item in current.values()) / MIB, 2),
      'pssMiB': round(pss, 2) if pss is not None else None, 'pssAgeSeconds': round(now - self.pss_at, 1),
      'processes': len(parts), 'threads': sum(item['threads'] for item in parts), 'parts': parts,
      '_cpuSeconds': cpu_seconds if complete else None, '_elapsed': elapsed if complete else 0}


def package_revision(root):
  """Stable package identity without git, subprocesses or a background watcher."""
  def relevant(name):
    return name.split('/')[0] in {'backend', 'bin', 'config', 'components', 'core', 'panels', 'widgets', 'assets', 'greeter'} or name in {'VERSION', 'HyprLarp.qml', 'shell.qml', 'preview.qml', 'settings.qml', 'recovery.qml'}
  try:
    manifest = read_json(root / '.hyprlarp-install.json', limit=4 * MIB)
    entries = {name: value for name, value in manifest['files'].items() if relevant(name)}
    if not entries or any(not isinstance(value, str) or len(value) != 64 for value in entries.values()):
      raise ValueError('Invalid package manifest')
  except (OSError, ValueError, KeyError, TypeError, AttributeError):
    entries = {}
    roots = [entry for entry in root.iterdir() if relevant(entry.name) and not entry.is_symlink()]
    paths = (path for entry in sorted(roots) for path in ([entry] if entry.is_file() else sorted(entry.rglob('*'))))
    for path in paths:
      relative = path.relative_to(root)
      if not relevant(relative.as_posix()) or any(part.startswith('.') or part == '__pycache__' for part in relative.parts):
        continue
      if path.is_file() and not path.is_symlink() and path.stat().st_size <= 4 * MIB:
        entries[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
      if len(entries) >= 2048:
        break
  return hashlib.sha256(json.dumps(entries, sort_keys=True).encode()).hexdigest()[:12]


def valid_report(item):
  if not isinstance(item, dict) or item.get('type') != 'hyprlarp-performance' or item.get('version') != 1:
    return False
  if not isinstance(item.get('id'), str) or len(item['id']) != 32 or any(c not in '0123456789abcdef' for c in item['id']):
    return False
  if not isinstance(item.get('label'), str) or len(item['label']) > 64 or not finite(item.get('createdAt'), high=10 ** 15):
    return False
  if not isinstance(item.get('revision'), str) or len(item['revision']) != 12:
    return False
  summary, context = item.get('summary'), item.get('context')
  if not isinstance(summary, dict) or not isinstance(context, dict) or not isinstance(context.get('fingerprint'), str):
    return False
  for key in ['seconds', 'samples', 'cpuPercent', 'rssMiB', 'peakRssMiB', 'processes', 'threads']:
    if not finite(summary.get(key)):
      return False
  return summary.get('pssMiB') is None or finite(summary['pssMiB'])


class Performance:
  def __init__(self, root, directory, *, preview=False, settings_only=False, clock=time.monotonic, sampler=None):
    self.root, self.directory, self.clock = Path(root), Path(directory), clock
    self.mode = 'preview' if preview else 'settings-only' if settings_only else 'native'
    self.sampler = sampler or ProcessSampler(root, clock=clock)
    self.lock = threading.RLock()
    self.open = False
    self.paused = False
    self.current = None
    self.samples = deque(maxlen=60)
    self.panel_loads = deque(maxlen=10)
    self.screens = []
    self.recording = None
    self.error = ''
    self.notice = ''
    self.startup = None
    self.revision = ''
    self.history_path = self.directory / 'performance-history.json'
    self.preferences_path = self.directory / 'performance-preferences.json'
    self.thresholds = {'cpuPercent': 80.0, 'rssMiB': 1024.0}
    try:
      saved = read_json(self.preferences_path, limit=4096)
      if isinstance(saved, dict):
        for key, low, high in [('cpuPercent', 1, 1000), ('rssMiB', 64, 1048576)]:
          if finite(saved.get(key), low, high):
            self.thresholds[key] = float(saved[key])
    except (FileNotFoundError, OSError, ValueError):
      pass
    self.history = []
    try:
      data = read_json(self.history_path, limit=256 * 1024)
      if isinstance(data, list):
        self.history = [item for item in data if valid_report(item)][-HISTORY_LIMIT:]
    except FileNotFoundError:
      pass
    except (OSError, ValueError):
      self.error = 'No se pudo leer el historial de rendimiento.'

  def version(self):
    if not self.revision:
      self.revision = package_revision(self.root)
    return self.revision

  def mark_ready(self):
    """Called once the actual QML interface acknowledges its initial settings."""
    with self.lock:
      if self.startup is not None:
        return
      target = self.sampler.targets.get('interface')
      if not target:
        return
      try:
        boot_id = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        identity = f"{boot_id}:{target['pid']}:{target['start']}"
        filename = 'performance-startup.json' if self.mode == 'native' else 'performance-startup-' + self.mode + '.json'
        path = self.directory / filename
        try:
          saved = read_json(path, limit=4096)
          if saved.get('identity') == identity and finite(saved.get('readyMs'), high=120000):
            self.startup = saved
            return
        except (OSError, ValueError, AttributeError):
          pass
        elapsed = time.clock_gettime(time.CLOCK_BOOTTIME) - target['start'] / TICKS
        if not 0 <= elapsed <= 120:
          return
        self.startup = {'identity': identity, 'readyMs': round(elapsed * 1000, 1), 'createdAt': round(time.time() * 1000)}
        atomic_json(path, self.startup)
      except (OSError, ValueError):
        pass

  def set_open(self, opened):
    with self.lock:
      if opened != self.open:
        self.sampler.reset()
        if opened:
          self.samples.clear()
          self.current = None
        if not opened and self.recording:
          self.recording = None
          self.notice = 'Medición cancelada al cerrar el panel.'
      self.open = opened

  def context(self, settings):
    preferences = {key: value for key, value in settings.items() if key not in {'doNotDisturb', 'clipboardPaused'}}
    result = {'mode': self.mode, 'renderer': os.environ.get('QT_QUICK_BACKEND', 'native'),
      'platform': os.uname().release, 'screens': self.screens,
      'effectiveTheme': effective_name(settings),
      'settingsHash': hashlib.sha256(json.dumps(preferences, sort_keys=True).encode()).hexdigest()[:16]}
    result['fingerprint'] = hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest()[:24]
    return copy.deepcopy(result)

  def set_screens(self, data):
    if not isinstance(data, list) or len(data) > 32:
      raise ValueError('Pantallas de la medición inválidas')
    screens = []
    for item in data:
      if not isinstance(item, dict) or not isinstance(item.get('name'), str) or len(item['name']) > 256:
        raise ValueError('Pantalla de la medición inválida')
      if not all(finite(item.get(key), 1, 65536) for key in ['width', 'height']):
        raise ValueError('Dimensiones de pantalla inválidas')
      screens.append({key: item[key] for key in ['name', 'width', 'height']})
    with self.lock:
      self.screens = sorted(screens, key=lambda item: item['name'])

  def panel_loaded(self, name, elapsed):
    if not isinstance(name, str) or len(name) > 64 or not finite(elapsed, high=60000):
      raise ValueError('Tiempo de carga inválido')
    with self.lock:
      self.panel_loads.append({'name': name, 'milliseconds': round(elapsed), 'createdAt': round(time.time() * 1000)})

  def snapshot(self):
    with self.lock:
      recording = None
      if self.recording:
        elapsed = self.clock() - self.recording['started']
        recording = {'label': self.recording['label'], 'seconds': self.recording['seconds'], 'elapsed': round(elapsed, 1),
          'progress': min(1, elapsed / self.recording['seconds'])}
      return copy.deepcopy({'mode': self.mode, 'revision': self.revision, 'paused': self.paused,
        'current': self.current, 'samples': list(self.samples), 'history': self.history, 'recording': recording,
        'startup': self.startup, 'panelLoads': list(self.panel_loads), 'error': self.error, 'notice': self.notice,
        'cpuTickMs': 1000 / TICKS, 'intervalSeconds': 2, 'thresholds': self.thresholds})

  def set_thresholds(self, data):
    values = {}
    for key, low, high in [('cpuPercent', 1, 1000), ('rssMiB', 64, 1048576)]:
      value = data.get(key)
      if not finite(value, low, high):
        raise ValueError('Umbral de rendimiento inválido')
      values[key] = float(value)
    atomic_json(self.preferences_path, values)
    self.thresholds = values

  def sample(self, settings):
    with self.lock:
      if not self.open:
        return self.snapshot()
      self.version()
      sample = self.sampler.sample()
      self.current = {key: value for key, value in sample.items() if not key.startswith('_')}
      self.samples.append({key: self.current[key] for key in ['time', 'cpuPercent', 'rssMiB']})
      if self.recording:
        recording = self.recording
        if recording['context']['fingerprint'] != self.context(settings)['fingerprint']:
          self.recording = None
          self.error = 'Medición cancelada: cambió la configuración, el tema o las pantallas.'
        elif sample['cpuPercent'] is None:
          self.recording = None
          self.error = 'Medición cancelada: cambió un proceso del shell.'
        else:
          recording['points'].append(sample)
          if self.clock() - recording['started'] >= recording['seconds']:
            self.finish_recording()
      return self.snapshot()

  def begin_recording(self, label, seconds, settings):
    if not isinstance(label, str) or len(label) > 64 or any(ord(c) < 32 for c in label):
      raise ValueError('Usa un nombre de hasta 64 caracteres')
    if not finite(seconds, 5, 120):
      raise ValueError('La medición debe durar entre 5 y 120 segundos')
    with self.lock:
      if not self.open or self.paused or self.recording:
        raise ValueError('Abre el panel y reanuda el muestreo antes de medir')
      self.sampler.reset()
      self.sample(settings)
      self.error = self.notice = ''
      self.recording = {'label': label.strip() or 'Medición', 'seconds': seconds, 'started': self.clock(),
        'context': self.context(settings), 'initialRssMiB': self.current['rssMiB'], 'points': []}

  def finish_recording(self):
    recording = self.recording
    self.recording = None
    points = recording['points']
    elapsed = sum(point['_elapsed'] for point in points)
    if not points or elapsed <= 0:
      self.error = 'No hay suficientes muestras para guardar la medición.'
      return
    last = points[-1]
    report = {'type': 'hyprlarp-performance', 'version': 1, 'id': uuid.uuid4().hex,
      'label': recording['label'], 'createdAt': round(time.time() * 1000), 'revision': self.version(),
      'context': recording['context'], 'startupMs': self.startup['readyMs'] if self.startup else None,
      'summary': {'seconds': round(elapsed, 2), 'samples': len(points),
        'cpuPercent': round(100 * sum(point['_cpuSeconds'] for point in points) / elapsed, 2),
        'rssMiB': last['rssMiB'], 'peakRssMiB': max(recording['initialRssMiB'], max(point['rssMiB'] for point in points)), 'pssMiB': last['pssMiB'],
        'processes': last['processes'], 'threads': last['threads']}}
    history = (self.history + [report])[-HISTORY_LIMIT:]
    try:
      atomic_json(self.history_path, history)
      self.history = history
      self.notice = 'Medición guardada: ' + report['label']
    except OSError:
      self.error = 'No se pudo guardar la medición; las muestras actuales siguen disponibles.'

  def handle(self, action, data, settings):
    with self.lock:
      if action == 'performance-ready':
        self.mark_ready()
        return
      if action == 'performance-panel-loaded':
        self.panel_loaded(data.get('name'), data.get('milliseconds'))
        return
      if action == 'performance-context':
        self.set_screens(data.get('screens'))
        return
      if action == 'performance-thresholds':
        self.set_thresholds(data)
        return
      if not self.open:
        raise ValueError('Abre el panel de rendimiento')
      if action == 'performance-pause':
        if not isinstance(data.get('paused'), bool) or self.recording:
          raise ValueError('No se puede pausar durante una medición')
        self.paused = data['paused']
        self.sampler.reset()
      elif action == 'performance-refresh':
        if self.recording:
          raise ValueError('Espera a que termine la medición')
        self.sample(settings)
      elif action == 'performance-record':
        self.begin_recording(data.get('label', ''), data.get('seconds', 15), settings)
      elif action == 'performance-cancel':
        self.recording = None
        self.notice = 'Medición cancelada.'
      elif action == 'performance-delete':
        identifier = data.get('id')
        if not isinstance(identifier, str) or not any(item['id'] == identifier for item in self.history):
          raise ValueError('Medición desconocida')
        history = [item for item in self.history if item['id'] != identifier]
        atomic_json(self.history_path, history)
        self.history = history
      else:
        raise ValueError('Acción de rendimiento desconocida')
