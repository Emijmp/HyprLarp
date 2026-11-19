"""Resolve the local scheduled theme without changing persisted preferences."""

from datetime import datetime
import math
import re


def luminance(color):
  channels = [int(color[offset:offset + 2], 16) / 255 for offset in (1, 3, 5)]
  return sum((value / 12.92 if value <= .04045 else ((value + .055) / 1.055) ** 2.4) * weight
    for value, weight in zip(channels, (.2126, .7152, .0722)))


def safe_accent(color, backgrounds, ratio=4.5):
  """Match the shell's black/white mixing and fallback for unusual palettes."""
  color = color.lower() if isinstance(color, str) and re.fullmatch(r'#[0-9a-fA-F]{6}', color) else '#ffffff'
  surfaces = [luminance(value) for value in backgrounds if isinstance(value, str) and re.fullmatch(r'#[0-9a-fA-F]{6}', value)]
  if not surfaces:
    return color
  def score(value):
    light = luminance(value)
    return min((max(light, surface) + .05) / (min(light, surface) + .05) for surface in surfaces)
  if score(color) >= ratio:
    return color
  channels = [int(color[offset:offset + 2], 16) for offset in (1, 3, 5)]
  def mix(end, amount):
    return '#' + ''.join(f'{math.floor(value + (end - value) * amount + .5):02x}' for value in channels)
  best, best_score, closest = color, score(color), math.inf
  for end in (0, 255):
    edge = mix(end, 1)
    edge_score = score(edge)
    if closest == math.inf and edge_score > best_score:
      best, best_score = edge, edge_score
    if edge_score < ratio:
      continue
    low, high = 0, 1
    for _ in range(20):
      middle = (low + high) / 2
      if score(mix(end, middle)) >= ratio:
        high = middle
      else:
        low = middle
    candidate = mix(end, high)
    distance = sum((value - int(candidate[1 + index * 2:3 + index * 2], 16)) ** 2 for index, value in enumerate(channels))
    if distance < closest:
      best, closest = candidate, distance
  if closest != math.inf:
    return best
  for channel in range(256):
    candidate = '#' + f'{channel:02x}' * 3
    candidate_score = score(candidate)
    if candidate_score > best_score:
      best, best_score = candidate, candidate_score
  return best


def effective_name(settings, *, now=None):
  manual = settings.get('theme', 'amoled')
  if not settings.get('themeScheduleEnabled', False):
    return manual
  day, night = settings.get('themeDayStart', '07:00'), settings.get('themeNightStart', '19:00')
  if any(not isinstance(value, str) or not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', value) for value in (day, night)):
    return manual
  current = now if now is not None else datetime.now()
  minute = current.hour * 60 + current.minute
  start = int(day[:2]) * 60 + int(day[3:])
  end = int(night[:2]) * 60 + int(night[3:])
  daytime = start <= minute < end if start <= end else minute >= start or minute < end
  return settings.get('themeDay', 'paper') if daytime else settings.get('themeNight', 'amoled')


def resolve(settings, palettes, *, now=None):
  """Return name, a new palette and the same effective accent used by Theme.qml."""
  name = effective_name(settings, now=now)
  base = palettes['amoled']
  selected = settings.get('customPalette', {}) if name == 'custom' else palettes.get(name, base)
  palette = {**base, **selected}
  if name == 'custom' or (settings.get('themeScheduleEnabled') and name != settings.get('theme', 'amoled')):
    accent = palette['accent']
  else:
    accent = settings.get('accent') or palette['accent']
  return name, palette, safe_accent(accent, [palette.get(role) for role in ('surface', 'raised', 'moduleSurface')])
