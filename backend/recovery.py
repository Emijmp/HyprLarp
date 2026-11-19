"""Session-scoped systemd supervision; health checks run only during startup."""

import fcntl
import json
import os
from pathlib import Path
import subprocess
import time

from .safety import private_directory, read_json

UNIT = 'hyprlarp.service'
ENVIRONMENT = {
  'PATH', 'DISPLAY', 'WAYLAND_DISPLAY', 'HYPRLAND_INSTANCE_SIGNATURE',
  'XDG_RUNTIME_DIR', 'XDG_SESSION_ID', 'XDG_SESSION_TYPE', 'XDG_CURRENT_DESKTOP',
  'XDG_SESSION_DESKTOP', 'XDG_CONFIG_HOME', 'XDG_DATA_HOME', 'XDG_STATE_HOME',
  'XDG_CACHE_HOME', 'XDG_DATA_DIRS', 'DBUS_SESSION_BUS_ADDRESS', 'LANG', 'LANGUAGE',
  'LC_ALL', 'LC_TIME', 'QT_QPA_PLATFORMTHEME', 'QT_STYLE_OVERRIDE', 'QS_ICON_THEME',
  'XCURSOR_THEME', 'XCURSOR_SIZE', 'HYPRCURSOR_THEME', 'HYPRCURSOR_SIZE',
  'GTK_IM_MODULE', 'QT_IM_MODULE', 'XMODIFIERS', 'SSH_AUTH_SOCK',
  'HYPRLARP_STATE_DIR', 'HYPRLARP_QUICKSHELL',
}


def run(args, *, check=True, timeout=8):
  result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
  if check and result.returncode:
    raise RuntimeError((result.stderr or result.stdout).strip() or 'Falló ' + args[0])
  return result


def systemd_word(value):
  """Exec* uses C quoting, percent specifiers and dollar expansion, not a shell."""
  if any(ord(char) < 32 for char in str(value)):
    raise ValueError('Ruta de servicio inválida')
  return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%').replace('$', '$$') + '"'


def render_unit(executable, root):
  command = systemd_word(executable)
  return ('# HyprLarp managed: ' + str(root) + '\n'
    '[Unit]\nDescription=HyprLarp desktop shell\n'
    'PartOf=graphical-session.target\nAfter=graphical-session.target\n'
    'StartLimitIntervalSec=300\nStartLimitBurst=3\n\n'
    '[Service]\nType=exec\n'
    'EnvironmentFile=%t/hyprlarp/session.env\n'
    'Environment=QT_QPA_PLATFORM=wayland PYTHONDONTWRITEBYTECODE=1 QT_LINUX_ACCESSIBILITY_ALWAYS_ON=1 HYPRLARP_SUPERVISOR=1\n'
    'UnsetEnvironment=HYPRLARP_PREVIEW HYPRLARP_SETTINGS_ONLY QT_QUICK_BACKEND\n'
    'ExecCondition=' + command + ' session-check\n'
    'ExecStart=' + command + ' run\n'
    'ExecStartPost=' + command + ' ready\n'
    'Restart=on-failure\nRestartSec=2\nTimeoutStartSec=60\nTimeoutStopSec=15\n'
    '# Applications and hyprlock launched by the shell have independent lifetimes.\n'
    'KillMode=process\nUMask=0077\nStandardOutput=journal\nStandardError=journal\n')


