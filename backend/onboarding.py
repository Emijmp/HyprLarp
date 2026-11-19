"""First-run state kept separate from user preferences and configuration history."""

from __future__ import annotations

from pathlib import Path

try:
  from .persistence import atomic_json
  from .safety import read_json
except ImportError:
  from persistence import atomic_json
  from safety import read_json


STATE_VERSION = 1
SETTINGS = frozenset({
  "theme", "accent", "themeScheduleEnabled", "panelLayout", "panelStyle",
  "barPosition", "barEnabled", "performanceMode", "animations",
  "accessibilityTextScale", "accessibilityMinimumFontSize",
  "accessibilityHighContrast", "accessibilityReducedMotion", "accessibilityLargeTargets",
})


class Onboarding:
  def __init__(self, directory: Path, root: Path, *, automatic: bool = True, writer=None):
    self.file = directory / "onboarding.json"
    self.write = writer or atomic_json
    self.automatic = automatic
    settings = directory / "settings.json"
    self.fresh = not (settings.exists() or settings.is_symlink())
    # The installer writes default settings before the shell's first launch.
    # Its flag bridges that gap; updates retain it until the separate state is done.
    try:
      manifest = read_json(root / ".hyprlarp-install.json", limit=4 * 1024 * 1024)
      self.fresh |= (isinstance(manifest, dict) and manifest.get("type") == "hyprlarp-install"
        and type(manifest.get("version")) is int and manifest["version"] == 1
        and manifest.get("first_run") is True)
    except (OSError, ValueError):
      pass
    self.state = None
    self.error = ""
    self._load()

  def _load(self):
    self.state, self.error = None, ""
    try:
      if self.file.is_symlink():
        raise ValueError("El estado del asistente no puede ser un enlace simbólico")
      state = read_json(self.file, limit=4096)
      if not isinstance(state, dict) or type(state.get("version")) is not int:
        raise ValueError("El estado del asistente no tiene un formato válido")
      if state["version"] > STATE_VERSION:
        raise ValueError("El estado del asistente pertenece a una versión más reciente de HyprLarp")
      if (state["version"] != STATE_VERSION or state.get("status") not in {"completed", "skipped"}
        or set(state) - {"version", "status", "release"}
        or ("release" in state and (not isinstance(state["release"], str) or len(state["release"]) > 128))):
        raise ValueError("El estado del asistente no tiene un formato válido")
      self.state = state
    except FileNotFoundError:
      pass
    except (OSError, ValueError, TypeError) as error:
      self.error = "Se ha conservado onboarding.json: " + str(error)

  def snapshot(self):
    status = self.state["status"] if self.state else ("pending" if self.fresh else "existing")
    return {"needed": self.automatic and self.fresh and self.state is None and not self.error,
      "status": status, "readOnly": bool(self.error), "error": self.error}

  def ensure_writable(self):
    self._load()
    if self.error:
      raise ValueError(self.error)

  def updates(self, data):
    if not isinstance(data, dict) or set(data) - {"updates"}:
      raise ValueError("Los datos del asistente no tienen un formato válido")
    updates = data.get("updates", {})
    if not isinstance(updates, dict) or set(updates) - SETTINGS:
      raise ValueError("El asistente solo puede cambiar sus ajustes de apariencia y accesibilidad")
    return updates

  def finish(self, status: str, release: str):
    if status not in {"completed", "skipped"}:
      raise ValueError("Estado final del asistente inválido")
    self.ensure_writable()
    state = {"version": STATE_VERSION, "status": status, "release": release}
    try:
      self.write(self.file, state)
    except OSError as error:
      raise OSError("No se pudo guardar el estado del asistente; puedes reintentar: " + str(error)) from error
    self.state = state
