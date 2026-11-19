"""Export HyprLarp appearance through Noctalia Greeter's constrained sync API."""

import argparse
import configparser
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tempfile
from urllib.parse import unquote, urlsplit

try:
  from .theme_context import effective_name, resolve as resolve_theme
except ImportError:
  from theme_context import effective_name, resolve as resolve_theme

ROOT = Path(__file__).resolve().parents[1]
HELPER = Path('/usr/bin/noctalia-greeter-apply-appearance')
GREETER_STATE = Path('/var/lib/noctalia-greeter')
GREETER_UI = Path('/usr/local/share/hyprlarp-greeter')
PREFERENCES = Path('/var/lib/hyprlarp-greeter/preferences/layout.json')
IMAGE_LIMIT = 64 * 1024 * 1024
IMAGES = {'.png', '.jpg', '.jpeg', '.webp', '.bmp', '.jxl'}
DEFAULT_GREETER = {
  'appearance': {'scheme': 'Synced', 'hide_logo': True, 'scheme_selector_position': 'hidden'},
  'clock': {'enabled': True, 'position': 'bottom-left', 'time_format': '%H:%M',
    'date_format': '%A, %d/%m/%Y'},
}


def toml_value(value):
  if isinstance(value, str):
    return json.dumps(value, ensure_ascii=False)
  if isinstance(value, bool):
    return 'true' if value else 'false'
  if isinstance(value, int):
    return str(value)
  if isinstance(value, float) and math.isfinite(value):
    return repr(value)
  if isinstance(value, list) and not any(isinstance(item, dict) for item in value):
    return '[' + ', '.join(toml_value(item) for item in value) + ']'
  raise ValueError('Valor TOML no admitido: ' + type(value).__name__)


def dump_toml(data):
  """Preserve configuration values without depending on a third-party TOML writer."""
  lines = []

  def key(value):
    return value if re.fullmatch(r'[A-Za-z0-9_-]+', value) else toml_value(value)

  def table(value, path=(), array=False):
    if path:
      name = '.'.join(key(part) for part in path)
      lines.extend(['', ('[[' + name + ']]') if array else ('[' + name + ']')])
    for name, item in value.items():
      if not isinstance(item, dict) and not (isinstance(item, list) and item and isinstance(item[0], dict)):
        lines.append(key(name) + ' = ' + toml_value(item))
    for name, item in value.items():
      if isinstance(item, dict):
        table(item, (*path, name))
      elif isinstance(item, list) and item and isinstance(item[0], dict):
        for row in item:
          if not isinstance(row, dict):
            raise ValueError('Array TOML mixto no admitido')
          table(row, (*path, name), array=True)

  table(data)
  return '\n'.join(lines).lstrip() + '\n'


def read_regular(path, limit=IMAGE_LIMIT):
  descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NONBLOCK)
  with os.fdopen(descriptor, 'rb') as source:
    metadata = os.fstat(source.fileno())
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > limit:
      raise ValueError('El archivo debe ser regular y respetar el límite: ' + str(path))
    data = source.read(limit + 1)
    if len(data) > limit:
      raise ValueError('Archivo demasiado grande: ' + str(path))
    return data