def unit_path(config=None):
  config = Path(config or os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config'))
  return config / 'systemd/user' / UNIT


def current_session(environment=None):
  environment = dict(os.environ if environment is None else environment)
  display = environment.get('WAYLAND_DISPLAY', '')
  runtime = Path(environment.get('XDG_RUNTIME_DIR', '/run/user/' + str(os.getuid())))
  if not display or not runtime.is_absolute() or runtime.stat().st_uid != os.getuid():
    raise RuntimeError('Inicia HyprLarp desde tu sesión Wayland')
  socket = Path(display) if Path(display).is_absolute() else runtime / display
  if not socket.is_socket():
    raise RuntimeError('La pantalla Wayland ya no está disponible')
  instances = json.loads(run(['hyprctl', 'instances', '-j']).stdout)
  match = next((entry for entry in instances if entry.get('wl_socket') == socket.name), None)
  if not match or not isinstance(match.get('instance'), str):
    raise RuntimeError('No se encontró la sesión activa de Hyprland')
  process = Path('/proc') / str(match['pid'])
  if process.stat().st_uid != os.getuid() or process.joinpath('comm').read_text().strip() != 'Hyprland':
    raise RuntimeError('La sesión de Hyprland no pertenece a tu usuario')
  environment.update(HYPRLAND_INSTANCE_SIGNATURE=match['instance'], XDG_RUNTIME_DIR=str(runtime))
  return environment


def session_alive():
  try:
    environment = current_session()
    return environment['HYPRLAND_INSTANCE_SIGNATURE'] == os.environ.get('HYPRLAND_INSTANCE_SIGNATURE')
  except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError):
    return False


def running_pids(root, entrypoint='shell.qml'):
  expected = os.fsencode(Path(root) / entrypoint)
  found = []
  for process in Path('/proc').iterdir():
    if not process.name.isdecimal():
      continue
    try:
      if (process.stat().st_uid == os.getuid()
          and process.joinpath('exe').readlink().name in {'quickshell', 'qs'}
          and expected in process.joinpath('cmdline').read_bytes().split(b'\0')):
        found.append(int(process.name))
    except OSError:
      continue
  return found


def has_visible_bar(value, namespace='hyprlarp-bar'):
  if isinstance(value, dict):
    if (value.get('namespace') == namespace and value.get('w', 0) > 0
        and value.get('h', 0) > 0 and value.get('alpha', 0) > 0):
      return True
    return any(has_visible_bar(child, namespace) for child in value.values())
  return isinstance(value, list) and any(has_visible_bar(child, namespace) for child in value)


def expects_bar(settings, monitors):
  return any({**settings, **settings.get('monitorBars', {}).get(monitor.get('name', ''), {})}
    .get('barEnabled', True) for monitor in monitors)


def healthy(root, binary, *, settings=None):
  entrypoint, target = 'shell.qml', 'shell'
  if not running_pids(root):
    if not running_pids(root, 'recovery.qml'):
      return False
    entrypoint, target = 'recovery.qml', 'recovery'
  result = run([binary, '--path', str(Path(root) / entrypoint), 'ipc', 'show'], check=False, timeout=3)
  if result.returncode or 'target ' + target not in result.stdout.splitlines() or 'ERROR' in result.stdout + result.stderr:
    return False
  if target == 'shell':
    result = run([binary, '--path', str(Path(root) / entrypoint), 'ipc', 'call', 'shell', 'health'], check=False, timeout=3)
    if result.returncode:
      return False
    try:
      state = json.loads(result.stdout)
    except (ValueError, TypeError):
      return False
    if (not isinstance(state, dict) or state.get('ready') is not True or state.get('connected') is not True
        or type(state.get('backendPid')) is not int or state['backendPid'] <= 1):
      return False
  monitors = json.loads(run(['hyprctl', '-j', 'monitors'], timeout=3).stdout)
  if not monitors:
    return False
  if target == 'recovery':
    return has_visible_bar(json.loads(run(['hyprctl', '-j', 'layers'], timeout=3).stdout), 'hyprlarp-recovery')
  if settings is None:
    config = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config')) / 'hyprlarp'
    settings = read_json(Path(os.environ.get('HYPRLARP_STATE_DIR', config)) / 'settings.json')
  return not expects_bar(settings, monitors) or has_visible_bar(json.loads(run(['hyprctl', '-j', 'layers'], timeout=3).stdout))


def wait_ready(root, binary, *, timeout=20):
  deadline, stable = time.monotonic() + timeout, 0
  while time.monotonic() < deadline:
    try:
      stable = stable + 1 if session_alive() and healthy(root, binary) else 0
      if stable >= 3:
        return
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError):
      stable = 0
    time.sleep(0.2)
  raise RuntimeError('HyprLarp no respondió o no mostró su barra. Consulta: journalctl --user -u ' + UNIT + ' -n 40')


