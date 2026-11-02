"""On-demand profile/theme storage and launcher history; no background jobs."""

import copy
import json
from pathlib import Path
import threading
import time
from urllib.parse import unquote, urlparse


class Features:
  def __init__(self, service, api):
    self.s, self.api = service, api
    self.lock = threading.RLock()
    self.library = self.read("library.json", {"profiles": {}, "themes": {}})
    if not isinstance(self.library, dict) or not all(isinstance(self.library.get(key), dict) for key in ("profiles", "themes")):
      self.library = {"profiles": {}, "themes": {}}
    self.launcher = self.read("launcher.json", {"favorites": [], "recent": []})
    if not isinstance(self.launcher, dict) or not isinstance(self.launcher.get("favorites"), list) or not isinstance(self.launcher.get("recent"), list):
      self.launcher = {"favorites": [], "recent": []}
    self.launcher["favorites"] = list(dict.fromkeys(item for item in self.launcher["favorites"] if isinstance(item, str) and 1 <= len(item) <= 512))[:100]
    self.launcher["recent"] = [item for item in self.launcher["recent"] if isinstance(item, dict)
      and isinstance(item.get("id"), str) and isinstance(item.get("count"), int) and not isinstance(item.get("count"), bool)
      and 0 <= item["count"] <= 10000 and isinstance(item.get("time"), (int, float))][:200]
    themes = {}
    for name, palette in self.library["themes"].items():
      try:
        themes[self.name(name)] = self.api.validate_setting("customPalette", palette)
      except (ValueError, TypeError):
        continue
    self.library["themes"] = themes
    self.library["profiles"] = {name: value for name, value in self.library["profiles"].items()
      if isinstance(name, str) and 1 <= len(name) <= 40 and isinstance(value, dict)}

  def read(self, name, fallback):
    try:
      return self.api.read_json(self.s.store.directory / name)
    except (OSError, ValueError):
      pass
    return copy.deepcopy(fallback)

  def startup(self):
    self.emit_library()
    self.s.emit("launcher", self.launcher)

  def emit_library(self):
    self.s.emit("library", {"profiles": sorted(self.library["profiles"]), "themes": self.library["themes"]})

  def require_config(self, request):
    if not self.s.configuration_focused or request.get("source") != "config":
      raise ValueError("Esta acción pertenece a la ventana de configuración")

  @staticmethod
  def name(value):
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= 40 or any(ord(c) < 32 for c in value):
      raise ValueError("Escribe un nombre de entre 1 y 40 caracteres")
    return value.strip()

  @staticmethod
  def path(value):
    if not isinstance(value, str) or not value or len(value) > 4096 or "\0" in value:
      raise ValueError("Ruta local inválida")
    if value.startswith("file:"):
      url = urlparse(value)
      if url.netloc not in {"", "localhost"}:
        raise ValueError("El archivo debe ser local")
      value = unquote(url.path)
    path = Path(value).expanduser()
    if not path.is_absolute():
      raise ValueError("Selecciona una ruta absoluta")
    return path

  def portable(self):
    return {key: copy.deepcopy(value) for key, value in self.s.store.settings.items()
        if key not in {"version", "doNotDisturb", "clipboardPaused"}}

  def verify_updates(self, updates):
    if not isinstance(updates, dict) or not updates or set(updates) - (self.api.DEFAULTS.keys() - {"version"}):
      raise ValueError("El archivo contiene ajustes desconocidos")
    result = {key: self.api.validate_setting(key, value) for key, value in updates.items()}
    self.api.validate_geometry(self.api.synchronize_layout(self.s.store.settings, result))
    return result

  def settings_updates(self, action, data):
    with self.lock:
      if action == "settings-reset-section":
        updates = self.api.section_updates(data.get("section"), self.api.DEFAULTS, self.s.store.settings, data.get("monitor", ""))
        merged = self.api.synchronize_layout(copy.deepcopy(self.s.store.settings), updates)
        def fit(configuration):
          cross = "barPaddingX" if configuration["barPosition"] in {"left", "right"} else "barPaddingY"
          required = self.api.geometry_minimum(configuration)
          if required > 128:
            configuration[cross] = max(0, configuration[cross] - (required - 128 + 1) // 2)
          configuration["barSize"] = max(configuration["barSize"], self.api.geometry_minimum(configuration))
          return configuration
        merged = fit(merged)
        for name, override in merged["monitorBars"].items():
          effective = fit({**merged, **override, "monitorBars": {}})
          for key in ("barSize", "barPaddingX", "barPaddingY"):
            if effective[key] != {**merged, **override}[key]:
              override[key] = effective[key]
        return {key: value for key, value in merged.items() if value != self.s.store.settings[key]}
      if action == "profile-apply":
        name = self.name(data.get("name"))
        if name not in self.library["profiles"]:
          raise ValueError("El perfil ya no existe")
        updates = self.verify_updates(self.library["profiles"][name])
      elif action == "theme-use":
        name = self.name(data.get("name"))
        if name not in self.library["themes"]:
          raise ValueError("El tema ya no existe")
        palette = self.api.validate_setting("customPalette", self.library["themes"][name])
        updates = {"theme": "custom", "customPalette": palette, "accent": palette["accent"]}
      elif action == "settings-import":
        path = self.path(data.get("path"))
        imported = self.api.read_json(path, limit=1_000_000)
        if not isinstance(imported, dict) or imported.get("version") != 1:
          raise ValueError("Formato de importación desconocido")
        if imported.get("type") == "hyprlarp-theme":
          palette = self.api.validate_setting("customPalette", imported.get("palette"))
          updates = {"theme": "custom", "customPalette": palette, "accent": palette["accent"]}
        elif imported.get("type") == "hyprlarp-profile":
          updates = self.verify_updates(imported.get("settings"))
        else:
          raise ValueError("Selecciona un perfil o tema exportado por HyprLarp")
      else:
        raise ValueError("Acción de configuración desconocida")
      self.api.atomic_json(self.s.store.directory / "settings.backup.json", self.s.store.settings)
      return updates

  def handle(self, request):
    action, data = request.get("action"), request.get("data", {})
    if action in {"launcher-used", "launcher-favorite"}:
      ident = data.get("id")
      if not isinstance(ident, str) or not 1 <= len(ident) <= 512 or any(ord(c) < 32 for c in ident):
        raise ValueError("Identificador de aplicación inválido")
      with self.lock:
        if action == "launcher-favorite":
          favorites = self.launcher["favorites"]
          self.launcher["favorites"] = [item for item in favorites if item != ident] if ident in favorites else (favorites + [ident])[-100:]
        else:
          previous = next((item for item in self.launcher["recent"] if isinstance(item, dict) and item.get("id") == ident), {})
          item = {"id": ident, "time": int(time.time()), "count": min(10000, int(previous.get("count", 0)) + 1)}
          self.launcher["recent"] = [item] + [entry for entry in self.launcher["recent"] if isinstance(entry, dict) and entry.get("id") != ident][:199]
        self.api.atomic_json(self.s.store.directory / "launcher.json", self.launcher)
        self.s.emit("launcher", self.launcher)
      return True
    if action not in {"profile-save", "profile-delete", "theme-save", "theme-delete", "settings-export"}:
      return False
    self.require_config(request)
    with self.lock:
      if action == "settings-export":
        path = self.path(data.get("path"))
        if path.suffix.lower() != ".json":
          path = path.with_suffix(".json")
        if data.get("kind") == "theme":
          palette = {**self.api.palette_for(self.s.store.settings), "accent": self.s.store.settings["accent"]}
          document = {"type": "hyprlarp-theme", "version": 1, "palette": palette}
        else:
          document = {"type": "hyprlarp-profile", "version": 1, "settings": self.portable()}
        self.api.atomic_json(path, document)
        self.s.emit("message", "Exportado: " + path.name)
        return True
      name = self.name(data.get("name"))
      group = "profiles" if action.startswith("profile-") else "themes"
      next_library = copy.deepcopy(self.library)
      if action.endswith("delete"):
        next_library[group].pop(name, None)
      else:
        if name not in next_library[group] and len(next_library[group]) >= 50:
          raise ValueError("La biblioteca admite hasta 50 elementos de cada tipo")
        if group == "profiles":
          next_library[group][name] = self.portable()
        else:
          palette = {**self.api.palette_for(self.s.store.settings), "name": name, "accent": self.s.store.settings["accent"]}
          next_library[group][name] = self.api.validate_setting("customPalette", palette)
      self.api.atomic_json(self.s.store.directory / "library.json", next_library)
      self.library = next_library
      self.emit_library()
    return True