def color(value):
  if not isinstance(value, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', value):
    raise ValueError('Color inválido en la paleta de HyprLarp')
  return value.lower()


def luminance(value):
  channels = [int(color(value)[i:i + 2], 16) / 255 for i in (1, 3, 5)]
  linear = [part / 12.92 if part <= 0.04045 else ((part + 0.055) / 1.055) ** 2.4 for part in channels]
  return sum(part * weight for part, weight in zip(linear, (0.2126, 0.7152, 0.0722)))


def contrast_text(value):
  return '#000000' if luminance(value) > 0.179 else '#ffffff'


def accessible_palette(settings, palette):
  if not settings.get('accessibilityHighContrast', False):
    return palette
  light = luminance(palette['background']) > .5
  foreground, background = ('#000000', '#ffffff') if light else ('#ffffff', '#000000')
  return {**palette, 'background': background, 'surface': background,
    'raised': '#f2f2f2' if light else '#101010', 'moduleSurface': background,
    'text': foreground, 'muted': '#333333' if light else '#dedede', 'accent': foreground,
    'border': foreground, 'separator': '#555555' if light else '#bfbfbf', 'danger': foreground}


def accessibility(settings):
  scale = settings.get('accessibilityTextScale', 1)
  if isinstance(scale, bool) or not isinstance(scale, (int, float)) or not 1 <= scale <= 2:
    raise ValueError('Escala de accesibilidad inválida')
  return {'textScale': scale, 'largeTargets': settings.get('accessibilityLargeTargets') is True,
    'reducedMotion': settings.get('accessibilityReducedMotion') is True}


def layout(settings):
  value = settings.get('greeterLayout', 'sidebar')
  if not isinstance(value, str) or value not in {'sidebar', 'centered'}:
    raise ValueError('Diseño de inicio de sesión desconocido')
  return value


def appearance(settings, palettes, *, now=None):
  _, selected, accent = resolve_theme(settings, palettes, now=now)
  palette = accessible_palette(settings, selected)
  accent = color(palette['accent'] if settings.get('accessibilityHighContrast') else accent)
  surface, text = color(palette['surface']), color(palette['text'])
  error = color(palette['danger'])
  roles = {
    'primary': accent, 'on_primary': contrast_text(accent),
    'secondary': accent, 'on_secondary': contrast_text(accent),
    'tertiary': accent, 'on_tertiary': contrast_text(accent),
    'error': error, 'on_error': contrast_text(error),
    'surface': surface, 'on_surface': text,
    'surface_variant': color(palette['raised']), 'on_surface_variant': color(palette['muted']),
    'outline': color(palette['border']), 'shadow': color(palette['background']),
    'hover': accent, 'on_hover': contrast_text(accent),
  }
  radii = settings.get('cornerRadii', {})
  radius = radii.get('panel', radii.get('panels', settings.get('radius', 0)))
  if isinstance(radius, bool) or not isinstance(radius, (int, float)) or not math.isfinite(radius):
    raise ValueError('Redondez inválida')
  font = settings.get('font') or 'Inter'
  if not isinstance(font, str) or len(font) > 256 or any(ord(char) < 32 for char in font):
    raise ValueError('Fuente inválida')
  return {'scheme': 'Synced', 'theme_mode': 'light' if luminance(surface) > 0.179 else 'dark',
    'corner_radius_scale': max(0, min(8, radius)) / 12, 'font_family': font, 'palette': roles}


def local_path(value):
  if value.startswith('file:'):
    parsed = urlsplit(value)
    if parsed.netloc not in {'', 'localhost'}:
      raise ValueError('El fondo debe ser un archivo local')
    value = unquote(parsed.path)
  if not value or any(ord(char) < 32 for char in value):
    raise ValueError('Ruta de fondo inválida')
  return Path(os.path.expandvars(value)).expanduser().resolve()


def wallpaper(settings, waypaper):
  if settings.get('wallpaperProvider', 'internal') == 'external':
    parser = configparser.ConfigParser(interpolation=None)
    parser.read_string(read_regular(waypaper, 1024 * 1024).decode('utf-8'))
    value = parser.get('Settings', 'wallpaper', fallback='').strip()
    fill = parser.get('Settings', 'fill', fallback='fill').strip()
    return local_path(value), {'fill': 'crop', 'fit': 'fit', 'stretch': 'stretch', 'center': 'center',
      'tile': 'repeat'}.get(fill, 'crop')
  value = settings.get('wallpaper', '')
  return (local_path(value) if value else None), 'crop'


def image_bytes(path):
  suffix = path.suffix.lower()
  if suffix in IMAGES:
    return 'wallpaper' + suffix, read_regular(path)
  # The login screen uses a still image for animated/external wallpapers.
  with tempfile.TemporaryDirectory(prefix='hyprlarp-greeter-frame-') as temporary:
    destination = Path(temporary) / 'wallpaper.png'
    if suffix == '.svg':
      command = ['magick', str(path), '-resize', '3840x2160>', str(destination)]
    elif suffix in {'.gif', '.mp4', '.mkv', '.webm', '.mov', '.avi'}:
      command = ['ffmpeg', '-v', 'error', '-nostdin', '-i', str(path), '-frames:v', '1',
        '-vf', 'scale=w=min(3840\\,iw):h=min(2160\\,ih):force_original_aspect_ratio=decrease', str(destination)]
    else:
      raise ValueError('Formato de fondo no admitido por el greeter: ' + suffix)
    result = subprocess.run(command, capture_output=True, timeout=30)
    if result.returncode:
      raise RuntimeError(result.stderr.decode(errors='replace')[-500:] or 'No se pudo preparar el fondo')
    return 'wallpaper.png', read_regular(destination)


def payload(settings_path, waypaper, palettes_path=None, *, now=None):
  settings = json.loads(read_regular(settings_path, 1024 * 1024))
  palettes = json.loads(read_regular(palettes_path or ROOT / 'config/palettes.json', 1024 * 1024))
  current = now if now is not None else datetime.now()
  look = appearance(settings, palettes, now=current)
  path, fill = wallpaper(settings, waypaper)
  files = {}
  if path is None:
    background = look['palette']['shadow']
    look['wallpaper'] = {'path': 'color:' + background, 'fill_mode': fill, 'fill_color': background}
  else:
    name, contents = image_bytes(path)
    files[name] = contents
    look['wallpaper'] = {'path': str(GREETER_STATE / name), 'fill_mode': fill}
  files['sync.toml'] = dump_toml({'appearance': look}).encode('utf-8')
  return files, {'wallpaper': str(path) if path else '', 'theme': effective_name(settings, now=current),
    'font': look['font_family'], 'corner_radius_scale': look['corner_radius_scale'], 'layout': layout(settings), 'accessibility': accessibility(settings)}


def private_directory(path):
  path = Path(path)
  if path.is_symlink():
    raise ValueError('El directorio privado no puede ser un enlace simbólico')
  path.mkdir(parents=True, exist_ok=True, mode=0o700)
  if path.stat().st_uid != os.getuid():
    raise ValueError('El directorio pertenece a otro usuario')
  path.chmod(0o700)
  return path


def atomic_write(path, data, *, mode=0o600):
  descriptor, temporary = tempfile.mkstemp(prefix='.' + path.name + '-', dir=path.parent)
  try:
    with os.fdopen(descriptor, 'wb') as output:
      os.fchmod(output.fileno(), mode)
      output.write(data)
      output.flush()
      os.fsync(output.fileno())
    os.replace(temporary, path)
  finally:
    Path(temporary).unlink(missing_ok=True)


def sync_layout(value, destination=None, *, accessibility_options=None):
  """Share only an enum with the greeter; appearance helper permissions stay unchanged."""
  value = layout({'greeterLayout': value})
  destination = destination or PREFERENCES
  folder = destination.parent
  if folder.is_symlink() or destination.is_symlink() or folder.stat().st_uid != os.getuid():
    raise ValueError('El directorio de preferencias del greeter debe pertenecer a tu usuario')
  preferences = {'layout': value}
  if accessibility_options is not None:
    preferences['accessibility'] = accessibility_options
  data = (json.dumps(preferences) + '\n').encode()
  try:
    if read_regular(destination, 1024) == data and stat.S_IMODE(destination.stat().st_mode) == 0o640:
      return False
  except FileNotFoundError:
    pass
  # The installer provisions a setgid directory readable by the greeter group.
  atomic_write(destination, data, mode=0o640)
  return True


def export(files, destination):
  destination = private_directory(destination)
  for path in destination.iterdir():
    if path.is_symlink() or not path.is_file() or (path.name != 'sync.toml' and not path.name.startswith('wallpaper')):
      raise ValueError('El destino contiene archivos ajenos: ' + str(path))
  for name, data in files.items():
    atomic_write(destination / name, data)
  for path in destination.iterdir():
    if path.name not in files:
      path.unlink()


def fingerprint(files):
  checksum = hashlib.sha256()
  for name, data in sorted(files.items()):
    checksum.update(name.encode() + b'\0' + hashlib.sha256(data).digest())
  return checksum.hexdigest()


def preview(settings_path, waypaper):
  import pwd
  import tomllib
  configuration = ROOT / 'greeter/shell.qml'
  if not configuration.is_file():
    configuration = GREETER_UI / 'greeter/shell.qml'
  if not configuration.is_file():
    raise ValueError('Instala primero la interfaz del greeter')
  files, information = payload(settings_path, waypaper)
  cache = private_directory(Path(os.environ.get('XDG_CACHE_HOME', Path.home() / '.cache')) / 'hyprlarp/greeter-preview')
  with tempfile.TemporaryDirectory(prefix='preview-', dir=cache) as temporary:
    directory = Path(temporary)
    export(files, directory)
    data = tomllib.loads((directory / 'sync.toml').read_text())
    image = data['appearance']['wallpaper']['path']
    if not image.startswith('color:'):
      data['appearance']['wallpaper']['path'] = str(directory / Path(image).name)
    atomic_write(directory / 'sync.toml', dump_toml(data).encode())
    atomic_write(directory / 'greeter.toml', dump_toml({'user': {'default': pwd.getpwuid(os.getuid()).pw_name}}).encode())
    atomic_write(directory / 'layout.json', (json.dumps({'layout': information['layout'], 'accessibility': information['accessibility']}) + '\n').encode())
    environment = {**os.environ, 'HYPRLARP_GREETER_STATE_DIR': str(directory),
      'HYPRLARP_GREETER_PREFERENCES': str(directory / 'layout.json'),
      'HYPRLARP_GREETER_PREVIEW': '1', 'QT_QUICK_CONTROLS_STYLE': 'Basic'}
    environment.pop('GREETD_SOCK', None)
    environment.pop('HYPRLARP_GREETER_TEST', None)
    subprocess.run(['/usr/bin/quickshell', '--path', str(configuration)], env=environment, check=True)
  return {'status': 'preview-closed'}


def sync(settings_path, waypaper, *, force=False):
  if os.geteuid() == 0:
    raise ValueError('La sincronización se ejecuta como el usuario del escritorio, sin sudo')
  runtime = private_directory(Path('/run/user') / str(os.getuid()))
  state = private_directory(Path(os.environ.get('XDG_STATE_HOME', Path.home() / '.local/state')) / 'hyprlarp-greeter')
  descriptor = os.open(runtime / 'hyprlarp-greeter-sync.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
  try:
    try:
      fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
      return {'status': 'busy'}
    files, information = payload(settings_path, waypaper)
    layout_changed = sync_layout(information['layout'], accessibility_options=information.get('accessibility'))
    digest = fingerprint(files)
    previous = json.loads((state / 'last-sync.json').read_text()) if (state / 'last-sync.json').is_file() else {}
    if not force and previous.get('fingerprint') == digest:
      report = {**previous, **information, 'status': 'synced' if layout_changed else 'unchanged'}
      if layout_changed or previous.get('layout') != information['layout']:
        report['updated'] = datetime.now(timezone.utc).isoformat()
        atomic_write(state / 'last-sync.json', (json.dumps(report, ensure_ascii=False, indent=2) + '\n').encode())
      return report
    supported = subprocess.run([str(HELPER), '--supports', 'secure-sync-v1'], capture_output=True, text=True, timeout=5)
    if supported.returncode or supported.stdout.strip() != 'secure-sync-v1':
      raise RuntimeError('Se requiere Noctalia Greeter con secure-sync-v1 (1.5 o posterior)')
    staging = runtime / 'noctalia-greeter-sync'
    export(files, staging)
    result = subprocess.run(['/usr/bin/pkexec', '--disable-internal-agent', str(HELPER), '--sync', str(staging)],
      capture_output=True, text=True, timeout=35)
    if result.returncode:
      raise RuntimeError((result.stderr or result.stdout).strip()[-1000:] or 'No se pudo sincronizar el greeter')
    report = {**information, 'fingerprint': digest, 'status': 'synced',
      'updated': datetime.now(timezone.utc).isoformat()}
    atomic_write(state / 'last-sync.json', (json.dumps(report, ensure_ascii=False, indent=2) + '\n').encode())
    return report
  finally:
    os.close(descriptor)


def main():
  config = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config'))
  parser = argparse.ArgumentParser(description='Sincroniza el greeter de greetd con HyprLarp')
  parser.add_argument('command', choices=['sync', 'export', 'status', 'preview', 'uninstall'])
  parser.add_argument('--settings', type=Path, default=config / 'hyprlarp/settings.json')
  parser.add_argument('--waypaper', type=Path, default=config / 'waypaper/config.ini')
  parser.add_argument('--output', type=Path, help='Directorio privado de exportación')
  parser.add_argument('--force', action='store_true')
  parser.add_argument('--dry-run', action='store_true', help='Mostrar la retirada del greeter sin modificar archivos')
  args = parser.parse_args()
  if args.dry_run and args.command != 'uninstall':
    parser.error('--dry-run solo se admite con uninstall')
  try:
    if args.command == 'uninstall':
      # The standalone user bridge ships its own lifecycle controller, so this
      # entry point also works after moving the checkout or removing the shell.
      import sys
      sys.path.insert(0, str(ROOT))
      from tools.install_greeter import uninstall_user
      uninstall_user(dry_run=args.dry_run)
      return
    elif args.command == 'export':
      if not args.output:
        parser.error('export requiere --output')
      files, report = payload(args.settings, args.waypaper)
      export(files, args.output)
      report['output'] = str(args.output.resolve())
    elif args.command == 'preview':
      report = preview(args.settings, args.waypaper)
    elif args.command == 'status':
      state = Path(os.environ.get('XDG_STATE_HOME', Path.home() / '.local/state')) / 'hyprlarp-greeter/last-sync.json'
      report = json.loads(state.read_text()) if state.is_file() else {'status': 'not-synced'}
    else:
      report = sync(args.settings, args.waypaper, force=args.force)
    print(json.dumps(report, ensure_ascii=False, indent=2))
  except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
    parser.exit(1, str(error) + '\n')


if __name__ == '__main__':
  main()
