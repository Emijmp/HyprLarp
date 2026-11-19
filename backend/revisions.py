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
HISTORY_VERSION = 2
# Values introduced after the original journal format. Keep these recorded
# defaults stable; a later schema change needs its own migration step.
LEGACY_DEFAULTS = {
  "accessibilityTextScale": 1,
  "accessibilityHighContrast": False,
  "accessibilityReducedMotion": False,
  "accessibilityLargeTargets": False,
  "accessibilityMinimumFontSize": 12,
  "themeScheduleEnabled": False,
  "themeDay": "paper",
  "themeNight": "amoled",
  "themeDayStart": "07:00",
  "themeNightStart": "19:00",
  "panelLayout": "floating",
  "panelStyle": "standard",
  "panelBlur": False,
  "performanceMode": "balanced",
}
# Legacy heads contain only a fingerprint, including journals with no complete
# snapshots. These are the additions made in the recorded releases.
LEGACY_HEAD_GROUPS = (
  frozenset({"accessibilityTextScale", "accessibilityHighContrast",
    "accessibilityReducedMotion", "accessibilityLargeTargets"}),
  frozenset({"accessibilityMinimumFontSize"}),
  frozenset(key for key in LEGACY_DEFAULTS if not key.startswith("accessibility")),
)
LEGACY_HEAD_SHAPES = tuple(frozenset().union(*(group for index, group in enumerate(LEGACY_HEAD_GROUPS)
  if mask & (1 << index))) for mask in range(1 << len(LEGACY_HEAD_GROUPS)))


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
    self.document = {"type": "hyprlarp-settings-history", "version": HISTORY_VERSION, "head": "", "undo": [], "redo": [], "revisions": []}
    self.warning = ""
    self.read_only = False
    self.added_defaults = set()
    self.capture_migrations = set()
    self.legacy = False
    self.legacy_head_shapes = set(LEGACY_HEAD_SHAPES)
    if self.path.exists():
      try:
        data = read_json(self.path, limit=HISTORY_BYTES)
        if (isinstance(data, dict) and data.get("type") == self.document["type"]
            and type(data.get("version")) is int and data["version"] > HISTORY_VERSION):
          self.read_only = True
          raise ValueError("El historial usa una versión posterior; se conserva sin modificar")
        if (not isinstance(data, dict) or data.get("type") != self.document["type"]
            or type(data.get("version")) is not int or data["version"] not in {1, HISTORY_VERSION}):
          raise ValueError("Formato de historial desconocido")
        self.legacy = data["version"] == 1
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
          if self.legacy and isinstance(values, dict):
            missing = (set(DEFAULTS) - TRANSIENT) - set(values)
            if missing and missing <= LEGACY_DEFAULTS.keys():
              self.added_defaults.update(missing)
              self.legacy_head_shapes.add(frozenset(missing))
              values.update({key: copy.deepcopy(LEGACY_DEFAULTS[key]) for key in missing})
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
        # Loading migrates only the in-memory document. The normal atomic save
        # writes the new version after the next actual configuration edit.
        data["version"] = HISTORY_VERSION
        self.document = data
      except (OSError, ValueError, TypeError, KeyError) as error:
        self.warning = "No se pudo leer el historial de configuración: " + str(error)

  def migrate_capture(self, values, context=None):
    shortcuts = values.get("shortcuts") if isinstance(values, dict) else None
    if not isinstance(shortcuts, dict):
      return
    if self.legacy and set(shortcuts) == set(DEFAULTS["shortcuts"]) - {CAPTURE_SHORTCUT}:
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
    if self.legacy:
      for removed in self.legacy_head_shapes:
        # New nondefault values are real edits, not an automatic migration.
        if removed and all(settings.get(key) == LEGACY_DEFAULTS[key] for key in removed):
          candidates.append({key: value for key, value in settings.items() if key not in removed})
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
    if self.read_only:
      raise ValueError("El historial usa una versión posterior; se conserva sin modificar")
    document = copy.deepcopy(self.document)
    versions = document["revisions"]
    for value, title in ((before, "Antes del cambio"), (settings, label)) if capture else ():
      value = portable(value)
      if not versions or versions[-1]["settings"] != value:
        versions.append({"id": uuid.uuid4().hex, "time": time.time(), "label": title, "settings": value})
    document.update(version=HISTORY_VERSION, head=fingerprint(settings), undo=copy.deepcopy(undo), redo=copy.deepcopy(redo), revisions=versions[-VERSION_LIMIT:])
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
    self.legacy = False
    self.capture_migrations.clear()

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
