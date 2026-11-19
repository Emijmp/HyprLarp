"""Settings schema, migrations and geometry validation, independent of the service."""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import re

try:
  from .layouts import synchronize_layout, validate_monitor_bars, validate_zones, zones_for
  from .shortcuts import chord_parts, chord_key, validate_custom, validate_combined
  from .wallpapers import EXTENSIONS, local_path
except ImportError:
  from layouts import synchronize_layout, validate_monitor_bars, validate_zones, zones_for
  from shortcuts import chord_parts, chord_key, validate_custom, validate_combined
  from wallpapers import EXTENSIONS, local_path

ROOT = Path(__file__).resolve().parents[1]
MODULE_DEFINITIONS = json.loads((ROOT / "config/modules.json").read_text())
MODULES = {entry["id"] for entry in MODULE_DEFINITIONS}
PANELS = {entry["target"] for entry in MODULE_DEFINITIONS if entry["kind"] == "panel"} | {"settings", "navigation"}
PALETTES = json.loads((ROOT / "config/palettes.json").read_text())
THEMES = set(PALETTES) | {"custom"}
COLOR_ROLES = set(PALETTES["amoled"]) - {"name"}
SETTINGS_ACTIONS = {"settings", "settings-undo", "settings-redo", "settings-reset", "settings-reset-section", "profile-apply", "settings-import", "theme-use", "settings-restore-revision"}
SETTINGS_HISTORY_LIMIT = 50
# 500 normalized notices can exceed the ordinary IPC budget with UTF-8 or escapes.
# History is persisted synchronously, so this allowance never enters the work queue.
NOTIFICATION_JSON_LIMIT = 16 * 1024 * 1024
DEFAULTS = json.loads((ROOT / "config/defaults.json").read_text())
COMMAND_PROFILE = os.environ.get("HYPRLARP_COMMAND_PROFILE", "")


def number(value: Any, low: float, high: float) -> float:
  if isinstance(value, bool) or not isinstance(value, (int, float)):
    raise ValueError("Se esperaba un número")
  if not low <= value <= high:
    raise ValueError(f"El valor debe estar entre {low} y {high}")
  return value


def validate_setting(key: str, value: Any) -> Any:
  if key not in DEFAULTS or key == "version":
    raise ValueError("Ajuste desconocido")
  if key == "accessibilityTextScale":
    return number(value, 1, 2)
  if key == "accessibilityMinimumFontSize":
    return int(number(value, 10, 18))
  if key in {"accessibilityHighContrast", "accessibilityReducedMotion", "accessibilityLargeTargets", "themeScheduleEnabled", "panelBlur"}:
    if not isinstance(value, bool):
      raise ValueError("Se esperaba verdadero o falso")
    return value
  if key in {"clockSeconds", "calendarWeekNumbers", "batteryAlertsEnabled", "animations", "doNotDisturb", "clipboardEnabled", "clipboardPaused", "osdEnabled", "nightLightEnabled", "nightLightSchedule", "barEnabled", "barReserveSpace", "barBlur", "barShowLabels", "showAppIcons", "migrateNoctaliaBinds", "waypaperRestoreOnStartup", "windowGapsEnabled", "windowGapsLinked"}:
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
  elif key == "greeterLayout":
    if not isinstance(value, str) or value not in {"sidebar", "centered"}:
      raise ValueError("Diseño de inicio de sesión desconocido")
  elif key == "panelLayout":
    if value not in {"floating", "centered", "sidebar"}:
      raise ValueError("Diseño de panel desconocido")
  elif key == "panelStyle":
    if value not in {"standard", "glass", "flat"}:
      raise ValueError("Estilo de panel desconocido")
  elif key == "performanceMode":
    if value not in {"efficient", "balanced", "responsive"}:
      raise ValueError("Perfil de rendimiento desconocido")
  elif key == "clockFormat":
    if not isinstance(value, str) or value not in {"12h", "24h"}:
      raise ValueError("Elige formato de 12 o 24 horas")
  elif key == "clockDateFormat":
    if not isinstance(value, str) or value not in {"dd/MM", "dd/MM/yyyy", "MM/dd/yyyy", "yyyy-MM-dd", "ddd, d MMM"}:
      raise ValueError("Formato de fecha desconocido")
  elif key == "calendarFirstDay":
    if not isinstance(value, str) or value not in {"monday", "sunday"}:
      raise ValueError("Elige lunes o domingo")
  elif key == "batteryAlertLevels":
    if not isinstance(value, dict) or set(value) != {"low", "critical"}:
      raise ValueError("Indica los niveles bajo y crítico de batería")
    value = {name: int(number(level, 1, 99)) for name, level in value.items()}
    if value["critical"] >= value["low"]:
      raise ValueError("El nivel crítico debe ser menor que el nivel bajo")
  elif key in {"nightLightStart", "nightLightEnd", "themeDayStart", "themeNightStart"}:
    if not isinstance(value, str) or not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value):
      raise ValueError("Usa una hora de 00:00 a 23:59")
  elif key == "cornerRadii":
    allowed = {"bar", "panel", "button", "field", "workspace", "notification", "tooltip"}
    if not isinstance(value, dict) or set(value) - allowed:
      raise ValueError("Tipo de elemento desconocido para la redondez")
    value = {kind: int(number(radius, 0, 8)) for kind, radius in value.items()}
  elif key in {"barMargin", "barPaddingX", "barPaddingY", "barSpacing"}:
    value = int(number(value, 0, 64))
  elif key == "windowGapsIn":
    value = int(number(value, 0, 64))
  elif key == "windowGapsOut":
    if not isinstance(value, dict) or set(value) != {"top", "right", "bottom", "left"}:
      raise ValueError("Indica los cuatro bordes de la pantalla")
    value = {edge: int(number(gap, 0, 128)) for edge, gap in value.items()}
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
  elif key in {"themeDay", "themeNight"}:
    if value not in THEMES - {"custom"}:
      raise ValueError("Elige un tema guardado para el horario")
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
  elif key == "wallpaperProvider":
    if not isinstance(value, str) or value not in {"internal", "external"}:
      raise ValueError("Gestor de fondos desconocido")
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
  custom_chords = set()
  custom = migrated.get("customBindings", [])
  for entry in custom if isinstance(custom, list) else []:
    if isinstance(entry, dict) and entry.get("enabled", True) is True:
      try:
        custom_chords.add(shortcut_key(entry.get("chord")))
      except (ValueError, TypeError):
        pass
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
      used.update(custom_chords)
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
    used.update(custom_chords)
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
