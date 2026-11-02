#!/usr/bin/env python3
"""A JSON-lines bridge with a standard-library core and optional GIO devices."""

from __future__ import annotations

import argparse
import concurrent.futures
import copy
import datetime as dt
import json
import math
import os
from pathlib import Path
import re
import signal
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from typing import Any

if __package__:
  from .icons import IconResolver
  from .layouts import BAR_KEYS, flatten, section_updates, synchronize_layout, validate_monitor_bars, validate_zones, zones_for
  from .features import Features
  from .clipboard import Clipboard
  from .captures import Captures
  from .battery import battery_state
  from .udev import UdevEvents
  from .devices import Devices
  from .night import NightLight
  from .wallpapers import EXTENSIONS, catalogue, local_path
  from .bluetooth import BluetoothManager
  from .wifi import WifiSecrets
  from .shortcuts import chord_parts, chord_key, validate_custom, validate_combined, render as render_bindings
  from .safety import BoundedExecutor, JSON_LIMIT, bounded_process, private_directory, read_json, read_regular, stop_processes, idle_processes, parse_json
else:
  from icons import IconResolver
  from layouts import BAR_KEYS, flatten, section_updates, synchronize_layout, validate_monitor_bars, validate_zones, zones_for
  from features import Features
  from clipboard import Clipboard
  from captures import Captures
  from battery import battery_state
  from udev import UdevEvents
  from devices import Devices
  from night import NightLight
  from wallpapers import EXTENSIONS, catalogue, local_path
  from bluetooth import BluetoothManager
  from wifi import WifiSecrets
  from shortcuts import chord_parts, chord_key, validate_custom, validate_combined, render as render_bindings
  from safety import BoundedExecutor, JSON_LIMIT, bounded_process, private_directory, read_json, read_regular, stop_processes, idle_processes, parse_json

ROOT = Path(__file__).resolve().parents[1]
MODULE_DEFINITIONS = json.loads((ROOT / "config/modules.json").read_text())
MODULES = {entry["id"] for entry in MODULE_DEFINITIONS}
PANELS = {entry["target"] for entry in MODULE_DEFINITIONS if entry["kind"] == "panel"} | {"settings"}
PALETTES = json.loads((ROOT / "config/palettes.json").read_text())
THEMES = set(PALETTES) | {"custom"}
COLOR_ROLES = set(PALETTES["amoled"]) - {"name"}
SETTINGS_ACTIONS = {"settings", "settings-undo", "settings-redo", "settings-reset", "settings-reset-section", "profile-apply", "settings-import", "theme-use"}
SETTINGS_HISTORY_LIMIT = 50
# 500 normalized notices can exceed the ordinary IPC budget with UTF-8 or escapes.
# History is persisted synchronously, so this allowance never enters the work queue.
NOTIFICATION_JSON_LIMIT = 16 * 1024 * 1024
DEFAULTS = json.loads((ROOT / "config/defaults.json").read_text())
COMMAND_PROFILE = os.environ.get("HYPRLARP_COMMAND_PROFILE", "")


def atomic_bytes(destination: Path, value: bytes) -> None:
  destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
  fd, temp = tempfile.mkstemp(prefix=".hyprlarp-", dir=destination.parent)
  try:
    with os.fdopen(fd, "wb") as handle:
      handle.write(value)
    os.replace(temp, destination)
  finally:
    if os.path.exists(temp):
      os.unlink(temp)


def atomic_text(destination: Path, value: str) -> None:
  atomic_bytes(destination, value.encode("utf-8"))


