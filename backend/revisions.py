"""Bounded configuration revisions and undo state, written only after edits."""

from __future__ import annotations

import copy
import hashlib
import json
import time
import uuid

try:
  from .persistence import atomic_json
  from .safety import read_json
  from .settings_schema import DEFAULTS, SETTINGS_HISTORY_LIMIT, shortcut_key, validate_setting
except ImportError:
  from persistence import atomic_json
  from safety import read_json
  from settings_schema import DEFAULTS, SETTINGS_HISTORY_LIMIT, shortcut_key, validate_setting

VERSION_LIMIT = 30
HISTORY_BYTES = 6 * 1024 * 1024
TRANSIENT = {"version", "doNotDisturb", "clipboardPaused"}
CAPTURE_SHORTCUT = "screenshot-region-frozen"


def capture_default(values):
  chord = DEFAULTS["shortcuts"][CAPTURE_SHORTCUT]
  occupied = [value for key, value in values.get("shortcuts", {}).items() if key != CAPTURE_SHORTCUT and value]
  occupied += [item.get("chord") for item in values.get("customBindings", [])
    if isinstance(item, dict) and item.get("enabled", True) is True]
  for value in occupied:
    try:
      if shortcut_key(value) == shortcut_key(chord):
        return ""
    except (ValueError, TypeError):
      pass
  return chord


def portable(settings):
  return {key: copy.deepcopy(value) for key, value in settings.items() if key not in TRANSIENT}


