"""Bar layouts, section resets and portable configuration selections."""

import copy

ZONES = ("start", "center", "end")
BAR_KEYS = {"barEnabled", "barPosition", "barSize", "barMargins", "barPaddingX", "barPaddingY",
  "barSpacing", "barBorderWidth", "barLength", "barAlignment", "barReserveSpace", "barBlur",
  "barWorkspaceDisplay", "barFontSize", "barIconSize", "barShowLabels", "barWorkspaceCount", "barOpacity", "barModules",
  "barZones", "moduleOpacity", "moduleBackgroundOpacity", "moduleBorderWidth", "modulePaddingX",
  "modulePaddingY", "moduleRadius", "moduleOpacities"}
SECTIONS = {
  "Appearance": {"decoration", "theme", "accent", "customPalette", "font", "radius", "cornerRadii", "panelOpacity", "animations"},
  "Bar": {key for key in BAR_KEYS if key.startswith("bar") and key not in {"barModules", "barZones"}},
  "Modules": {"barModules", "barZones", "disabledModules", "moduleOpacity", "moduleOpacities",
    "moduleBackgroundOpacity", "moduleBorderWidth", "modulePaddingX", "modulePaddingY", "moduleRadius", "trayHiddenItems"},
  "Wallpapers": {"wallpaper", "wallpaperDirectory"},
  "Shortcuts": {"shortcuts"},
  "General": {"osdEnabled", "osdTimeout", "osdPosition", "nightLightEnabled", "nightLightTemperature", "nightLightSchedule", "nightLightStart", "nightLightEnd", "clipboardEnabled", "clipboardPaused", "clipboardRetentionHours", "notificationHistoryLimit",
    "notificationRules", "showAppIcons"}
}


def validate_zones(value, modules):
  if not isinstance(value, dict) or set(value) != set(ZONES):
    raise ValueError("Indica las tres zonas: inicio, centro y final")
  selected = []
  for names in value.values():
    if not isinstance(names, list) or any(not isinstance(name, str) or name not in modules for name in names):
      raise ValueError("Módulo desconocido en la zona")
    selected += names
  if len(selected) != len(set(selected)):
    raise ValueError("Un módulo solo puede pertenecer a una zona")
  return copy.deepcopy(value)


def zones_for(modules):
  # Legacy lists keep their order until the user assigns explicit zones.
  return {"start": list(modules), "center": [], "end": []}


def flatten(zones):
  return [name for zone in ZONES for name in zones[zone]]


def synchronize_layout(current, updates):
  result = {**current, **updates}
  if "barZones" in updates:
    selected = flatten(updates["barZones"])
    if "barModules" in updates and set(selected) != set(updates["barModules"]):
      raise ValueError("La lista de módulos debe coincidir con las zonas")
    result["barModules"] = selected
  elif "barModules" in updates:
    result["barZones"] = zones_for(updates["barModules"])
  return result


def validate_monitor_bars(value, validate):
  if not isinstance(value, dict) or len(value) > 16:
    raise ValueError("Configuración por monitor inválida")
  result = {}
  for name, overrides in value.items():
    if not isinstance(name, str) or not 1 <= len(name) <= 128 or any(ord(c) < 32 for c in name):
      raise ValueError("Nombre de monitor inválido")
    if not isinstance(overrides, dict) or set(overrides) - BAR_KEYS:
      raise ValueError("Solo se admiten ajustes de barra por monitor")
    result[name] = {key: validate(key, item) for key, item in overrides.items()}
    if "barZones" in overrides:
      result[name] = synchronize_layout(result[name], {"barZones": result[name]["barZones"]})
    elif "barModules" in overrides:
      result[name]["barZones"] = zones_for(result[name]["barModules"])
  return result


def section_updates(section, defaults, settings, monitor=""):
  if section not in SECTIONS:
    raise ValueError("Sección desconocida")
  keys = SECTIONS[section] & defaults.keys()
  if monitor:
    if section not in {"Bar", "Modules"}:
      raise ValueError("Esa sección no tiene ajustes por monitor")
    bars = copy.deepcopy(settings["monitorBars"])
    override = bars.get(monitor, {})
    for key in keys:
      override.pop(key, None)
    if override:
      bars[monitor] = override
    else:
      bars.pop(monitor, None)
    return {"monitorBars": bars}
  return {key: copy.deepcopy(defaults[key]) for key in keys}
