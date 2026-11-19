"""Generate native hyprlock widgets from the current HyprLarp appearance."""

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

try:
  from .greeter import wallpaper, accessible_palette, accessibility
  from .theme_context import resolve as resolve_theme
  from .safety import bounded_process, private_directory, read_json, read_regular
except ImportError:
  from greeter import wallpaper, accessible_palette, accessibility
  from theme_context import resolve as resolve_theme
  from safety import bounded_process, private_directory, read_json, read_regular

ROOT = Path(__file__).resolve().parents[1]


def prepare(settings, directory, *, now=None):
  """Cache small tinted artwork and a still wallpaper; failure keeps locking usable."""
  try:
    from .service import atomic_bytes, atomic_json
  except ImportError:
    from service import atomic_bytes, atomic_json
  folder = private_directory(directory / 'lock-assets')
  try:
    previous = read_json(folder / 'metadata.json')
  except (OSError, ValueError):
    previous = {}
  _, selected, accent = resolve_theme(settings, json.loads((ROOT / 'config/palettes.json').read_text()), now=now)
  palette = accessible_palette(settings, selected)
  if settings.get('accessibilityHighContrast'):
    accent = palette['accent']
  svg = read_regular(ROOT / 'assets/hyprlarp.svg').replace(b'#ffffff', accent.encode())
  logo_hash = hashlib.sha256(svg).hexdigest()
  result = {'logo': '', 'wallpaper': '', 'logoHash': logo_hash}
  if previous.get('logoHash') == logo_hash and (folder / 'logo.png').is_file():
    result['logo'] = 'logo.png'
  elif shutil.which('magick'):
    try:
      png = bounded_process(['magick', '-limit', 'thread', '1', '-background', 'none',
        'svg:-', '-resize', '192x192', 'png:-'], content=svg, timeout=2, limit=1024 * 1024)
      atomic_bytes(folder / 'logo.png', png)
      result['logo'] = 'logo.png'
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
      pass
  config = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config'))
  try:
    source, _ = wallpaper(settings, config / 'waypaper/config.ini')
    if source is not None:
      metadata = source.stat()
      stamp = [str(source), metadata.st_mtime_ns, metadata.st_size]
      name = 'wallpaper' + source.suffix.lower()
      if previous.get('source') == stamp and previous.get('wallpaper') and (folder / previous['wallpaper']).is_file():
        result.update(wallpaper=previous['wallpaper'], source=stamp)
      elif source.suffix.lower() in {'.png', '.jpg', '.jpeg', '.webp'}:
        atomic_bytes(folder / name, read_regular(source, 64 * 1024 * 1024))
        result.update(wallpaper=name, source=stamp)
      else:
        if source.suffix.lower() in {'.gif', '.mp4', '.mkv', '.webm', '.mov', '.avi'}:
          command = ['ffmpeg', '-v', 'error', '-nostdin', '-threads', '1', '-i', str(source),
            '-frames:v', '1', '-vf', 'scale=1920:1080:force_original_aspect_ratio=decrease',
            '-f', 'image2pipe', '-vcodec', 'png', '-']
        else:
          command = ['magick', '-limit', 'thread', '1', '-limit', 'memory', '128MiB',
            '-limit', 'map', '128MiB', str(source) + '[0]', '-resize', '3840x2160>', 'png:-']
        data = bounded_process(command, timeout=2, limit=32 * 1024 * 1024)
        atomic_bytes(folder / 'wallpaper.png', data)
        result.update(wallpaper='wallpaper.png', source=stamp)
  except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
    # An unavailable wallpaper or converter must never prevent authentication.
    pass
  atomic_json(folder / 'metadata.json', result)
  return folder, result


def monitors():
  try:
    result = subprocess.run(['hyprctl', '-j', 'monitors'], capture_output=True, text=True, timeout=2)
    value = json.loads(result.stdout)
    return value if result.returncode == 0 and isinstance(value, list) else []
  except (OSError, ValueError, subprocess.SubprocessError):
    return []


