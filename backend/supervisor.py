"""Supervise only the shell process and fall back to an independent QML UI."""

import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import threading
import time

from .persistence import atomic_json
from .safety import private_directory, read_json


class FailureWindow:
  def __init__(self):
    self.events = []

  def failed(self, now):
    self.events = [stamp for stamp in self.events if now - 300 <= stamp <= now] + [now]
    return len(self.events) >= 3


def identity(pid):
  process = Path('/proc') / str(pid)
  if process.stat().st_uid != os.getuid():
    raise ValueError('El supervisor pertenece a otro usuario')
  return process.joinpath('stat').read_text().rsplit(') ', 1)[1].split()[19]


def state_path(root, environment):
  folder = private_directory(Path(environment.get('XDG_RUNTIME_DIR', '/run/user/' + str(os.getuid()))) / 'hyprlarp')
  key = str(Path(root).resolve()) + '\0' + environment.get('HYPRLAND_INSTANCE_SIGNATURE', '')
  return folder / ('supervisor-' + hashlib.sha256(key.encode()).hexdigest()[:20] + '.json')


def request(root, mode, *, environment=None):
  if mode not in {'normal', 'recovery'}:
    raise ValueError('Modo de recuperación desconocido')
  environment = dict(os.environ if environment is None else environment)
  from .recovery import current_session
  session_resolved = False
  try:
    environment = current_session(environment)
    session_resolved = True
  except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
    pass
  path = state_path(root, environment)
  # With a verified compositor, a missing state file means this session has no
  # supervisor. Searching other signatures would signal a different desktop.
  candidates = [path] if session_resolved or path.is_file() else list(path.parent.glob('supervisor-*.json'))
  matches = []
  for candidate in candidates:
    try:
      value = read_json(candidate, limit=4096)
      if session_resolved and value.get('signature') != environment.get('HYPRLAND_INSTANCE_SIGNATURE', ''):
        continue
      pid = value.get('pid')
      if value.get('root') == str(Path(root).resolve()) and isinstance(pid, int) and pid > 1 and identity(pid) == value.get('identity'):
        process_environment = (Path('/proc') / str(pid) / 'environ').read_bytes().split(b'\0')
        arguments = (Path('/proc') / str(pid) / 'cmdline').read_bytes().split(b'\0')
        if b'HYPRLARP_SUPERVISOR=1' in process_environment or os.fsencode(Path(root) / 'bin/hyprlarp') in arguments:
          matches.append(value)
    except (OSError, ValueError, TypeError, AttributeError):
      continue
  if len(matches) != 1:
    raise RuntimeError('No se encontró un supervisor de HyprLarp único en esta sesión. Usa hyprlarp start.')
  value = matches[0]
  os.kill(value['pid'], signal.SIGUSR1 if mode == 'normal' else signal.SIGUSR2)
  return value


def terminate(child, timeout=8):
  if child is None or child.poll() is not None:
    return
  child.terminate()
  try:
    child.wait(timeout=timeout)
  except subprocess.TimeoutExpired:
    child.kill()
    child.wait(timeout=3)


def notify_exit(child, event):
  """Wake only for this child, leaving reaping and shutdown to its owner."""
  try:
    try:
      # WNOWAIT avoids taking Popen's waitpid lock while the renderer runs.
      # Main-thread terminate()/wait(timeout) therefore stays bounded even if
      # the renderer ignores SIGTERM, or a control signal arrives immediately.
      os.waitid(os.P_PID, child.pid, os.WEXITED | os.WNOWAIT)
    except (AttributeError, OSError):
      child.wait()
  finally:
    event.set()


def supervise(root, binary, environment=None, *, startup_timeout=18, readiness=None, shutdown_timeout=8):
  from .recovery import healthy
  root = Path(root).resolve()
  environment = dict(os.environ if environment is None else environment)
  path = state_path(root, environment)
  lock = os.open(path.with_suffix('.lock'), os.O_CREAT | os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600)
  try:
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
  except BaseException:
    os.close(lock)
    raise
  policy = FailureWindow()
  interrupted = threading.Event()
  child_wakeup = None
  child = None
  stopping = False
  requested = None
  mode = 'normal'
  reason = ''
  old_handlers = {}

  def control(signum, frame):
    nonlocal stopping, requested
    if signum in {signal.SIGTERM, signal.SIGINT}:
      stopping = True
    else:
      requested = 'normal' if signum == signal.SIGUSR1 else 'recovery'
    interrupted.set()
    if child_wakeup is not None:
      child_wakeup.set()
    if child is not None and child.poll() is None:
      child.terminate()

  for number in [signal.SIGTERM, signal.SIGINT, signal.SIGUSR1, signal.SIGUSR2]:
    old_handlers[number] = signal.signal(number, control)
  try:
    while not stopping:
      if requested:
        mode, requested = requested, None
        if mode == 'normal':
          policy.events = []
      interrupted.clear()
      atomic_json(path, {'pid': os.getpid(), 'identity': identity(os.getpid()), 'root': str(root),
        'signature': environment.get('HYPRLAND_INSTANCE_SIGNATURE', ''), 'mode': mode, 'reason': reason})
      child_environment = {**environment, 'HYPRLARP_SUPERVISOR_PID': str(os.getpid()),
        'HYPRLARP_RECOVERY_REASON': reason, 'QT_LINUX_ACCESSIBILITY_ALWAYS_ON': '1'}
      entry = 'recovery.qml' if mode == 'recovery' else 'shell.qml'
      child_wakeup = threading.Event()
      child = subprocess.Popen([binary, '--path', str(root / entry), '--no-duplicate'], env=child_environment)
      deadline, stable = time.monotonic() + startup_timeout, 0
      ready = False
      while not stopping and requested is None and child.poll() is None and time.monotonic() < deadline:
        try:
          valid = readiness(child, mode) if readiness else healthy(root, binary)
          stable = stable + 1 if valid else 0
          if stable >= 3:
            ready = True
            break
        except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError):
          stable = 0
        interrupted.wait(.2)
      if stopping or requested:
        terminate(child, shutdown_timeout)
        continue
      if ready:
        # One blocking kernel wait replaces subprocess.wait(timeout)'s busy
        # wait. Each generation captures its own event, so a late notification
        # from the previous renderer cannot wake a replacement renderer.
        watcher = threading.Thread(target=notify_exit, args=(child, child_wakeup),
          name='hyprlarp-renderer-exit', daemon=True)
        watcher.start()
        child_wakeup.wait()
        if stopping or requested:
          terminate(child, shutdown_timeout)
          watcher.join(timeout=3)
          continue
        code = child.wait()
        watcher.join(timeout=3)
        if code == 0:
          return 0
        reason = 'El proceso del shell terminó inesperadamente.'
      else:
        timed_out = child.poll() is None
        terminate(child, shutdown_timeout)
        reason = 'La interfaz no pudo completar su arranque.'
        if timed_out and mode == 'normal':
          mode = 'recovery'
          continue
      if mode == 'recovery':
        return 1
      mode = 'recovery' if policy.failed(time.monotonic()) else 'normal'
      if mode == 'normal':
        interrupted.wait(2)
    return 0
  finally:
    terminate(child, shutdown_timeout)
    path.unlink(missing_ok=True)
    for number, handler in old_handlers.items():
      signal.signal(number, handler)
    os.close(lock)