def fingerprint(settings):
  return hashlib.sha256(json.dumps(settings, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


class Revisions:
  def __init__(self, directory):
    self.path = directory / "settings-history.json"
    self.document = {"type": "hyprlarp-settings-history", "version": 1, "head": "", "undo": [], "redo": [], "revisions": []}
    self.warning = ""
    self.added_defaults = set()
    self.capture_migrations = set()
    if self.path.exists():
      try:
        data = read_json(self.path, limit=HISTORY_BYTES)
        if not isinstance(data, dict) or data.get("type") != self.document["type"] or data.get("version") != 1:
          raise ValueError("Formato de historial desconocido")
        revisions = data.get("revisions")
        if not isinstance(revisions, list) or len(revisions) > VERSION_LIMIT:
          raise ValueError("Historial de versiones inválido")
        seen = set()
        for item in revisions:
          if not isinstance(item, dict) or not isinstance(item.get("id"), str) or len(item["id"]) != 32 or item["id"] in seen:
            raise ValueError("Identificador de versión inválido")
          int(item["id"], 16)
          seen.add(item["id"])
          if not isinstance(item.get("time"), (int, float)) or isinstance(item["time"], bool) or not 0 <= item["time"] <= 1e12:
            raise ValueError("Fecha de versión inválida")
          if not isinstance(item.get("label"), str) or len(item["label"]) > 120:
            raise ValueError("Nombre de versión inválido")
          values = item.get('settings')
          if isinstance(values, dict):
            missing = (set(DEFAULTS) - TRANSIENT) - set(values)
            if missing and all(key.startswith('accessibility') for key in missing):
              self.added_defaults.update(missing)
              values.update({key: copy.deepcopy(DEFAULTS[key]) for key in missing})
          self.migrate_capture(values)
          self.validate_values(values, complete=True)
        for name in ("undo", "redo"):
          if not isinstance(data.get(name), list) or len(data[name]) > SETTINGS_HISTORY_LIMIT:
            raise ValueError("Historial de cambios inválido")
          for entry in data[name]:
            if not isinstance(entry, dict) or set(entry) != {"before", "after"}:
              raise ValueError("Cambio inválido")
            self.migrate_capture(entry["before"])
            self.migrate_capture(entry["after"])
            self.validate_values(entry["before"])
            self.validate_values(entry["after"])
            if set(entry["before"]) != set(entry["after"]):
              raise ValueError("Cambio incompleto")
        self.document = data
      except (OSError, ValueError, TypeError, KeyError) as error:
        self.warning = "No se pudo leer el historial de configuración: " + str(error)

  def migrate_capture(self, values, context=None):
    shortcuts = values.get("shortcuts") if isinstance(values, dict) else None
    if not isinstance(shortcuts, dict):
      return
    if set(shortcuts) == set(DEFAULTS["shortcuts"]) - {CAPTURE_SHORTCUT}:
      self.capture_migrations.add(id(shortcuts))
    if id(shortcuts) in self.capture_migrations:
      shortcuts[CAPTURE_SHORTCUT] = capture_default({**(context or {}), **values})

  @staticmethod
  def validate_values(values, complete=False):
    allowed = set(DEFAULTS) - {"version"}
    if not isinstance(values, dict) or set(values) - allowed or (complete and set(values) != allowed - TRANSIENT):
      raise ValueError("Ajustes de versión inválidos")
    for key, value in values.items():
      # A deleted wallpaper/folder must not discard the entire history. It is
      # validated against the filesystem again when restoring that revision.
      if key in {"wallpaper", "wallpaperDirectory"}:
        if not isinstance(value, str) or len(value) > 4096 or "\0" in value:
          raise ValueError("Ruta de versión inválida")
      else:
        validate_setting(key, value)

  def stacks(self, settings):
    candidates = [settings]
    if self.added_defaults:
      candidates.append({key: value for key, value in settings.items() if key not in self.added_defaults})
    if settings.get("shortcuts", {}).get(CAPTURE_SHORTCUT) == capture_default(settings):
      for candidate in list(candidates):
        previous = copy.deepcopy(candidate)
        previous["shortcuts"].pop(CAPTURE_SHORTCUT, None)
        candidates.append(previous)
    if not any(self.document.get("head") == fingerprint(candidate) for candidate in candidates):
      return [], []
    # Partial undo entries inherit custom binds from their historical context.
    for name, target in (("undo", "before"), ("redo", "after")):
      context = copy.deepcopy(settings)
      for entry in reversed(self.document[name]):
        self.migrate_capture(entry["before"], context)
        self.migrate_capture(entry["after"], context)
        context.update(copy.deepcopy(entry[target]))
    self.document["head"] = fingerprint(settings)
    return copy.deepcopy(self.document["undo"]), copy.deepcopy(self.document["redo"])

  def save(self, before, settings, undo, redo, *, capture=True, label="Configuración"):
    document = copy.deepcopy(self.document)
    versions = document["revisions"]
    for value, title in ((before, "Antes del cambio"), (settings, label)) if capture else ():
      value = portable(value)
      if not versions or versions[-1]["settings"] != value:
        versions.append({"id": uuid.uuid4().hex, "time": time.time(), "label": title, "settings": value})
    document.update(head=fingerprint(settings), undo=copy.deepcopy(undo), redo=copy.deepcopy(redo), revisions=versions[-VERSION_LIMIT:])
    # Retain the most recent data if unusually large per-monitor settings would
    # exceed the disk budget; normal defaults remain far below this limit.
    while len(json.dumps(document, ensure_ascii=False).encode()) > HISTORY_BYTES - 1024:
      if len(document["revisions"]) > 1:
        document["revisions"].pop(0)
      elif document["undo"]:
        document["undo"].pop(0)
      elif document["redo"]:
        document["redo"].pop(0)
      else:
        raise ValueError("La configuración supera el límite del historial")
    atomic_json(self.path, document)
    self.document = document

  def get(self, ident):
    if not isinstance(ident, str):
      raise ValueError("Selecciona una versión")
    item = next((item for item in self.document["revisions"] if item["id"] == ident), None)
    if item is None:
      raise ValueError("La versión ya no existe")
    return copy.deepcopy(item)

  def listing(self, settings):
    current = portable(settings)
    return [{"id": item["id"], "time": item["time"], "label": item["label"],
      "keys": [key for key, value in item["settings"].items() if current.get(key) != value]}
      for item in reversed(self.document["revisions"])]

  def compare(self, ident, settings):
    item = self.get(ident)
    return {"id": ident, "changes": [{"key": key, "current": copy.deepcopy(settings.get(key)), "saved": value}
      for key, value in item["settings"].items() if settings.get(key) != value]}