def atomic_json(destination: Path, value: Any) -> None:
  atomic_text(destination, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def number(value: Any, low: float, high: float) -> float:
  if isinstance(value, bool) or not isinstance(value, (int, float)):
    raise ValueError("Se esperaba un número")
  if not low <= value <= high:
    raise ValueError(f"El valor debe estar entre {low} y {high}")
  return value


def validate_setting(key: str, value: Any) -> Any:
  if key not in DEFAULTS or key == "version":
    raise ValueError("Ajuste desconocido")
  if key in {"animations", "doNotDisturb", "clipboardEnabled", "clipboardPaused", "osdEnabled", "nightLightEnabled", "nightLightSchedule", "barEnabled", "barReserveSpace", "barBlur", "barShowLabels", "showAppIcons", "migrateNoctaliaBinds"}:
    if not isinstance(value, bool):
      raise ValueError("Se esperaba verdadero o falso")
  elif key in {"barOpacity", "moduleOpacity", "moduleBackgroundOpacity", "panelOpacity"}:
    number(value, 0, 1)
  elif key in {"radius", "moduleRadius"}:
    value = int(number(value, 0, 8))
  elif key == "barWorkspaceDisplay":
    if value not in {"current", "dots", "compact"}:
      raise ValueError("Indicador de espacios desconocido")
  elif key == "nightLightTemperature":
    value = int(number(value, 1000, 6500))
  elif key == "osdTimeout":
    value = int(number(value, 500, 5000))
  elif key == "osdPosition":
    if value not in {"top", "bottom"}:
      raise ValueError("Posición del OSD desconocida")
  elif key in {"nightLightStart", "nightLightEnd"}:
    if not isinstance(value, str) or not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value):
      raise ValueError("Usa una hora de 00:00 a 23:59")
  elif key == "cornerRadii":
    allowed = {"bar", "panel", "button", "field", "workspace", "notification", "tooltip"}
    if not isinstance(value, dict) or set(value) - allowed:
      raise ValueError("Tipo de elemento desconocido para la redondez")
    value = {kind: int(number(radius, 0, 8)) for kind, radius in value.items()}
  elif key in {"barMargin", "barPaddingX", "barPaddingY", "barSpacing"}:
    value = int(number(value, 0, 64))
  elif key in {"modulePaddingX", "modulePaddingY"}:
    value = int(number(value, 0, 32))
  elif key == "barMargins":
    if not isinstance(value, dict) or set(value) != {"top", "right", "bottom", "left"}:
      raise ValueError("Indica los cuatro márgenes de la barra")
    value = {edge: int(number(margin, 0, 64)) for edge, margin in value.items()}
  elif key in {"barBorderWidth", "moduleBorderWidth"}:
    value = int(number(value, 0, 4))
  elif key == "barSize":
    value = int(number(value, 22, 128))
  elif key == "barLength":
    value = int(number(value, 25, 100))
  elif key in {"barFontSize", "barIconSize"}:
    value = int(number(value, 10, 24))
  elif key == "barWorkspaceCount":
    value = int(number(value, 1, 10))
  elif key == "decoration":
    if value not in {"minimal", "subtle"}:
      raise ValueError("Nivel de detalle desconocido")
  elif key == "decorationOptions":
    if not isinstance(value, dict) or set(value) - set(DEFAULTS["decorationOptions"]) or any(not isinstance(item, bool) for item in value.values()):
      raise ValueError("Opciones de decoración inválidas")
  elif key == "barAlignment":
    if value not in {"start", "center", "end"}:
      raise ValueError("Alineación desconocida")
  elif key == "notificationHistoryLimit":
    value = int(number(value, 0, 500))
  elif key == "clipboardRetentionHours":
    value = int(number(value, 0, 8760))
  elif key == "barZones":
    value = validate_zones(value, MODULES)
  elif key == "monitorBars":
    value = validate_monitor_bars(value, validate_setting)
  elif key == "trayHiddenItems":
    if not isinstance(value, list) or len(value) > 100 or any(not isinstance(item, str) or len(item) > 256 for item in value):
      raise ValueError("Lista de iconos oculta inválida")
    value = list(dict.fromkeys(value))
  elif key == "notificationRules":
    if not isinstance(value, dict) or len(value) > 200:
      raise ValueError("Reglas de notificación inválidas")
    for app, rule in value.items():
      if not isinstance(app, str) or not 1 <= len(app) <= 256 or not isinstance(rule, dict) or set(rule) - {"popup", "sound", "history"} or any(not isinstance(flag, bool) for flag in rule.values()):
        raise ValueError("Regla por aplicación inválida")
  elif key == "theme":
    if value not in THEMES:
      raise ValueError("Tema desconocido")
  elif key == "customPalette":
    if not isinstance(value, dict) or set(value) != COLOR_ROLES | {"name"}:
      raise ValueError("La paleta debe incluir un nombre y todos los colores")
    name = value["name"]
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 40 or any(ord(character) < 32 for character in name):
      raise ValueError("El nombre del tema debe tener entre 1 y 40 caracteres")
    for role in COLOR_ROLES:
      if not isinstance(value[role], str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", value[role]):
        raise ValueError(f"Color inválido en {role}: usa #RRGGBB")
    value = {key: color.lower() if key != "name" else name.strip() for key, color in value.items()}
  elif key == "barPosition":
    if value not in {"top", "bottom", "left", "right"}:
      raise ValueError("Posición de barra desconocida")
  elif key == "accent":
    if not isinstance(value, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
      raise ValueError("Usa un color hexadecimal: #ffffff")
  elif key in {"barModules", "disabledModules"}:
    if not isinstance(value, list) or any(x not in MODULES for x in value):
      raise ValueError("Módulo desconocido")
    if len(value) != len(set(value)):
      raise ValueError("Un módulo no puede aparecer dos veces")
  elif key == "moduleOpacities":
    if not isinstance(value, dict) or set(value) - MODULES:
      raise ValueError("Módulo desconocido")
    for opacity in value.values():
      number(opacity, 0, 1)
  elif key == "shortcuts":
    if not isinstance(value, dict) or set(value) != set(DEFAULTS["shortcuts"]):
      raise ValueError("Lista de atajos inválida")
    used = set()
    for chord in value.values():
      if chord == "":
        continue
      chord_parts(chord)
      canonical = shortcut_key(chord)
      if canonical in used:
        raise ValueError("Hay atajos duplicados")
      used.add(canonical)
  elif key == "customBindings":
    value = validate_custom(value, DEFAULTS["shortcuts"])
  elif key in {"wallpaper", "wallpaperDirectory", "font"}:
    if not isinstance(value, str) or len(value) > 4096 or "\0" in value:
      raise ValueError("Texto inválido")
    if key == "wallpaper" and value:
      candidate = local_path(value)
      if not candidate.is_file() or candidate.suffix.lower() not in EXTENSIONS:
        raise ValueError("El fondo debe ser una imagen local existente")
      value = str(candidate.resolve())
    elif key == "wallpaperDirectory" and value:
      candidate = local_path(value)
      if not candidate.is_dir():
        raise ValueError("La carpeta de fondos no existe")
      value = str(candidate)
  return value


def migrate_settings(saved: dict) -> dict:
  migrated = copy.deepcopy(saved)
  version = migrated.get("version", 1)
  if not isinstance(version, int) or isinstance(version, bool) or version < 2:
    old_theme = migrated.get("theme", "graphite")
    if isinstance(old_theme, str) and old_theme in {"graphite", "nocturne", "sage", "paper"}:
      for key in ("theme", "accent", "radius", "animations", "barOpacity", "moduleOpacity", "panelOpacity", "moduleOpacities"):
        migrated[key] = copy.deepcopy(DEFAULTS[key])
    if migrated.get("barSize", 48) == 48:
      migrated["barSize"] = DEFAULTS["barSize"]
    margin = migrated.get("barMargin", DEFAULTS["barMargin"])
    migrated.setdefault("barMargins", {edge: margin for edge in ("top", "right", "bottom", "left")})
    wallpaper = migrated.get("wallpaper", "")
    if isinstance(wallpaper, str) and wallpaper in {str(ROOT / "assets/wallpapers" / name) for name in ("prism.svg", "monolith.svg", "orbit.svg")}:
      migrated["wallpaper"] = ""
  if not isinstance(version, int) or isinstance(version, bool) or version < 3:
    modules = migrated.get("barModules", DEFAULTS["barModules"])
    disabled = migrated.get("disabledModules", [])
    if isinstance(modules, list) and all(isinstance(name, str) for name in modules):
      excluded = {name for name in disabled if isinstance(name, str)} if isinstance(disabled, list) else set()
      migrated["barModules"] = [name for name in dict.fromkeys(modules) if name not in excluded]
    migrated["disabledModules"] = []
    migrated["showAppIcons"] = True
    previous = migrated.get("shortcuts", {})
    if isinstance(previous, dict):
      shortcuts = {key: value for key, value in previous.items() if key in DEFAULTS["shortcuts"]}
      used = {shortcut_key(value) for value in shortcuts.values() if isinstance(value, str) and "," in value}
      for key, chord in DEFAULTS["shortcuts"].items():
        if key not in shortcuts:
          shortcuts[key] = "" if shortcut_key(chord) in used else chord
          if shortcuts[key]:
            used.add(shortcut_key(chord))
      migrated["shortcuts"] = shortcuts
  migrated["version"] = 3
  if "barZones" not in migrated and isinstance(migrated.get("barModules"), list):
    migrated["barZones"] = zones_for(migrated["barModules"])
  if isinstance(migrated.get("shortcuts"), dict):
    shortcuts = {key: value for key, value in migrated["shortcuts"].items() if key in DEFAULTS["shortcuts"]}
    used = {shortcut_key(chord) for chord in shortcuts.values() if isinstance(chord, str) and "," in chord}
    for key, chord in DEFAULTS["shortcuts"].items():
      if key not in shortcuts:
        shortcuts[key] = "" if shortcut_key(chord) in used else chord
        if shortcuts[key]:
          used.add(shortcut_key(chord))
    migrated["shortcuts"] = shortcuts
  return migrated


def shortcut_key(chord: str) -> tuple:
  return chord_key(chord)


def geometry_minimum(settings: dict) -> int:
  # The cross-axis padding must leave space for the text and icons.
  vertical = settings["barPosition"] in {"left", "right"}
  padding = settings["barPaddingX" if vertical else "barPaddingY"]
  inner = settings["modulePaddingX" if vertical else "modulePaddingY"]
  return 2 * (padding + settings["barBorderWidth"] + inner + settings["moduleBorderWidth"]) + max(settings["barIconSize"], settings["barFontSize"] + 4)


def validate_geometry(settings: dict) -> None:
  minimum = geometry_minimum(settings)
  if settings["barSize"] < minimum:
    raise ValueError(f"Con ese padding y tamaño de contenido, el grosor mínimo es {minimum} px")
  for name, overrides in settings.get("monitorBars", {}).items():
    try:
      validate_geometry({**settings, **overrides, "monitorBars": {}})
    except ValueError as error:
      raise ValueError(f"Monitor {name}: {error}") from error


class Store:
  def __init__(self, directory: Path):
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
      atomic_json(self.file, settings)
    if changed:
      if record:
        entry = {"before": {key: copy.deepcopy(self.settings[key]) for key in changed},
             "after": {key: copy.deepcopy(settings[key]) for key in changed}}
        self.undo_stack = (self.undo_stack + [entry])[-SETTINGS_HISTORY_LIMIT:]
        self.redo_stack.clear()
      else:
        # Changes from shell panels must survive configuration undo/redo.
        self._forget_external_keys(changed)
      self.settings = copy.deepcopy(settings)

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
        atomic_json(self.file, target)
        self.redo_stack.append(self.undo_stack.pop())
        self.settings = target
      return copy.deepcopy(self.settings)

  def redo(self) -> dict:
    with self.lock:
      if self.redo_stack:
        entry = self.redo_stack[-1]
        target = {**self.settings, **copy.deepcopy(entry["after"])}
        validate_geometry(target)
        atomic_json(self.file, target)
        self.undo_stack.append(self.redo_stack.pop())
        self.settings = target
      return copy.deepcopy(self.settings)

  def reset(self) -> dict:
    with self.lock:
      self._commit(copy.deepcopy(DEFAULTS), force=True)
      self.warning = ""
      return copy.deepcopy(self.settings)


def palette_for(settings: dict) -> dict:
  return settings["customPalette"] if settings["theme"] == "custom" else PALETTES[settings["theme"]]


def render_lock_config(settings: dict) -> str:
  palette = palette_for(settings)
  template = (ROOT / "config/hyprlock.conf").read_text()
  defaults = {"background": "000000", "foreground": "ffffff", "muted": "a0a0a0"}
  colors = {"background": palette["background"], "foreground": palette["text"], "muted": palette["muted"]}
  for role, default in defaults.items():
    template = template.replace(f"${role} = rgb({default})", f"${role} = rgb({colors[role][1:]})")
  return template


def command(argv: list[str], *, input_text: str | None = None,
      timeout: float = 8, check: bool = True) -> str:
  if not shutil.which(argv[0]):
    raise RuntimeError(f"Falta instalar {argv[0]}")
  if COMMAND_PROFILE:
    with open(COMMAND_PROFILE, "a") as profile:
      profile.write(json.dumps({"time": time.monotonic(), "command": Path(argv[0]).name}) + "\n")
  content = input_text.encode("utf-8") if input_text is not None else b""
  return bounded_process(argv, content=content, timeout=timeout, check=check).decode("utf-8", errors="replace").strip()


def optional(argv: list[str], fallback: str = "") -> str:
  try:
    return command(argv)
  except (OSError, RuntimeError, ValueError):
    return fallback


def split_nmcli(line: str) -> list[str]:
  """nmcli -t escapes both colons and backslashes, including in SSIDs."""
  fields, current, escaped = [], [], False
  for character in line:
    if escaped:
      current.append(character)
      escaped = False
    elif character == "\\":
      escaped = True
    elif character == ":":
      fields.append("".join(current))
      current = []
    else:
      current.append(character)
  if escaped:
    current.append("\\")
  return fields + ["".join(current)]


def clean_history(entries, limit):
  result = []
  for index, entry in enumerate(entries[:limit]):
    if not isinstance(entry, dict):
      continue
    item = {}
    for key, maximum in {"token": 128, "app": 128, "appId": 128, "summary": 256, "body": 2048, "icon": 1024}.items():
      item[key] = entry.get(key, "")[:maximum] if isinstance(entry.get(key), str) else ""
    item["app"] = item["app"] or "Aplicación"
    item["token"] = item["token"] or "stored:" + str(index)
    item["id"] = entry.get("id", 0) if isinstance(entry.get("id"), int) and not isinstance(entry["id"], bool) else 0
    stamp = entry.get("time", 0)
    item["time"] = stamp if isinstance(stamp, (int, float)) and not isinstance(stamp, bool) and 0 <= stamp <= 8640000000000000 else 0
    item["urgency"] = entry.get("urgency", 1) if entry.get("urgency") in (0, 1, 2) else 1
    item["read"] = entry.get("read") is True
    result.append(item)
  return result


def parse_networks(output: str) -> list[dict]:
  networks = {}
  for line in output.splitlines():
    fields = split_nmcli(line)
    if len(fields) != 5 or not fields[1]:
      continue
    active, ssid, strength, security, interface = fields
    try:
      item = {"ssid": ssid, "signal": int(strength), "security": security,
          "connected": active == "*", "interface": interface}
    except ValueError:
      continue
    key = (ssid, interface)
    old = networks.get(key)
    if old is None or item["connected"] or (not old["connected"] and item["signal"] > old["signal"]):
      networks[key] = item
  return sorted(networks.values(), key=lambda item: (not item["connected"], -item["signal"]))


def brightness_state(base: Path = Path("/sys/class/backlight")) -> dict:
  for device in sorted(base.glob("*")):
    try:
      maximum = int((device / "max_brightness").read_text())
      source = device / "actual_brightness"
      current = int((source if source.exists() else device / "brightness").read_text())
      if maximum > 0:
        return {"brightness": round(100 * current / maximum), "brightnessAvailable": True}
    except (OSError, ValueError):
      continue
  return {"brightness": 0, "brightnessAvailable": False}


def poll_intervals(settings: dict, panel: str, settings_only: bool = False, native_services: bool = False, outputs: list[str] | None = None) -> dict[str, float]:
  """No idle CPU sampling or child processes for panels that are closed."""
  if settings_only:
    return {}
  names = [""] if outputs is None else outputs
  modules = set()
  for name in names:
    bar = {**settings, **settings.get("monitorBars", {}).get(name, {})}
    if bar.get("barEnabled", True):
      modules.update(bar["barModules"])
  modules -= set(settings["disabledModules"])
  plan = {}
  if "resources" in modules or panel in {"resources", "control"}:
    plan["metrics"] = 2
  if panel in {"control", "brightness"} or "brightness" in modules:
    plan["brightness"] = 2
  if panel == "battery":
    plan["battery"] = 2
  elif panel == "control" or "battery" in modules:
    plan["battery"] = 30
  if not native_services and ("wifi" in modules or panel in {"wifi", "control"}):
    plan["network"] = 60
  if panel == "clipboard" and settings["clipboardEnabled"]:
    plan["clipboard"] = 2
  if not native_services and panel == "bluetooth":
    plan["bluetooth"] = 6
  if settings.get("clipboardEnabled") and settings.get("clipboardRetentionHours", 0):
    plan["clipboard-expiry"] = 60
  return plan


class Metrics:
  def __init__(self):
    self.previous_cpu: tuple[int, int] | None = None
    self.previous_network: tuple[float, int, int] | None = None
    self.disk_sample = {}
    self.disk_at = 0
    self.thermal_path = None
    self.thermal_at = 0

  def read(self, detailed=True) -> dict:
    data: dict[str, Any] = {"cpu": None, "memory": 0, "memoryUsed": 0, "memoryTotal": 0,
                "disk": 0, "temperature": None, "upload": 0, "download": 0}
    try:
      with Path("/proc/stat").open() as cpu:
        times = [int(x) for x in cpu.readline().split()[1:9]]
      total, idle = sum(times), times[3] + times[4]
      if self.previous_cpu:
        delta = total - self.previous_cpu[0]
        data["cpu"] = round(100 * (1 - (idle - self.previous_cpu[1]) / max(1, delta)), 1)
      self.previous_cpu = (total, idle)
      memory = {line.split(":")[0]: int(line.split()[1]) for line in Path("/proc/meminfo").read_text().splitlines()}
      data["memoryTotal"] = round(memory["MemTotal"] / 1024**2, 1)
      data["memoryUsed"] = round((memory["MemTotal"] - memory["MemAvailable"]) / 1024**2, 1)
      data["memory"] = round(100 * (1 - memory["MemAvailable"] / memory["MemTotal"]), 1)
      if not detailed:
        return {key: data[key] for key in ("cpu", "memory", "memoryUsed", "memoryTotal")}
      now = time.monotonic()
      if not self.disk_sample or now - self.disk_at >= 10:
        disk = shutil.disk_usage(Path.home())
        self.disk_sample = {"disk": round(100 * disk.used / disk.total, 1), "diskFree": round(disk.free / 1024**3, 1)}
        self.disk_at = now
      data.update(self.disk_sample)
      data["uptime"] = int(float(Path("/proc/uptime").read_text().split()[0]))
      received, sent = 0, 0
      for line in Path("/proc/net/dev").read_text().splitlines()[2:]:
        interface, values = line.split(":", 1)
        if interface.strip() == "lo":
          continue
        values = values.split()
        received += int(values[0])
        sent += int(values[8])
      now = time.monotonic()
      if self.previous_network:
        elapsed = max(0.01, now - self.previous_network[0])
        data["download"] = max(0, round((received - self.previous_network[1]) / elapsed / 1024))
        data["upload"] = max(0, round((sent - self.previous_network[2]) / elapsed / 1024))
      self.previous_network = (now, received, sent)
      if now - self.thermal_at >= 60 or self.thermal_at == 0:
        self.thermal_at = now
        self.thermal_path = next((zone / "temp" for zone in sorted(Path("/sys/class/thermal").glob("thermal_zone*"))
          if (zone / "type").read_text().strip() in {"x86_pkg_temp", "cpu-thermal", "k10temp", "acpitz"}), None)
      if self.thermal_path:
        data["temperature"] = round(int(self.thermal_path.read_text()) / 1000)
    except (OSError, ValueError, KeyError, IndexError):
      pass
    return data


def lua_string(value: str) -> str:
  """Quote a UTF-8 string as Lua source, including paths with quotes or spaces."""
  escaped = []
  for character in value:
    if character in {'"', "\\"}:
      escaped.append("\\" + character)
    elif ord(character) < 32:
      escaped.append(f"\\{ord(character):03d}")
    else:
      escaped.append(character)
  return '"' + "".join(escaped) + '"'


def generate_bindings(settings: dict, executable: Path) -> str:
  validate_setting("shortcuts", settings["shortcuts"])
  custom = validate_setting("customBindings", settings["customBindings"])
  return render_bindings({**settings, "customBindings": custom}, executable)


class Service:
  def __init__(self, store: Store, preview: bool = False, settings_only: bool = False, native_services: bool = False):
    self.store, self.preview, self.settings_only = store, preview, settings_only
    self.native_services = native_services
    self.serving = False
    self.output_lock = threading.Lock()
    self.stopping = threading.Event()
    self.wakeup = threading.Event()
    self.metrics = Metrics()
    self.system_lock = threading.Lock()
    self.system = {"user": os.environ.get("USER", "tú"), "hostname": os.uname().nodename}
    self.snapshot_lock = threading.Lock()
    self.snapshots = {}
    self.watchers: list[subprocess.Popen] = []
    self.watcher_lock = threading.Lock()
    self.output_names = None
    self.active_panel = ""
    self.configuration_focused = False
    self.networks: list[dict] = []
    self.network_lock = threading.Lock()
    self.refresh_lock = threading.Lock()
    self.refreshing = set()
    self.pending_refresh = {}
    self.icon_resolver = None
    self.icon_lock = threading.Lock()
    self.executor = BoundedExecutor(max_workers=3, pending=12)
    self.features = Features(self, sys.modules[__name__])
    self.clipboard_manager = Clipboard(self, sys.modules[__name__])
    self.captures = Captures(self, sys.modules[__name__])
    self.devices = Devices(self)
    self.bluetooth_manager = BluetoothManager(self)
    self.wifi_secrets = WifiSecrets()
    self.night = NightLight(self, sys.modules[__name__])
    self.backlight = UdevEvents("backlight", lambda: self.queue_refresh("brightness-event", lambda: self.refresh_system(brightness=True), latest=True))

  def emit(self, kind: str, data: Any) -> None:
    with self.output_lock:
      try:
        print(json.dumps({"type": kind, "data": data}, ensure_ascii=False), flush=True)
      except (BrokenPipeError, OSError):
        self.stopping.set()
        self.wakeup.set()

  def emit_changed(self, kind: str, data: Any) -> None:
    with self.snapshot_lock:
      if self.snapshots.get(kind) != data:
        self.snapshots[kind] = copy.deepcopy(data)
        self.emit(kind, data)

  def queue_refresh(self, name: str, function, latest: bool = False) -> bool:
    """One worker per source, with at most one coalesced follow-up for events."""
    with self.refresh_lock:
      if name in self.refreshing:
        if latest:
          self.pending_refresh[name] = function
        return False
      if self.stopping.is_set():
        return False
      self.refreshing.add(name)
    def run():
      current = function
      while current is not None:
        self.safe_refresh(current)
        with self.refresh_lock:
          current = self.pending_refresh.pop(name, None) if not self.stopping.is_set() else None
          if current is None:
            self.refreshing.discard(name)
    try:
      self.executor.submit(run)
    except RuntimeError:
      with self.refresh_lock:
        self.refreshing.discard(name)
        self.pending_refresh.pop(name, None)
      return False
    return True

  def refresh_network(self, rescan: bool = False) -> None:
    with self.network_lock:
      try:
        output = command(["nmcli", "--wait", "15", "-t", "-f", "IN-USE,SSID,SIGNAL,SECURITY,DEVICE", "device", "wifi", "list", "--rescan", "yes" if rescan and not self.preview else "no"], timeout=20)
        self.networks = parse_networks(output)
        enabled = command(["nmcli", "radio", "wifi"]) == "enabled"
        connections = command(["nmcli", "-t", "-f", "TYPE,STATE,CONNECTION", "device"])
        ethernet = any(fields[0] == "ethernet" and fields[1] == "connected"
          for fields in map(split_nmcli, connections.splitlines()) if len(fields) >= 2)
        self.emit_changed("network", {"available": True, "enabled": enabled, "error": "",
          "ethernet": ethernet, "networks": self.networks,
          "ssid": next((x["ssid"] for x in self.networks if x["connected"]), "")})
      except (OSError, RuntimeError) as error:
        self.networks = []
        self.emit_changed("network", {"available": False, "enabled": False, "ethernet": False,
          "networks": [], "ssid": "", "error": "NetworkManager no está disponible: " + str(error)})

  def refresh_bluetooth(self) -> None:
    self.bluetooth_manager.refresh()

  def refresh_clipboard(self) -> None:
    self.clipboard_manager.refresh()

  def refresh_wallpapers(self) -> None:
    directory = self.store.settings["wallpaperDirectory"]
    pictures = optional(["xdg-user-dir", "PICTURES"], str(Path.home() / "Pictures")) if not directory else str(Path.home() / "Pictures")
    images, state = catalogue(directory, ROOT / "assets/wallpapers", Path(pictures) / "Wallpapers")
    self.emit_changed("wallpaper-state", state)
    self.emit_changed("wallpapers", images)

  def refresh_system(self, metrics: bool = False, brightness: bool = False, battery: bool = False) -> None:
    # CPU/memory, backlight and battery are small local reads; no subprocesses.
    with self.system_lock:
      if metrics:
        self.system.update(self.metrics.read(detailed=self.active_panel in {"resources", "control"}))
      if brightness:
        self.system.update(brightness_state())
      if battery:
        self.system["battery"] = battery_state()
      self.emit_changed("system", self.system)

  def load_history(self) -> None:
    try:
      history = read_json(self.store.directory / "notifications.json", limit=NOTIFICATION_JSON_LIMIT)
      self.emit("history", clean_history(history, self.store.settings["notificationHistoryLimit"]) if isinstance(history, list) else [])
    except (OSError, ValueError):
      self.emit("history", [])

  def sync_watchers(self) -> None:
    with self.watcher_lock:
      enabled = self.store.settings["clipboardEnabled"] and not self.store.settings["clipboardPaused"] and not self.preview and not self.settings_only
      if not enabled:
        for watcher in self.watchers:
          if watcher.poll() is None:
            watcher.terminate()
        self.watchers.clear()
      elif not self.watchers and shutil.which("wl-paste") and shutil.which("cliphist"):
        for mime in ["text", "image"]:
          self.watchers.append(subprocess.Popen([sys.executable, str(ROOT / "backend/child.py"), str(os.getpid()), "wl-paste", "--type", mime, "--watch", sys.executable, str(ROOT / "backend/clipboard_store.py")],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))

  def sync_hardware(self):
    if not self.serving:
      return
    modules = set()
    for name in ([""] if self.output_names is None else self.output_names):
      bar = {**self.store.settings, **self.store.settings["monitorBars"].get(name, {})}
      if bar.get("barEnabled", True):
        modules.update(bar["barModules"])
    modules -= set(self.store.settings["disabledModules"])
    self.devices.sync(power="energy" in modules or self.active_panel in {"energy", "battery", "control"}, usb="usb" in modules or self.active_panel == "usb")
    if not self.preview and not self.settings_only and self.store.settings["osdEnabled"]:
      self.backlight.start()
    else:
      self.backlight.stop()

  def poll(self) -> None:
    due, previous = {}, {}
    self.refresh_system(battery=True)
    while not self.stopping.is_set():
      self.wakeup.clear()
      plan = poll_intervals(self.store.settings, self.active_panel, self.settings_only, self.native_services, self.output_names)
      now = time.monotonic()
      for name in set(due) - set(plan):
        del due[name]
        if name == "metrics":
          with self.system_lock:
            self.metrics.previous_cpu = None
            self.metrics.previous_network = None
      sources = {"metrics": lambda: self.refresh_system(metrics=True),
            "brightness": lambda: self.refresh_system(brightness=True),
            "battery": lambda: self.refresh_system(battery=True),
            "network": self.refresh_network, "bluetooth": self.refresh_bluetooth,
            "clipboard": self.refresh_clipboard,
            "clipboard-expiry": lambda: self.clipboard_manager.refresh(expire=True)}
      for name, interval in plan.items():
        if previous.get(name) != interval or now >= due.get(name, 0):
          self.queue_refresh("wifi" if name == "network" else name, sources[name])
          due[name] = now + interval
      previous = plan
      timeout = max(0.05, min(due.values()) - time.monotonic()) if due else None
      self.wakeup.wait(timeout)

  def safe_refresh(self, function) -> None:
    try:
      function()
    except Exception as error:
      self.emit("error", str(error))

  def emit_settings(self) -> None:
    self.emit("settings-history", self.store.history_state())
    self.emit("settings", self.store.settings)

  def edit_settings(self, action: str, data: dict, source: str = "shell") -> None:
    if action != "settings" and (not self.configuration_focused or source != "config"):
      raise ValueError("Abre y enfoca la configuración para deshacer, rehacer o restablecer")
    previous_directory = self.store.settings["wallpaperDirectory"]
    if action == "settings":
      self.store.update(data, record=source == "config")
    elif action == "settings-undo":
      self.store.undo()
    elif action == "settings-redo":
      self.store.redo()
    elif action == "settings-reset":
      self.store.reset()
    else:
      self.store.update(self.features.settings_updates(action, data))
    self.safe_refresh(self.sync_watchers)
    self.safe_refresh(self.sync_hardware)
    if self.serving:
      self.queue_refresh("night-light", self.night.sync, latest=True)
    self.wakeup.set()
    if previous_directory != self.store.settings["wallpaperDirectory"]:
      self.queue_refresh("wallpapers", self.refresh_wallpapers, latest=True)
    self.emit_settings()

  def action(self, request: dict) -> None:
    action = request.get("action")
    data = request.get("data", {})
    try:
      if action != "history" and not isinstance(data, dict):
        raise ValueError("Los datos de la acción deben ser un objeto")
      if action in SETTINGS_ACTIONS:
        self.edit_settings(action, data, request.get("source", "shell"))
        return
      if action == "settings-context":
        focused = data.get("focused")
        if not isinstance(focused, bool):
          raise ValueError("Estado de la ventana de configuración inválido")
        self.configuration_focused = focused
        return
      if self.features.handle(request):
        self.emit("done", {"action": action})
        return
      if self.devices.handle(action, data):
        self.emit("done", {"action": action})
        return
      if self.bluetooth_manager.handle(action, data):
        self.emit("done", {"action": action})
        return
      if action == "night-sync":
        self.night.sync(force=data.get("force") is True)
        return
      if action == "system-refresh":
        refresh = {"power": lambda: self.devices.refresh("power"), "usb": lambda: self.devices.refresh("usb"), "night-light": lambda: self.night.sync(force=True), "battery": lambda: self.refresh_system(battery=True)}
        if data.get("name") not in refresh:
          raise ValueError("Servicio desconocido")
        refresh[data["name"]]()
        self.emit("done", {"action": action})
        return
      if self.captures.handle(action, data) or self.clipboard_manager.handle(action, data):
        self.emit("done", {"action": action})
        return
      if action == "history":
        if not isinstance(data, list) or len(data) > 500:
          raise ValueError("Historial inválido")
        cleaned = clean_history(data, self.store.settings["notificationHistoryLimit"])
        atomic_json(self.store.directory / "notifications.json", cleaned)
        return
      if action == "panel":
        if self.active_panel == "bluetooth" and data.get("name") != "bluetooth":
          self.bluetooth_manager.cancel()
          self.bluetooth_manager.stop_scan()
        self.active_panel = str(data.get("name", ""))
        self.sync_hardware()
        self.wakeup.set()
        refresh = {"wifi": self.refresh_network, "bluetooth": self.refresh_bluetooth,
             "clipboard": self.refresh_clipboard, "wallpapers": self.refresh_wallpapers}
        if self.active_panel in refresh and not (self.native_services and self.active_panel == "bluetooth"):
          self.queue_refresh(self.active_panel, refresh[self.active_panel])
        return
      if action == "outputs":
        names = data.get("names")
        if not isinstance(names, list) or len(names) > 32 or any(not isinstance(name, str) or len(name) > 128 for name in names):
          raise ValueError("Lista de monitores inválida")
        self.output_names = names
        self.sync_hardware()
        self.wakeup.set()
        return
      if action == "network-status":
        self.queue_refresh("wifi", self.refresh_network, latest=True)
        return
      if action in {"shortcut-list", "shortcut-conflicts"}:
        self.features.require_config(request)
        state = self.shortcut_state() if not self.preview else {"available": False, "bindings": [], "conflicts": []}
        self.emit("shortcut-state", state)
        self.emit("shortcut-conflicts", state["conflicts"])
        self.emit("done", {"action": action})
        return
      if action == "app-icons":
        names = data.get("names", [])
        if not isinstance(names, list) or len(names) > 3000 or any(not isinstance(name, str) for name in names):
          raise ValueError("Lista de iconos inválida")
        with self.icon_lock:
          if self.icon_resolver is None:
            self.icon_resolver = IconResolver(os.environ)
          self.emit("app-icons", self.icon_resolver.resolve(names))
        return
      if action == "refresh":
        name = data.get("name")
        refresh = {"wifi": lambda: self.refresh_network(True), "bluetooth": self.refresh_bluetooth,
             "clipboard": self.refresh_clipboard, "wallpapers": self.refresh_wallpapers}
        if name not in refresh:
          raise ValueError("Panel desconocido")
        refresh[name]()
        self.emit("done", {"action": action})
        return
      if self.preview:
        raise RuntimeError("La vista previa no modifica las conexiones ni la sesión")
      if action == "volume":
        command(["wpctl", "set-volume", "-l", "1", "@DEFAULT_AUDIO_SINK@", str(number(data.get("value"), 0, 1))])
      elif action == "mute":
        command(["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "toggle"])
      elif action == "brightness":
        value = int(number(data.get("value"), 1, 100))
        command(["brightnessctl", "set", f"{value}%"])
        self.refresh_system(brightness=True)
      elif action == "wifi-power":
        if not isinstance(data.get("enabled"), bool):
          raise ValueError("Estado Wi-Fi inválido")
        command(["nmcli", "radio", "wifi", "on" if data.get("enabled") is True else "off"])
        self.refresh_network()
      elif action == "wifi-connect":
        ssid = data.get("ssid")
        if not isinstance(ssid, str) or not ssid or len(ssid.encode()) > 32:
          raise ValueError("SSID inválido")
        interface = data.get("interface") or next((entry["interface"] for entry in self.networks if entry["ssid"] == ssid), "")
        if not isinstance(interface, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,32}", interface):
          raise ValueError("Selecciona una red con un adaptador Wi-Fi disponible")
        argv = ["nmcli", "--wait", "45", "device", "wifi", "connect", ssid, "ifname", interface]
        password = data.get("password", "")
        if not isinstance(password, str) or len(password) > 256 or "\0" in password:
          raise ValueError("Contraseña inválida")
        try:
          if password:
            security = next((entry["security"] for entry in self.networks if entry["ssid"] == ssid and entry["interface"] == interface), "")
            profile = self.wifi_secrets.prepare(ssid, interface, password, security)
            argv = ["nmcli", "--wait", "45", "connection", "up", "uuid", profile, "ifname", interface]
          command(argv, timeout=50)
        except (RuntimeError, ValueError) as error:
          detail = str(error).replace(password, "[oculta]") if password else str(error)
          raise RuntimeError("No se pudo conectar a la red: " + detail) from None
        self.refresh_network()
      elif action == "wifi-disconnect":
        interface = data.get("interface", "")
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,32}", interface):
          raise ValueError("Interfaz inválida")
        command(["nmcli", "device", "disconnect", interface])
        self.refresh_network()
      elif action == "workspace":
        workspace = int(number(data.get("id"), 1, 99))
        command(["hyprctl", "dispatch", f"hl.dsp.focus({{ workspace = {workspace} }})"])
      elif action == "screenshot":
        self.captures.capture(data)
      elif action == "session":
        self.session(data.get("command"), self.store.directory)
      elif action == "open-tool":
        tools = {"network": ["nm-connection-editor"], "bluetooth": ["blueman-manager"],
            "audio": ["pavucontrol"]}
        argv = tools.get(data.get("name"))
        if not argv or not shutil.which(argv[0]):
          raise RuntimeError("Instala el editor externo para usar esta opción")
        subprocess.Popen(argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
      elif action == "apply-shortcuts":
        self.features.require_config(request)
        if not self.shortcut_state()["available"]:
          raise ValueError("Carga bindings-prelude.lua antes de tus binds y hyprlarp.lua al final de hyprland.lua")
        executable = Path(os.environ.get("HYPRLARP_EXECUTABLE", str(ROOT / "bin/hyprlarp")))
        destination = self.store.directory / "bindings.lua"
        previous = read_regular(destination) if destination.exists() else None
        atomic_text(destination, generate_bindings(self.store.settings, executable))
        try:
          command(["hyprctl", "reload"])
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
          if previous is None:
            destination.unlink(missing_ok=True)
          else:
            atomic_bytes(destination, previous)
          raise
        self.emit("message", "Atajos aplicados; los binds existentes tienen prioridad")
      else:
        raise ValueError("Acción desconocida")
      self.emit("done", {"action": action})
    except (OSError, ValueError, TypeError, RuntimeError, subprocess.SubprocessError) as error:
      self.emit("action-error", {"action": action, "message": str(error)})
      self.emit("error", str(error))
      if action in SETTINGS_ACTIONS:
        self.emit("settings-rejected", {"action": action})
        self.emit_settings()
    finally:
      self.emit("idle", {"action": action})

  def shortcut_state(self):
    expression = 'HyprLarpBinds and HyprLarpBinds.snapshot() or [[{"available":false,"bindings":[],"conflicts":[]}]]'
    state = parse_json(command(["hyprctl", "repl", expression]))
    if not isinstance(state, dict) or not isinstance(state.get("available"), bool) or not isinstance(state.get("bindings"), list) or not isinstance(state.get("conflicts"), list) or len(state["bindings"]) > 1024:
      raise ValueError("Hyprland devolvió una lista de binds inválida")
    return state

  def screenshot(self, mode: str) -> None:
    self.captures.capture({"mode": mode})

  @staticmethod
  def session(name: str, directory: Path | None = None) -> None:
    if name == "lock":
      if not shutil.which("hyprlock"):
        raise RuntimeError("Instala hyprlock para bloquear la sesión")
      if directory is None:
        config_home = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
        directory = Path(os.environ.get("HYPRLARP_STATE_DIR", str(config_home / "hyprlarp")))
      configuration = directory / "generated-lock.conf"
      atomic_text(configuration, render_lock_config(Store(directory).settings))
      subprocess.Popen(["hyprlock", "--grace", "0", "--config", str(configuration)],
              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    elif name in {"poweroff", "reboot"}:
      command(["systemctl", name])
    elif name == "logout":
      command(["hyprctl", "dispatch", "hl.dsp.exit()"])
    elif name == "suspend":
      # hypridle's sleep inhibitor waits for the session-lock protocol before sleep.
      # Require our explicit config; an arbitrary idle daemon may not lock on sleep.
      import shlex
      if directory is None:
        raise RuntimeError("No se encontró la configuración de suspensión")
      expected = str(directory / "hypridle.conf")
      managed_idle = next(idle_processes(expected), None) is not None
      if not managed_idle or not Path(expected).is_file():
        raise RuntimeError("Inicia hypridle con el archivo hypridle.conf instalado por HyprLarp para suspender con bloqueo")
      command(["systemctl", "suspend"])
    else:
      raise ValueError("Acción de sesión desconocida")

  def serve(self) -> None:
    self.serving = True
    self.emit("modules", MODULE_DEFINITIONS)
    self.emit("palettes", PALETTES)
    self.features.startup()
    self.emit_settings()
    self.load_history()
    self.emit("power", {"available": False, "profiles": [], "profile": "", "error": ""})
    self.emit("usb", {"available": False, "drives": [], "devices": [], "error": ""})
    self.night.emit()
    if self.store.warning:
      self.emit("error", self.store.warning)
    self.sync_watchers()
    self.sync_hardware()
    self.queue_refresh("night-light", self.night.sync)
    polling = threading.Thread(target=self.poll, daemon=True)
    polling.start()
    try:
      while True:
        stream = getattr(sys.stdin, "buffer", sys.stdin)
        line = stream.readline(NOTIFICATION_JSON_LIMIT + 1)
        if not line:
          break
        try:
          if len(line) > NOTIFICATION_JSON_LIMIT:
            newline = b"\n" if isinstance(line, bytes) else "\n"
            while line and not line.endswith(newline):
              line = stream.readline(NOTIFICATION_JSON_LIMIT + 1)
            raise ValueError("La petición supera 16 MiB")
          request = parse_json(line)
          if not isinstance(request, dict) or not isinstance(request.get("action"), str) or len(request["action"]) > 64:
            raise ValueError("La petición no es un objeto JSON")
          if request["action"] != "history" and len(line) > JSON_LIMIT:
            raise ValueError("La petición supera 2 MiB")
          # Serialize persistence; slow device operations use workers.
          if request.get("action") in SETTINGS_ACTIONS | {"settings-context", "history", "panel", "network-status", "outputs", "profile-save", "profile-delete", "theme-save", "theme-delete", "settings-export", "bluetooth-respond", "bluetooth-cancel"}:
            self.action(request)
          elif request.get("action") == "refresh":
            data = request.get("data", {})
            name = data.get("name") if isinstance(data, dict) else None
            if isinstance(name, str) and name in {"wifi", "bluetooth", "clipboard", "wallpapers"}:
              if not self.queue_refresh("manual-" + name, lambda request=request: self.action(request)):
                self.emit("idle", {"action": "refresh"})
            else:
              self.action(request)
          else:
            try:
              self.executor.submit(self.action, request)
            except RuntimeError:
              self.emit("idle", {"action": request["action"]})
              raise
        except (ValueError, TypeError, RuntimeError) as error:
          self.emit("error", str(error))
    finally:
      self.serving = False
      self.stopping.set()
      self.wakeup.set()
      stop_processes()
      self.devices.stop()
      self.bluetooth_manager.close()
      self.backlight.stop()
      self.night.close()
      with self.watcher_lock:
        for watcher in self.watchers:
          if watcher.poll() is None:
            watcher.terminate()
      self.executor.shutdown(wait=False, cancel_futures=True)


def main() -> None:
  def terminate(signum, frame):
    raise SystemExit(0)
  signal.signal(signal.SIGTERM, terminate)
  os.umask(0o077)
  parser = argparse.ArgumentParser()
  parser.add_argument("--preview", action="store_true")
  parser.add_argument("--settings-only", action="store_true")
  parser.add_argument("--native-services", action="store_true")
  args = parser.parse_args()
  config = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
  directory = Path(os.environ.get("HYPRLARP_STATE_DIR", str(config / "hyprlarp")))
  Service(Store(directory), args.preview, args.settings_only, args.native_services).serve()


if __name__ == "__main__":
  main()
