"""Validated settings persistence and configuration-only undo/redo."""

from __future__ import annotations

import copy
from pathlib import Path
import threading

try:
  from .persistence import atomic_json
  from .revisions import Revisions
  from .safety import private_directory, read_json
  from .settings_schema import DEFAULTS, PALETTES, SETTINGS_HISTORY_LIMIT, migrate_settings, validate_setting, validate_geometry, geometry_minimum, synchronize_layout, validate_combined
except ImportError:
  from persistence import atomic_json
  from revisions import Revisions
  from safety import private_directory, read_json
  from settings_schema import DEFAULTS, PALETTES, SETTINGS_HISTORY_LIMIT, migrate_settings, validate_setting, validate_geometry, geometry_minimum, synchronize_layout, validate_combined

class Store:
  def __init__(self, directory: Path, writer=None):
    self.write = writer or atomic_json
    self.directory = private_directory(directory)
    self.file = directory / "settings.json"
    self.lock = threading.RLock()
    self.settings = copy.deepcopy(DEFAULTS)
    self.warning = ""
    self.undo_stack: list[dict] = []
    self.redo_stack: list[dict] = []
    if self.file.exists():
      try:
        saved = read_json(self.file)
        if not isinstance(saved, dict):
          raise ValueError("La configuración no es un objeto JSON")
        saved = migrate_settings(saved)
        for key, value in saved.items():
          if key in DEFAULTS and key != "version":
            try:
              self.settings[key] = validate_setting(key, value)
            except (ValueError, TypeError):
              self.warning = f"Se ignoró un ajuste inválido: {key}"
        for name, override in list(self.settings["monitorBars"].items()):
          effective = {**self.settings, **override, "monitorBars": {}}
          minimum = geometry_minimum(effective)
          if minimum > 128:
            del self.settings["monitorBars"][name]
            self.warning = f"Se ignoró la geometría inválida del monitor {name}"
          elif effective["barSize"] < minimum:
            override["barSize"] = minimum
            self.warning = f"Se ajustó el grosor del monitor {name}"
        try:
          validate_geometry(self.settings)
        except ValueError:
          content = max(self.settings["barIconSize"], self.settings["barFontSize"] + 4)
          for key in ("barPaddingX", "barPaddingY"):
            inner = self.settings["modulePaddingX" if key == "barPaddingX" else "modulePaddingY"]
            maximum_padding = (128 - content) // 2 - self.settings["barBorderWidth"] - inner - self.settings["moduleBorderWidth"]
            self.settings[key] = min(self.settings[key], maximum_padding)
          self.settings["barSize"] = max(self.settings["barSize"], geometry_minimum(self.settings))
          self.warning = "Se ajustó la geometría de la barra para mantener el contenido visible"
          validate_geometry(self.settings)
        try:
          validate_combined(self.settings)
        except ValueError:
          self.settings["customBindings"] = []
          self.warning = "Se ignoraron binds personalizados con combinaciones duplicadas"
      except (ValueError, OSError) as error:
        self.warning = f"No se pudo leer settings.json: {error}"
    self.revisions = Revisions(directory)
    self.undo_stack, self.redo_stack = self.revisions.stacks(self.settings)
    self.warning = self.warning or self.revisions.warning

  def _save_history(self, before, *, capture=True, label="Configuración"):
    try:
      self.revisions.save(before, self.settings, self.undo_stack, self.redo_stack, capture=capture, label=label)
    except (OSError, ValueError) as error:
      # A history failure must not roll back successfully saved preferences.
      self.warning = "Los ajustes se guardaron, pero no su historial: " + str(error)

  def update(self, updates: dict, *, record: bool = True) -> dict:
    if not isinstance(updates, dict):
      raise ValueError("Los ajustes deben ser un objeto")
    validated = {key: validate_setting(key, value) for key, value in updates.items()}
    with self.lock:
      merged = synchronize_layout(self.settings, validated)
      if merged["theme"] == "custom":
        palette = copy.deepcopy(merged["customPalette"])
        if "accent" in validated:
          palette["accent"] = validated["accent"]
        merged["customPalette"] = palette
        merged["accent"] = palette["accent"]
      elif "theme" in validated and "accent" not in validated:
        merged["accent"] = PALETTES[merged["theme"]]["accent"]
      if "barMargin" in validated and "barMargins" not in validated:
        merged["barMargins"] = {edge: validated["barMargin"] for edge in ("top", "right", "bottom", "left")}
      validate_geometry(merged)
      validate_combined(merged)
      self._commit(merged, record=record)
      return copy.deepcopy(self.settings)

  def _commit(self, settings: dict, force: bool = False, record: bool = True) -> None:
    changed = {key for key in settings if settings[key] != self.settings[key]}
    if changed or force:
      # Mutate the history only after persistence succeeds.
      self.write(self.file, settings)
    if changed:
      previous = self.settings
      if record:
        entry = {"before": {key: copy.deepcopy(self.settings[key]) for key in changed},
             "after": {key: copy.deepcopy(settings[key]) for key in changed}}
        self.undo_stack = (self.undo_stack + [entry])[-SETTINGS_HISTORY_LIMIT:]
        self.redo_stack.clear()
      else:
        # Changes from shell panels must survive configuration undo/redo.
        self._forget_external_keys(changed)
      self.settings = copy.deepcopy(settings)
      self._save_history(previous, capture=record)

  def _forget_external_keys(self, keys: set) -> None:
    def remaining(stack):
      result = []
      for entry in stack:
        before = {key: value for key, value in entry["before"].items() if key not in keys}
        if before:
          result.append({"before": before, "after": {key: entry["after"][key] for key in before}})
      return result
    self.undo_stack = remaining(self.undo_stack)
    self.redo_stack = remaining(self.redo_stack)

  def history_state(self) -> dict:
    with self.lock:
      return {"undo": len(self.undo_stack), "redo": len(self.redo_stack)}

  def undo(self) -> dict:
    with self.lock:
      if self.undo_stack:
        entry = self.undo_stack[-1]
        target = {**self.settings, **copy.deepcopy(entry["before"])}
        validate_geometry(target)
        validate_combined(target)
        self.write(self.file, target)
        previous = self.settings
        self.redo_stack.append(self.undo_stack.pop())
        self.settings = target
        self._save_history(previous, label="Deshacer")
      return copy.deepcopy(self.settings)

  def redo(self) -> dict:
    with self.lock:
      if self.redo_stack:
        entry = self.redo_stack[-1]
        target = {**self.settings, **copy.deepcopy(entry["after"])}
        validate_geometry(target)
        validate_combined(target)
        self.write(self.file, target)
        previous = self.settings
        self.undo_stack.append(self.redo_stack.pop())
        self.settings = target
        self._save_history(previous, label="Rehacer")
      return copy.deepcopy(self.settings)

  def reset(self) -> dict:
    with self.lock:
      self._commit(copy.deepcopy(DEFAULTS), force=True)
      self.warning = ""
      return copy.deepcopy(self.settings)
