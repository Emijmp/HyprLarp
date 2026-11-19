"""On-demand local palette extraction, isolated from the long-lived backend."""

from collections import OrderedDict
import json
from pathlib import Path
import re
import stat
import sys
import threading

try:
  from .safety import bounded_process
except ImportError:
  from safety import bounded_process

SUFFIXES = {'.png', '.jpg', '.jpeg', '.webp', '.bmp', '.svg'}
COLOR = re.compile(r'#[0-9a-f]{6}')
CACHE_LIMIT = 8
WORKER_TIMEOUT = 5


def _source(path_value):
  if not isinstance(path_value, str) or not path_value or len(path_value) > 4096 or '\0' in path_value:
    raise ValueError('Selecciona un fondo local antes de extraer sus colores')
  try:
    path = Path(path_value).expanduser().resolve(strict=True)
    metadata = path.stat()
  except (OSError, RuntimeError) as error:
    raise ValueError('El fondo seleccionado ya no está disponible') from error
  if not stat.S_ISREG(metadata.st_mode):
    raise ValueError('El fondo seleccionado no es un archivo local normal')
  if path.suffix.lower() not in SUFFIXES:
    raise ValueError('Usa un fondo PNG, JPEG, WebP, BMP o SVG')
  limit = 1024 * 1024 if path.suffix.lower() == '.svg' else 64 * 1024 * 1024
  if metadata.st_size > limit:
    raise ValueError('El SVG supera el límite de 1 MiB' if path.suffix.lower() == '.svg' else 'La imagen supera el límite de 64 MiB')
  identity = [metadata.st_dev, metadata.st_ino, metadata.st_size, metadata.st_mtime_ns]
  return path, identity


class PaletteExtractor:
  """One active decoder and a small LRU keyed by the source's file identity."""
  def __init__(self, *, runner=None):
    self.runner = runner or bounded_process
    self.cache = OrderedDict()
    self.lock = threading.Lock()
    self.work = threading.Lock()
    self.closed = False

  def close(self):
    # Service shutdown also terminates tracked children through stop_processes.
    with self.lock:
      self.closed = True
      self.cache.clear()

  def _cached(self, key):
    with self.lock:
      if self.closed:
        raise RuntimeError('El servicio se está cerrando')
      if key in self.cache:
        colors = self.cache.pop(key)
        self.cache[key] = colors
        return list(colors)
    return None

  def extract(self, path_value):
    path, identity = _source(path_value)
    key = (str(path), *identity)
    colors = self._cached(key)
    if colors is not None:
      return {'path': str(path), 'name': path.name, 'colors': colors}
    if not self.work.acquire(blocking=False):
      raise RuntimeError('Ya se están extrayendo colores; espera a que termine el análisis')
    try:
      colors = self._cached(key)
      if colors is None:
        try:
          output = self.runner([sys.executable, '-I', str(Path(__file__).with_name('palette_worker.py')),
            str(path), json.dumps(identity)], timeout=WORKER_TIMEOUT, limit=4096)
        except (OSError, RuntimeError, ValueError) as error:
          raise RuntimeError('No se pudo analizar el fondo dentro de los límites de tiempo o recursos; prueba una imagen más pequeña') from error
        try:
          result = json.loads(output)
        except (ValueError, UnicodeError) as error:
          raise RuntimeError('El analizador del fondo no devolvió una paleta válida') from error
        if isinstance(result, dict) and isinstance(result.get('error'), str):
          raise ValueError(result['error'][:240])
        colors = result.get('colors') if isinstance(result, dict) else None
        if not isinstance(colors, list) or not 1 <= len(colors) <= 6 or any(not isinstance(color, str) or not COLOR.fullmatch(color) for color in colors):
          raise RuntimeError('El analizador del fondo no devolvió una paleta válida')
        _, after = _source(str(path))
        if after != identity:
          raise ValueError('El fondo cambió durante el análisis; vuelve a extraer sus colores')
        with self.lock:
          if self.closed:
            raise RuntimeError('El servicio se está cerrando')
          # Drop older versions of the same path instead of filling the cache
          # with repeated edits of a wallpaper.
          for previous in [entry for entry in self.cache if entry[0] == str(path)]:
            del self.cache[previous]
          self.cache[key] = tuple(colors)
          while len(self.cache) > CACHE_LIMIT:
            self.cache.popitem(last=False)
      return {'path': str(path), 'name': path.name, 'colors': list(colors)}
    finally:
      self.work.release()


_default = PaletteExtractor()


def extract(path_value):
  """Compatibility API for callers that do not own a service instance."""
  return _default.extract(path_value)
