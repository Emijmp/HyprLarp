#!/usr/bin/env python3
"""Read public login metadata and the appearance installed by the sync helper."""

import configparser
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import shlex
import shutil
import socket
import stat
import sys
import time
import tomllib

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.version import VERSION

PREFERENCES = Path('/var/lib/hyprlarp-greeter/preferences/layout.json')
FALLBACK = {
  'background': '#000000', 'surface': '#000000', 'raised': '#101010', 'border': '#ffffff',
  'text': '#ffffff', 'muted': '#a0a0a0', 'accent': '#ffffff', 'onAccent': '#000000', 'danger': '#ffffff',
}


def read_toml(path):
  try:
    return tomllib.loads(path.read_text())
  except FileNotFoundError:
    return {}


def session_entry(path):
  parser = configparser.ConfigParser(interpolation=None, strict=False)
  parser.read_string(path.read_text())
  entry = parser['Desktop Entry']
  if entry.get('Type', 'Application') != 'Application' or entry.getboolean('Hidden', False) or entry.getboolean('NoDisplay', False):
    return None
  executable = entry.get('TryExec', '')
  if executable and not shutil.which(executable):
    return None
  name = entry.get('Name', path.stem)
  arguments = []
  for word in shlex.split(entry.get('Exec', '')):
    if word == '%i':
      if entry.get('Icon'):
        arguments.extend(['--icon', entry['Icon']])
      continue
    word = word.replace('%%', '\0').replace('%c', name).replace('%k', str(path))
    word = re.sub(r'%[fFuUdDnNvm]', '', word).replace('\0', '%')
    if word:
      arguments.append(word)
  if not arguments:
    return None
  desktops = ':'.join(part for part in entry.get('DesktopNames', '').split(';') if part)
  environment = ['XDG_SESSION_TYPE=wayland']
  if desktops:
    environment.extend(['XDG_CURRENT_DESKTOP=' + desktops, 'XDG_SESSION_DESKTOP=' + desktops])
  return {'id': path.stem, 'name': name, 'command': arguments, 'environment': environment}


def sessions(directories=None):
  directories = directories or [Path('/usr/local/share/wayland-sessions'), Path('/usr/share/wayland-sessions')]
  result = {}
  for folder in directories:
    if not folder.is_dir():
      continue
    for path in sorted(folder.glob('*.desktop')):
      if path.stem in result:
        continue
      try:
        entry = session_entry(path)
        if entry:
          result[path.stem] = entry
      except (OSError, ValueError, KeyError, configparser.Error):
        continue
  return sorted(result.values(), key=lambda entry: entry['name'].casefold())


def users():
  return [{'name': account.pw_name, 'label': account.pw_gecos.split(',')[0] or account.pw_name}
    for account in sorted(pwd.getpwall(), key=lambda account: account.pw_name)
    if 1000 <= account.pw_uid < 65534 and Path(account.pw_shell).name not in {'nologin', 'false'}]


def appearance(sync):
  value = sync.get('appearance', {})
  palette = value.get('palette', {})
  roles = {'background': 'shadow', 'surface': 'surface', 'raised': 'surface_variant', 'border': 'outline',
    'text': 'on_surface', 'muted': 'on_surface_variant', 'accent': 'primary', 'onAccent': 'on_primary', 'danger': 'error'}
  result = {**FALLBACK}
  for target, source in roles.items():
    color = palette.get(source, '')
    if isinstance(color, str) and re.fullmatch(r'#[0-9a-fA-F]{6}', color):
      result[target] = color
  result['font'] = value.get('font_family') or 'Inter'
  scale = value.get('corner_radius_scale', 0)
  result['radius'] = max(0, min(8, float(scale) * 12))
  wallpaper = value.get('wallpaper', {})
  path = wallpaper.get('path', '')
  result['wallpaper'] = ''
  result['fill'] = wallpaper.get('fill_mode', 'crop')
  if path.startswith('color:') and re.fullmatch(r'#[0-9a-fA-F]{6}', path[6:]):
    result['background'] = path[6:]
  elif path and Path(path).is_file():
    source = Path(path)
    metadata = source.stat()
    result['wallpaper'] = source.as_uri() + '?revision=' + str(metadata.st_mtime_ns) + '-' + str(metadata.st_ino)
  return result


