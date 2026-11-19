"""On-demand, bounded local diagnostics; collecting a report changes no services."""

from __future__ import annotations

from datetime import datetime, timezone
import copy
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import shutil
import sys

try:
  from .persistence import atomic_json
  from .safety import bounded_process, read_json
except ImportError:
  from persistence import atomic_json
  from safety import bounded_process, read_json

REQUIRED = {"quickshell": "Interfaz", "hyprctl": "Hyprland"}
OPTIONAL = {"nmcli": "Wi-Fi", "bluetoothctl": "Bluetooth", "wpctl": "Audio", "brightnessctl": "Brillo",
  "cliphist": "Portapapeles", "wl-paste": "Captura del portapapeles", "wl-copy": "Copiar", "grim": "Capturas",
  "slurp": "Selección de región", "hyprpicker": "Captura estática", "hyprlock": "Bloqueo", "hypridle": "Bloqueo al suspender",
  "playerctl": "Multimedia", "nm-connection-editor": "Conexiones empresariales", "blueman-manager": "Editor Bluetooth",
  "powerprofilesctl": "Perfiles de energía", "hyprsunset": "Modo nocturno", "udisksctl": "Unidades USB",
  "waypaper": "Fondos externos", "mpvpaper": "Fondos de vídeo", "socat": "Control del vídeo",
  "magick": "Editor y miniaturas", "pw-play": "Sonidos de notificaciones"}


def redact(text):
  text = str(text).replace(str(Path.home()), "$HOME")
  text = re.sub(r"(?i)((?:password|passwd|token|secret|authorization)\s*[=:]\s*)[^\s,;]+", r"\1[oculto]", text)
  return text[-8192:]


def probe(argv):
  try:
    return True, redact(bounded_process(argv, timeout=2, limit=16 * 1024).decode(errors="replace").strip())
  except (OSError, ValueError, RuntimeError) as error:
    return False, redact(error)