def render(settings, palettes, *, outputs=None, asset_path=None, assets=None, now=None):
  _, selected, accent = resolve_theme(settings, palettes, now=now)
  palette = accessible_palette(settings, selected)
  if settings.get('accessibilityHighContrast'):
    accent = palette['accent']
  font = settings.get('font') or 'Inter'
  if len(font) > 256 or any(char in font for char in '\n\r\0$#{}='):
    font = 'Inter'
  centered = settings.get('greeterLayout') == 'centered'
  radius = settings.get('cornerRadii', {}).get('panel', settings.get('radius', 0))
  field_radius = settings.get('cornerRadii', {}).get('field', settings.get('radius', 0))
  colors = {key: palette[key][1:] for key in ('background', 'surface', 'raised', 'text', 'muted', 'border', 'danger')}
  colors['accent'] = accent[1:]
  template = (ROOT / 'config/hyprlock.conf').read_text()
  for key, value in {**colors, 'font': font, 'animations': str(bool(settings.get('animations')) and not settings.get('accessibilityReducedMotion')).lower()}.items():
    template = template.replace('@' + key.upper() + '@', value)
  assets = assets or {}
  path = str(asset_path) if asset_path else ''
  wallpaper_file = assets.get('wallpaper', '')
  logo_file = assets.get('logo', '')
  if path and not re.fullmatch(r'/proc/self/fd/[0-9]+', path):
    raise ValueError('Los recursos del bloqueo requieren un descriptor de directorio')
  background = path + '/' + wallpaper_file if path and re.fullmatch(r'wallpaper\.(png|jpe?g|webp)', wallpaper_file) else ''
  template = template.replace('@WALLPAPER@', background)
  logo = path + '/logo.png' if path and logo_file == 'logo.png' else ''
  widgets = []

  def widget(kind, output, **values):
    widgets.append(kind + ' {\n  monitor = ' + output + '\n' + ''.join('  ' + key + ' = ' + str(value) + '\n' for key, value in values.items()) + '}\n')

  displays = outputs or [{'name': '', 'width': 1280, 'height': 720, 'scale': 1}]
  for display in displays:
    name = display.get('name', '')
    if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9_.:-]*', name):
      continue
    scale = max(0.5, float(display.get('scale', 1)))
    width, height = float(display.get('width', 1280)), float(display.get('height', 720))
    if display.get('transform', 0) in {1, 3, 5, 7}:
      width, height = height, width
    width, height = max(320, round(width / scale)), max(240, round(height / scale))
    # Keep the native authentication form on screen; it has no scroll surface.
    ui_scale = min(accessibility(settings)['textScale'], max(1, (height - 48) / 420), max(1, (width - 48) / 448))
    width, height = width / ui_scale, height / ui_scale
    scale *= ui_scale
    padding = 24 if width < 900 else 36
    panel_width = min(448, width - padding * 2) if centered else min(350, width * .53) if width < 800 else min(440, width * .34)
    panel_width = round(panel_width)
    panel_height = min(420, height - padding * 2) if centered else height
    x = round((width - panel_width) / 2) if centered else 0
    y = round((height - panel_height) / 2) if centered else 0
    inset = min(padding, round(panel_width * .1))
    content_width = max(140, panel_width - inset * 2)
    form_y = y + round(panel_height * .53) if centered else round(height * .51)

    def extent(w, h):
      return f'{w / width * 100:.6f}%, {h / height * 100:.6f}%'

    def position(px, py):
      # hyprlock lays widgets out in framebuffer pixels, not Hyprland logical
      # coordinates. Percentages keep geometry aligned at fractional scales.
      return {'position': extent(px, -py), 'halign': 'left', 'valign': 'top', 'zindex': 3}

    def label(text, px, py, size=11, color='$foreground'):
      widget('label', name, text=text, color=color, font_size=max(8, round(size * scale)), font_family='$font', **position(px, py))

    if centered:
      widget('shape', name, size='100%, 100%', color='rgba(' + colors['background'] + '33)', rounding=0, zindex=0)
    panel_position = {'position': '0, 0', 'halign': 'center', 'valign': 'center'} if centered else position(x, y)
    widget('shape', name, size=extent(panel_width, panel_height), color='$surface',
      rounding=round(radius * scale) if centered else 0, border_size=max(1, round(scale)) if centered else 0,
      border_color='$border', **{**panel_position, 'zindex': 1})
    if not centered:
      widget('shape', name, size=extent(1, height), color='$border', rounding=0,
        **{**position(panel_width - 1, 0), 'zindex': 2})
    if logo:
      widget('image', name, path=logo, size=round(38 * scale), rounding=0, border_size=0, **position(x + inset, y + padding))
    label('HYPRLARP', x + inset + (51 if logo else 0), y + padding + 2, 11)
    label('Sesión bloqueada', x + inset + (51 if logo else 0), y + padding + 24, 9, '$muted')
    label('Desbloquear', x + inset, form_y - 94, 23)
    label('$USER', x + inset, form_y - 47, 12, '$muted')
    widget('input-field', name, size=extent(content_width, 46), outline_thickness=max(1, round(scale)),
      inner_color='$raised', outer_color='$border', font_color='$foreground', font_family='$font',
      check_color='$accent', fail_color='$danger', capslock_color='$accent',
      placeholder_text='Contraseña', check_text='Verificando…', fail_text='Inténtalo de nuevo · $ATTEMPTS',
      fade_on_empty='false', rounding=round(field_radius * scale), dots_size=.2, dots_spacing=.3,
      **position(x + inset, form_y))
    label('Enter para desbloquear', x + inset, form_y + 66, 9, '$muted')
    label('TECLADO · $LAYOUT', x + inset, y + panel_height - padding - 13, 9, '$muted')
    if centered:
      widget('label', name, text='$TIME', color='$foreground', font_size=round(30 * scale), font_family='$font',
        position=extent(-padding, padding), halign='right', valign='bottom', zindex=3)
    else:
      label('$TIME', x + inset, height - padding - 103, 32)
  return template + '\n' + '\n'.join(widgets)
