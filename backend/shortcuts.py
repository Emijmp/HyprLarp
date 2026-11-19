"""Validate owned binds and render data for the non-blocking Lua bind manager."""

import re
import shlex

MODIFIERS = {"SUPER", "SHIFT", "CTRL", "ALT", "MOD1", "MOD2", "MOD3", "MOD4", "MOD5"}
LEGACY = {"panel-toggle launcher": "launcher", "panel-toggle control-center": "control",
  "settings-toggle": "settings", "panel-toggle session": "session", "panel-toggle clipboard": "clipboard",
  "screenshot-region": "screenshot-region", "screenshot-screen": "screenshot-screen"}
MEDIA = {"volume-up": "wpctl set-volume -l 1 @DEFAULT_AUDIO_SINK@ 5%+",
  "volume-down": "wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%-", "volume-mute": "wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle",
  "brightness-up": "brightnessctl set +5%", "brightness-down": "brightnessctl set 5%-"}


def chord_parts(value):
  if not isinstance(value, str) or len(value) > 128 or not re.fullmatch(r"[A-Za-z0-9_ +]*,\s*(?:[A-Za-z0-9_]+|(?:mouse|code):[0-9]+)", value):
    raise ValueError("Formato de atajo: SUPER SHIFT, S")
  modifiers, key = value.replace("+", " ").split(",", 1)
  modifiers = modifiers.upper().split()
  if set(modifiers) - MODIFIERS:
    raise ValueError("Modificador de teclado desconocido")
  modifiers = sorted({{"MOD4": "SUPER", "MOD1": "ALT"}.get(mod, mod) for mod in modifiers})
  return modifiers, key.strip()


def chord_key(value):
  modifiers, key = chord_parts(value)
  return tuple(modifiers), key.upper()


def validate_custom(value, actions):
  if not isinstance(value, list) or len(value) > 128:
    raise ValueError("Puedes guardar hasta 128 binds personalizados")
  result, ids, sources = [], set(), set()
  allowed = {"id", "name", "chord", "type", "action", "command", "source", "enabled", "repeat", "locked", "release", "replace"}
  for entry in value:
    if not isinstance(entry, dict) or set(entry) - allowed:
      raise ValueError("Bind personalizado inválido")
    ident = entry.get("id")
    if not isinstance(ident, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", ident) or ident in ids:
      raise ValueError("Identificador de bind inválido o duplicado")
    ids.add(ident)
    name = entry.get("name", "")
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 80 or any(ord(c) < 32 for c in name):
      raise ValueError("Escribe un nombre de entre 1 y 80 caracteres")
    mods, key = chord_parts(entry.get("chord"))
    kind = entry.get("type")
    if kind not in {"command", "shell", "inherit"}:
      raise ValueError("Tipo de acción desconocido")
    source = entry.get("source", "")
    if not isinstance(source, str) or len(source) > 512 or any(ord(c) < 32 for c in source):
      raise ValueError("Origen de bind inválido")
    if source:
      if source in sources:
        raise ValueError("Un bind actual solo puede tener una personalización")
      sources.add(source)
    if kind == "inherit" and not source:
      raise ValueError("Selecciona el bind actual que quieres modificar")
    command, action = entry.get("command", ""), entry.get("action", "")
    if not isinstance(command, str) or len(command) > 4096 or any(ord(c) < 32 for c in command):
      raise ValueError("El comando debe estar en una sola línea y tener hasta 4096 caracteres")
    if kind == "command" and not command.strip():
      raise ValueError("Escribe el comando que ejecutará el bind")
    if not isinstance(action, str) or (kind == "shell" and action not in actions):
      raise ValueError("Acción del shell desconocida")
    flags = {flag: entry.get(flag, flag == "enabled") for flag in ("enabled", "repeat", "locked", "release", "replace")}
    if any(not isinstance(flag, bool) for flag in flags.values()):
      raise ValueError("Las opciones del bind deben ser booleanas")
    result.append({"id": ident, "name": name.strip(), "chord": " ".join(mods) + ", " + key,
      "type": kind, "action": action if kind == "shell" else "", "command": command if kind == "command" else "",
      "source": source, **flags})
  return result


def validate_combined(settings):
  used = {chord_key(chord) for chord in settings["shortcuts"].values() if chord}
  for entry in settings["customBindings"]:
    if not entry["enabled"]:
      continue
    key = chord_key(entry["chord"])
    if key in used:
      raise ValueError("Hay combinaciones duplicadas entre el shell y los binds personalizados")
    used.add(key)


def invocation(action, executable):
  arguments = [str(executable)]
  arguments += [action] if action in {"settings", "lock", "screenshot-region", "screenshot-region-frozen", "screenshot-window", "screenshot-screen"} else ["toggle", action]
  return shlex.join(arguments)


def lua_value(value):
  # JSON strings are valid Lua strings after escaping UTF-8 control sequences.
  if isinstance(value, str):
    return '"' + "".join("\\" + c if c in {'"', "\\"} else "\\%03d" % ord(c) if ord(c) < 32 else c for c in value) + '"'
  if isinstance(value, bool):
    return "true" if value else "false"
  if isinstance(value, dict):
    return "{ " + ", ".join("[" + lua_value(key) + "] = " + lua_value(item) for key, item in value.items()) + " }"
  if isinstance(value, list):
    return "{\n" + ",\n".join("  " + lua_value(item) for item in value) + "\n}"
  raise ValueError("Valor no admitido en los binds")


def render(settings, executable):
  validate_combined(settings)
  definitions = [{"id": "shell-" + action, "name": action, "chord": chord, "type": "command",
    "command": invocation(action, executable), "source": "", "enabled": True,
    "repeat": False, "locked": False, "release": False, "replace": False}
    for action, chord in settings["shortcuts"].items() if chord]
  for entry in settings["customBindings"]:
    item = dict(entry)
    if item["type"] == "shell":
      item["type"], item["command"] = "command", invocation(item["action"], executable)
    definitions.append(item)
  legacy = {tail: invocation(action, executable) for tail, action in LEGACY.items()}
  legacy.update(MEDIA)
  return "-- Generated by HyprLarp. Configure binds from the settings app.\n" \
    + "local manager = rawget(_G, \"HyprLarpBinds\")\n" \
    + "if not manager then\n  print(\"HyprLarp: carga bindings-prelude.lua antes de tus binds\")\n  return\nend\n" \
    + "manager.apply(" + lua_value(definitions) + ", " + lua_value(legacy) + ", " + lua_value(settings["migrateNoctaliaBinds"]) + ", " + lua_value(LEGACY) + ")\n"