def collect(root, *, directory=None, include_logs=True):
  root = Path(root)
  config = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
  directory = Path(directory or os.environ.get("HYPRLARP_STATE_DIR", config / "hyprlarp"))
  checks = [{"id": "python", "name": "Python", "required": True,
    "status": "ok" if sys.version_info >= (3, 11) else "error", "detail": platform.python_version() + " · mínimo 3.11"}]
  versions = {}
  for name, purpose in {**REQUIRED, **OPTIONAL}.items():
    path = shutil.which(name) or (shutil.which("qs") if name == "quickshell" else None)
    required = name in REQUIRED
    checks.append({"id": name, "name": name + " · " + purpose, "required": required,
      "status": "ok" if path else "error" if required else "optional", "detail": redact(path or "No instalado")})
  for name, argv in {"quickshell": [shutil.which("quickshell") or shutil.which("qs") or "quickshell", "--version"],
    "Hyprland": ["Hyprland", "--version"], "Qt": ["pkg-config", "--modversion", "Qt6Core"]}.items():
    if shutil.which(argv[0]):
      ok, detail = probe(argv)
      versions[name] = detail if ok else "No se pudo consultar: " + detail
      minimum = {"quickshell": (0, 3, 2), "Hyprland": (0, 57, 0)}.get(name)
      match = re.search(r"\b(\d+)\.(\d+)(?:\.(\d+))?", detail) if ok else None
      if minimum and match:
        actual = tuple(int(part or 0) for part in match.groups())
        checks.append({"id": "version-" + name, "name": "Versión de " + name, "required": True,
          "status": "ok" if actual >= minimum else "error",
          "detail": ".".join(map(str, actual)) + " · mínimo " + ".".join(map(str, minimum))})
  checks.append({"id": "python-gobject", "name": "Integración D-Bus de Python", "required": False,
    "status": "ok" if importlib.util.find_spec("gi") else "optional", "detail": "python-gobject"})
  runtime = Path(os.environ.get("XDG_RUNTIME_DIR", "/run/user/" + str(os.getuid())))
  display = os.environ.get("WAYLAND_DISPLAY", "")
  checks.append({"id": "wayland", "name": "Sesión Wayland", "required": False,
    "status": "ok" if display and (runtime / display).exists() else "warning", "detail": display or "No hay sesión gráfica disponible"})
  settings = directory / "settings.json"
  try:
    if not settings.exists():
      raise ValueError("Todavía no hay ajustes guardados")
    document = read_json(settings)
    if not isinstance(document, dict):
      raise ValueError("settings.json no es un objeto JSON")
    try:
      from .settings_schema import DEFAULTS, migrate_settings, validate_setting, validate_geometry, validate_combined
    except ImportError:
      from settings_schema import DEFAULTS, migrate_settings, validate_setting, validate_geometry, validate_combined
    candidate = copy.deepcopy(DEFAULTS)
    for key, value in migrate_settings(document).items():
      if key in DEFAULTS and key != "version":
        candidate[key] = validate_setting(key, value)
    validate_geometry(candidate)
    validate_combined(candidate)
    ok, detail = True, "Ajustes válidos · versión " + str(document.get("version", 1))
  except (OSError, ValueError, TypeError) as error:
    ok, detail = False, str(error)
  checks.append({"id": "settings", "name": "Configuración guardada", "required": False,
    "status": "ok" if ok else "warning", "detail": redact(detail)})
  services, logs = {}, {}
  if shutil.which("systemctl"):
    for unit in ("hyprlarp.service", "hyprpolkitagent.service"):
      ok, detail = probe(["systemctl", "--user", "show", unit, "--no-pager",
        "--property=LoadState,ActiveState,SubState,Result,NRestarts"])
      services[unit] = detail
      active = ok and "ActiveState=active" in detail
      checks.append({"id": unit, "name": unit, "required": False, "status": "ok" if active else "warning",
        "detail": detail if not active else "Servicio activo"})
  if os.environ.get("HYPRLAND_INSTANCE_SIGNATURE") and shutil.which("hyprctl"):
    ok, detail = probe(["hyprctl", "configerrors"])
    has_errors = detail.strip() not in {"", "ok", "No config errors"}
    checks.append({"id": "hyprland-config", "name": "Configuración de Hyprland", "required": False,
      "status": "ok" if ok and not has_errors else "warning", "detail": detail or "Sin errores"})
  installed = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "hyprlarp"
  ipc_root = root if (root / ".hyprlarp-install.json").is_file() else installed if installed.exists() else root
  binary = shutil.which("quickshell") or shutil.which("qs")
  health = {}
  if binary:
    ok, detail = probe([binary, "--path", str(ipc_root / "shell.qml"), "ipc", "show"])
    ipc_ready = ok and "target shell" in detail
    checks.append({"id": "ipc", "name": "Conexión con HyprLarp", "required": False,
      "status": "ok" if ipc_ready else "warning", "detail": "Canal del shell disponible" if ipc_ready else detail or "No hay una instancia activa"})
    if ok:
      available, state = probe([binary, "--path", str(ipc_root / "shell.qml"), "ipc", "call", "shell", "health"])
      if available:
        try:
          # Qt can print locale diagnostics before the compact IPC result.
          health = json.loads(state.rsplit("\n", 1)[-1])
          if not isinstance(health, dict):
            health = {}
        except ValueError:
          health = {}
        if health:
          ready = health.get("ready") is True and health.get("connected") is True
          checks.append({"id": "backend", "name": "Servicio de HyprLarp", "required": False,
            "status": "ok" if ready else "warning", "detail": "Interfaz y servicio conectados" if ready else "La interfaz está esperando al servicio"})
  if include_logs and shutil.which("journalctl"):
    ok, detail = probe(["journalctl", "--user", "-u", "hyprlarp.service", "-n", "20", "--no-pager", "-o", "cat"])
    logs["hyprlarp.service"] = detail
  return {"type": "hyprlarp-diagnostics", "version": 1, "time": datetime.now(timezone.utc).isoformat(),
    "platform": platform.system() + " " + platform.release(), "root": redact(root), "versions": versions,
    "checks": checks, "services": services, "logs": logs, "health": health,
    "ok": not any(check["required"] and check["status"] == "error" for check in checks)}


def export(report, path):
  path = Path(path).expanduser()
  atomic_json(path, report)
  return path


def render(report):
  lines = ["HyprLarp · Diagnóstico", ""]
  for check in report["checks"]:
    mark = {"ok": "✓", "error": "✗", "warning": "!", "optional": "·"}[check["status"]]
    lines.append(mark + " " + check["name"] + ": " + check["detail"].replace("\n", " · "))
  lines.extend(["", "Versiones:"] + [name + ": " + detail.replace("\n", " ")[:400] for name, detail in report["versions"].items()])
  return "\n".join(lines)