def service_running(root, destination=None):
  destination = destination or unit_path()
  if not destination.is_file() or destination.is_symlink():
    return False
  if not destination.read_text().startswith('# HyprLarp managed: ' + str(root) + '\n'):
    return False
  result = run(['systemctl', '--user', 'show', UNIT, '-p', 'ActiveState', '-p', 'FragmentPath'], check=False)
  properties = dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)
  return properties.get('FragmentPath') == str(destination) and properties.get('ActiveState') in {'active', 'activating', 'reloading'}


def stop(root, binary, *, destination=None):
  if service_running(root, destination):
    run(['systemctl', '--user', 'stop', UNIT], timeout=20)
  if running_pids(root):
    run([binary, 'kill', '--path', str(Path(root) / 'shell.qml')], check=False)
  if running_pids(root, 'recovery.qml'):
    run([binary, 'kill', '--path', str(Path(root) / 'recovery.qml')], check=False)
  deadline = time.monotonic() + 12
  while (running_pids(root) or running_pids(root, 'recovery.qml')) and time.monotonic() < deadline:
    time.sleep(0.1)
  if running_pids(root) or running_pids(root, 'recovery.qml'):
    raise RuntimeError('La instancia anterior sigue cerrándose; no se inicia otra encima')


def start(root, executable, binary, *, destination=None):
  destination = destination or unit_path()
  if not destination.is_file() or destination.read_text() != render_unit(executable, root):
    raise RuntimeError('Instala el servicio de recuperación con hyprlarp install antes de usar start')
  environment = current_session()
  folder = private_directory(Path(environment['XDG_RUNTIME_DIR']) / 'hyprlarp')
  descriptor = os.open(folder / 'start.lock', os.O_CREAT | os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600)
  try:
    fcntl.flock(descriptor, fcntl.LOCK_EX)
    # Update only this invocation, never the global user-manager environment.
    previous_signature = os.environ.get('HYPRLAND_INSTANCE_SIGNATURE')
    os.environ['HYPRLAND_INSTANCE_SIGNATURE'] = environment['HYPRLAND_INSTANCE_SIGNATURE']
    if service_running(root, destination):
      result = run(['systemctl', '--user', 'show', UNIT, '-p', 'MainPID', '--value'])
      pid = result.stdout.strip()
      if pid.isdecimal() and pid != '0':
        try:
          entries = (Path('/proc') / pid / 'environ').read_bytes().split(b'\0')
          other = dict(entry.split(b'=', 1) for entry in entries if b'=' in entry).get(b'HYPRLAND_INSTANCE_SIGNATURE', b'').decode()
          if other and other != environment['HYPRLAND_INSTANCE_SIGNATURE']:
            raise RuntimeError('HyprLarp ya está supervisado en otra sesión; ciérrala antes de cambiarlo de pantalla')
        except FileNotFoundError:
          pass
    if service_running(root, destination) and healthy(root, binary):
      return
    stop(root, binary, destination=destination)
    lines = []
    for name in sorted(ENVIRONMENT):
      if name not in environment:
        continue
      value = environment[name]
      if any(ord(char) < 32 for char in value):
        raise ValueError('Variable de sesión inválida: ' + name)
      lines.append(name + '="' + value.replace('\\', '\\\\').replace('"', '\\"').replace('`', '\\`').replace('$', '\\$') + '"')
    from .service import atomic_text
    atomic_text(folder / 'session.env', '\n'.join(lines) + '\n')
    run(['systemctl', '--user', 'daemon-reload'])
    run(['systemctl', '--user', 'reset-failed', UNIT], check=False)
    run(['systemctl', '--user', 'start', UNIT], timeout=65)
    wait_ready(root, binary)
  finally:
    if 'previous_signature' in locals():
      if previous_signature is None:
        os.environ.pop('HYPRLAND_INSTANCE_SIGNATURE', None)
      else:
        os.environ['HYPRLAND_INSTANCE_SIGNATURE'] = previous_signature
    os.close(descriptor)
