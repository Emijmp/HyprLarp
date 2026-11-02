"""Local wallpaper paths and a bounded, deduplicated image catalogue."""

import os
from pathlib import Path
from urllib.parse import unquote, urlsplit

EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".svg", ".bmp"}


def local_path(value):
  if value.startswith("file:"):
    url = urlsplit(value)
    if url.netloc not in {"", "localhost"}:
      raise ValueError("Elige una carpeta o imagen local")
    value = unquote(url.path)
  if "\0" in value or "\n" in value or "\r" in value:
    raise ValueError("Ruta inválida")
  return Path(os.path.expandvars(value) if value.startswith("$") else value).expanduser().resolve()


def catalogue(directory, builtin, default, limit=200):
  folder = local_path(directory) if directory else default.resolve()
  images, seen, error, truncated = [], set(), "", False
  for location in (folder, builtin.resolve()):
    try:
      if not location.is_dir():
        if location == folder:
          error = "No existe la carpeta. Elige otra o escribe una ruta válida."
        continue
      for candidate in sorted(location.iterdir(), key=lambda entry: entry.name.casefold()):
        if candidate.suffix.lower() not in EXTENSIONS or not candidate.is_file():
          continue
        path = candidate.resolve()
        if path in seen:
          continue
        seen.add(path)
        if len(images) >= limit:
          truncated = True
          break
        images.append({"name": candidate.stem, "path": str(path), "url": path.as_uri()})
    except OSError:
      if location == folder:
        error = "No se pudo leer la carpeta. Comprueba sus permisos."
  browse = folder
  while not browse.is_dir() and browse != browse.parent:
    browse = browse.parent
  return images, {"directory": str(folder), "browseUrl": browse.as_uri(), "error": error,
    "count": len(images), "truncated": truncated}