def read_layout(path):
  """Preferences are untrusted metadata and can only select one of two layouts."""
  try:
    descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, 'rb') as source:
      metadata = os.fstat(source.fileno())
      if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > 1024:
        return 'sidebar'
      data = json.loads(source.read(1025))
    value = data.get('layout') if isinstance(data, dict) else None
    return value if isinstance(value, str) and value in {'sidebar', 'centered'} else 'sidebar'
  except (OSError, ValueError):
    return 'sidebar'


def read_accessibility(path):
  result = {'textScale': 1, 'largeTargets': False, 'reducedMotion': False}
  try:
    descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, 'rb') as source:
      metadata = os.fstat(source.fileno())
      if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > 1024:
        return result
      value = json.loads(source.read(1025)).get('accessibility', {})
    if isinstance(value, dict):
      scale = value.get('textScale', 1)
      if type(scale) in {int, float} and 1 <= scale <= 2:
        result['textScale'] = scale
      for key in ['largeTargets', 'reducedMotion']:
        result[key] = value.get(key) is True
  except (OSError, ValueError, TypeError, AttributeError):
    pass
  return result


def keyboard_layout(configuration, environment=None, system=Path('/etc/default/keyboard')):
  environment = os.environ if environment is None else environment
  layout = configuration.get('keyboard', {}).get('layout') or environment.get('XKB_DEFAULT_LAYOUT', '')
  if not layout:
    try:
      for line in system.read_text().splitlines():
        words = shlex.split(line, comments=True)
        if words and words[0].startswith('XKBLAYOUT='):
          layout = words[0].split('=', 1)[1]
          break
    except (OSError, ValueError):
      pass
  return layout.upper().replace(',', ' / ') if isinstance(layout, str) and re.fullmatch(r'[a-zA-Z0-9_,+-]{1,128}', layout) else 'Predeterminado'


def keyboard_status(state, leds=Path('/sys/class/leds')):
  values = []
  for source in sorted(leds.glob('*::capslock'))[:32]:
    try:
      value = (source / 'brightness').read_text().strip()
      if value in {'0', '1'}:
        values.append(value == '1')
    except OSError:
      continue
  return {'capsLock': any(values) if values else None,
    'layout': keyboard_layout(read_toml(state / 'greeter.toml'))}


def watch_keyboard(state):
  # Only LED state is read. No input device, typed key or password is collected.
  leds = Path('/sys/class/leds')
  if os.environ.get('HYPRLARP_GREETER_PREVIEW') == '1' and os.environ.get('HYPRLARP_GREETER_TEST') == '1':
    leds = Path(os.environ.get('HYPRLARP_GREETER_TEST_LEDS', leds))
  previous = None
  while True:
    try:
      current = keyboard_status(state, leds)
      if current != previous:
        print(json.dumps(current), flush=True)
        previous = current
      time.sleep(.5)
    except (BrokenPipeError, KeyboardInterrupt):
      return


def load(state, preferences=None):
  configuration = read_toml(state / 'greeter.toml')
  synced = read_toml(state / 'sync.toml')
  entries = sessions()
  selected = configuration.get('session', {}).get('default') or synced.get('session', {}).get('last', '')
  selected = str(selected).casefold()
  default_session = next((entry['id'] for entry in entries if selected in {entry['id'].casefold(), entry['name'].casefold()}), '')
  look = appearance(synced)
  preferences = preferences or Path(os.environ.get('HYPRLARP_GREETER_PREFERENCES', PREFERENCES))
  look['layout'] = read_layout(preferences)
  look.update(read_accessibility(preferences))
  return {'version': VERSION, 'appearance': look, 'users': users(), 'sessions': entries,
    'default_user': configuration.get('user', {}).get('default', ''), 'default_session': default_session,
    'hostname': socket.gethostname(), 'revision': hashlib.sha256(json.dumps(look, sort_keys=True).encode()).hexdigest()}


if __name__ == '__main__':
  if '--version' in sys.argv:
    print('HyprLarp Greeter ' + VERSION)
    raise SystemExit(0)
  state = Path(os.environ.get('HYPRLARP_GREETER_STATE_DIR', '/var/lib/noctalia-greeter'))
  try:
    if '--keyboard-watch' in sys.argv:
      watch_keyboard(state)
    else:
      print(json.dumps(load(state), ensure_ascii=False))
  except (OSError, ValueError, TypeError, tomllib.TOMLDecodeError) as error:
    print(json.dumps({'error': str(error)}, ensure_ascii=False))
    raise SystemExit(1)
