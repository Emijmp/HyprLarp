"""Resolve an installed icon theme once at startup, including plain Wayland sessions."""

import configparser
from itertools import product
import os
from pathlib import Path

ICON_SUFFIXES = tuple("." + "".join(letters) for extension in ("svg", "png", "xpm")
  for letters in product(*[(letter, letter.upper()) for letter in extension]))


def choose_icon_theme(environment: dict) -> str:
  if "QS_ICON_THEME" in environment:
    return environment["QS_ICON_THEME"]
  config = Path(environment.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
  data = Path(environment.get("XDG_DATA_HOME", str(Path.home() / ".local/share")))
  locations = [data / "icons", Path.home() / ".icons"]
  locations += [Path(path) / "icons" for path in environment.get("XDG_DATA_DIRS", "/usr/local/share:/usr/share").split(os.pathsep) if path]
  preferred = []
  for relative, section, key in [("qt6ct/qt6ct.conf", "Appearance", "icon_theme"),
                   ("gtk-3.0/settings.ini", "Settings", "gtk-icon-theme-name"),
                   ("gtk-4.0/settings.ini", "Settings", "gtk-icon-theme-name")]:
    parser = configparser.ConfigParser(interpolation=None)
    try:
      parser.read(config / relative)
      theme = parser.get(section, key, fallback="").strip().strip('"')
      if theme:
        preferred.append(theme)
    except (OSError, configparser.Error):
      continue
  for theme in preferred + ["Papirus-Dark", "Papirus", "breeze-dark", "breeze", "Adwaita", "hicolor"]:
    if any((location / theme / "index.theme").is_file() for location in locations):
      return theme
  return ""


class IconResolver:
  """A cached fallback for Qt platforms without system icon search paths."""
  def __init__(self, environment: dict):
    data = Path(environment.get("XDG_DATA_HOME", str(Path.home() / ".local/share")))
    self.locations = [data / "icons", Path.home() / ".icons"]
    self.locations += [Path(path) / "icons" for path in environment.get("XDG_DATA_DIRS", "/usr/local/share:/usr/share").split(os.pathsep) if path]
    self.pixmaps = [location.parent / "pixmaps" for location in self.locations]
    self.folders = []
    self.cache = {}
    visited = set()
    def visit(theme):
      if not theme or theme in visited:
        return
      visited.add(theme)
      inherited = []
      for location in self.locations:
        folder = location / theme
        parser = configparser.ConfigParser(interpolation=None, strict=False)
        try:
          if not parser.read(folder / "index.theme"):
            continue
          directories = parser.get("Icon Theme", "Directories", fallback="").split(",")
          directories += parser.get("Icon Theme", "ScaledDirectories", fallback="").split(",")
          # App delegates request 24 px; prefer that size, then the closest available.
          directories = [name.strip() for name in directories if name.strip()]
          directories.sort(key=lambda name: (abs(parser.getint(name, "Size", fallback=24) - 24), parser.getint(name, "Scale", fallback=1)))
          self.folders += [folder / name for name in directories]
          inherited += parser.get("Icon Theme", "Inherits", fallback="").split(",")
        except (OSError, ValueError, configparser.Error):
          continue
      for name in inherited:
        visit(name.strip())
    for theme in [choose_icon_theme(environment), "Papirus-Dark", "breeze-dark", "Adwaita", "hicolor"]:
      visit(theme)

  def resolve(self, names: list[str]) -> dict[str, str]:
    absolute = {name for name in names if name.startswith("/") and len(name) <= 4096 and "\0" not in name}
    for name in absolute - self.cache.keys():
      path = Path(name)
      valid = path.suffix.lower() in {".svg", ".png", ".xpm", ".jpg", ".jpeg", ".webp", ".ico"} and path.is_file()
      self.cache[name] = path.as_uri() if valid else ""
    names = {name for name in names if name and len(name) <= 256 and "/" not in name and "\\" not in name and "\0" not in name}
    remaining = names - self.cache.keys()
    # Listing a whole theme is worthwhile for large batches, but a few missing
    # names otherwise walk thousands of unrelated icons in every size/theme.
    # Once only a small tail remains, fixed candidate probes are much cheaper.
    for folder in self.folders + self.pixmaps:
      if not remaining:
        break
      found = {}
      if len(remaining) == 1:
        prefix = str(folder) + os.sep
        for name in remaining:
          candidates = ([name] if name.rpartition(".")[2].lower() in {"svg", "png", "xpm"} else [])
          candidates += [name + suffix for suffix in ICON_SUFFIXES]
          for candidate in candidates:
            path = prefix + candidate
            if os.path.isfile(path):
              found[name] = path
              break
        for name, path in found.items():
          self.cache[name] = Path(path).absolute().as_uri()
        remaining.difference_update(found)
        continue
      try:
        with os.scandir(folder) as entries:
          for entry in entries:
            stem, separator, extension = entry.name.rpartition(".")
            if not separator or extension.lower() not in {"svg", "png", "xpm"}:
              continue
            name = entry.name if entry.name in remaining else stem
            if name in remaining and entry.is_file():
              previous = found.get(name)
              if previous is None or extension.lower() == "svg":
                found[name] = entry.path
      except OSError:
        continue
      for name, path in found.items():
        self.cache[name] = Path(path).absolute().as_uri()
      remaining.difference_update(found)
    self.cache.update({name: "" for name in remaining})
    result = {name: self.cache[name] for name in names | absolute}
    if len(self.cache) > 4096:
      for name in list(self.cache)[:len(self.cache) - 4096]:
        del self.cache[name]
    return result
