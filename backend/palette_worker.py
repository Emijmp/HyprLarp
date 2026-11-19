#!/usr/bin/env python3
"""Short-lived, resource-limited image decoder. Never imported by the shell."""

from collections import Counter
import json
import os
from pathlib import Path
import re
import resource
import stat
import sys

MEMORY_LIMIT = 384 * 1024 * 1024
HEX = re.compile(r'#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})(?![0-9a-fA-F])')


def analyze(path_value, expected):
  path = Path(path_value)
  descriptor = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC | os.O_NOFOLLOW)
  with os.fdopen(descriptor, 'rb') as source:
    metadata = os.fstat(source.fileno())
    if not stat.S_ISREG(metadata.st_mode):
      raise ValueError('El fondo seleccionado no es un archivo local normal')
    identity = [metadata.st_dev, metadata.st_ino, metadata.st_size, metadata.st_mtime_ns]
    if identity != expected:
      raise ValueError('El fondo cambió durante el análisis; vuelve a extraer sus colores')
    if path.suffix.lower() == '.svg':
      maximum = 1024 * 1024
      data = source.read(maximum + 1)
      if len(data) > maximum:
        raise ValueError('El SVG supera el límite de 1 MiB')
      candidates = []
      for color in HEX.findall(data.decode('utf-8', errors='replace')):
        if len(color) == 4:
          color = '#' + ''.join(character * 2 for character in color[1:])
        candidates.append(color.lower())
      colors = [color for color, _ in Counter(candidates).most_common(6)]
      if not colors:
        raise ValueError('No se encontraron colores hexadecimales en el fondo')
      return colors
    if path.suffix.lower() not in {'.png', '.jpg', '.jpeg', '.webp', '.bmp'}:
      raise ValueError('Usa un fondo PNG, JPEG, WebP, BMP o SVG')
    if metadata.st_size > 64 * 1024 * 1024:
      raise ValueError('La imagen supera el límite de 64 MiB')
    try:
      from PIL import Image, UnidentifiedImageError
    except ImportError as error:
      raise RuntimeError('Para extraer colores de este formato se necesita Pillow') from error
    Image.MAX_IMAGE_PIXELS = 24_000_000
    try:
      with Image.open(source) as image:
        width, height = image.size
        if width < 1 or height < 1 or width * height > 24_000_000:
          raise ValueError('La imagen supera el límite de 24 megapíxeles')
        image.thumbnail((96, 96), Image.Resampling.BILINEAR)
        with image.convert('RGB') as reduced:
          with reduced.quantize(colors=8, method=Image.Quantize.MEDIANCUT) as quantized:
            palette = quantized.getpalette() or []
            counts = quantized.getcolors(96 * 96) or []
            colors = []
            for _, index in sorted(counts, reverse=True):
              offset = index * 3
              if offset + 2 < len(palette):
                red, green, blue = palette[offset:offset + 3]
                colors.append(f'#{red:02x}{green:02x}{blue:02x}')
            return colors[:6]
    except (UnidentifiedImageError, Image.DecompressionBombError) as error:
      raise ValueError('El formato del fondo no se puede analizar o supera el límite de 24 megapíxeles') from error


def main():
  resource.setrlimit(resource.RLIMIT_AS, (MEMORY_LIMIT, MEMORY_LIMIT))
  resource.setrlimit(resource.RLIMIT_CPU, (3, 3))
  resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
  try:
    if len(sys.argv) != 3:
      raise ValueError('Petición de análisis inválida')
    colors = analyze(sys.argv[1], json.loads(sys.argv[2]))
    result = {'colors': colors}
  except MemoryError:
    result = {'error': 'La imagen requiere demasiada memoria; prueba una imagen más pequeña'}
  except (OSError, ValueError, RuntimeError) as error:
    result = {'error': str(error)[:240]}
  print(json.dumps(result), flush=True)


if __name__ == '__main__':
  main()
