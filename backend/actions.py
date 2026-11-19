"""Explicit system mutations, separate from settings and read-only queries."""

import re


class SystemActions:
  NAMES = {"volume", "mute", "brightness", "wifi-power", "wifi-connect", "wifi-disconnect", "workspace", "screenshot", "session", "open-tool", "waypaper-restore", "apply-window-gaps", "apply-shortcuts"}

  def __init__(self, service, api):
    self.s, self.api = service, api

  def handle(self, action, data, request):
    if action not in self.NAMES:
      return False
    s, api = self.s, self.api
    if s.preview:
      raise RuntimeError("La vista previa no modifica las conexiones ni la sesión")
    if action == "volume":
      api.command(["wpctl", "set-volume", "-l", "1", "@DEFAULT_AUDIO_SINK@", str(api.number(data.get("value"), 0, 1))])
    elif action == "mute":
      api.command(["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "toggle"])
    elif action == "brightness":
      value = int(api.number(data.get("value"), 1, 100))
      api.command(["brightnessctl", "set", f"{value}%"])
      s.refresh_system(brightness=True)
    elif action == "wifi-power":
      if not isinstance(data.get("enabled"), bool):
        raise ValueError("Estado Wi-Fi inválido")
      api.command(["nmcli", "radio", "wifi", "on" if data.get("enabled") is True else "off"])
      s.refresh_network()
    elif action == "wifi-connect":
      ssid = data.get("ssid")
      if not isinstance(ssid, str) or not ssid or len(ssid.encode()) > 32:
        raise ValueError("SSID inválido")
      interface = data.get("interface") or next((entry["interface"] for entry in s.networks if entry["ssid"] == ssid), "")
      if not isinstance(interface, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,32}", interface):
        raise ValueError("Selecciona una red con un adaptador Wi-Fi disponible")
      argv = ["nmcli", "--wait", "45", "device", "wifi", "connect", ssid, "ifname", interface]
      password = data.get("password", "")
      if not isinstance(password, str) or len(password) > 256 or "\0" in password:
        raise ValueError("Contraseña inválida")
      try:
        if password:
          security = next((entry["security"] for entry in s.networks if entry["ssid"] == ssid and entry["interface"] == interface), "")
          profile = s.wifi_secrets.prepare(ssid, interface, password, security)
          argv = ["nmcli", "--wait", "45", "connection", "up", "uuid", profile, "ifname", interface]
        api.command(argv, timeout=50)
      except (RuntimeError, ValueError) as error:
        detail = str(error).replace(password, "[oculta]") if password else str(error)
        raise RuntimeError("No se pudo conectar a la red: " + detail) from None
      s.refresh_network()
    elif action == "wifi-disconnect":
      interface = data.get("interface", "")
      if not re.fullmatch(r"[A-Za-z0-9_.-]{1,32}", interface):
        raise ValueError("Interfaz inválida")
      api.command(["nmcli", "device", "disconnect", interface])
      s.refresh_network()
    elif action == "workspace":
      workspace = int(api.number(data.get("id"), 1, 99))
      api.command(["hyprctl", "dispatch", f"hl.dsp.focus({{ workspace = {workspace} }})"])
    elif action == "screenshot":
      s.captures.capture(data)
    elif action == "session":
      s.session(data.get("command"), s.store.directory)
    elif action == "open-tool":
      tools = {"network": ["nm-connection-editor"], "bluetooth": ["blueman-manager"],
          "audio": ["pavucontrol"], "waypaper": ["waypaper"]}
      argv = tools.get(data.get("name"))
      if not argv or not api.shutil.which(argv[0]):
        raise RuntimeError("Instala el editor externo para usar esta opción")
      api.subprocess.Popen(argv, stdout=api.subprocess.DEVNULL, stderr=api.subprocess.DEVNULL, start_new_session=True)
    elif action == "waypaper-restore":
      s.restore_waypaper()
    elif action == "apply-window-gaps":
      s.features.require_config(request)
      if not s.window_gaps.sync():
        raise RuntimeError("No se pudo aplicar la separación de ventanas; revisa el mensaje en Apariencia")
    elif action == "apply-shortcuts":
      s.features.require_config(request)
      if not s.shortcut_state()["available"]:
        raise ValueError("Carga bindings-prelude.lua antes de tus binds y hyprlarp.lua al final de hyprland.lua")
      executable = api.Path(api.os.environ.get("HYPRLARP_EXECUTABLE", str(api.ROOT / "bin/hyprlarp")))
      destination = s.store.directory / "bindings.lua"
      previous = api.read_regular(destination) if destination.exists() else None
      api.atomic_text(destination, api.generate_bindings(s.store.settings, executable))
      try:
        api.command(["hyprctl", "reload"])
      except (OSError, ValueError, RuntimeError, api.subprocess.SubprocessError):
        if previous is None:
          destination.unlink(missing_ok=True)
        else:
          api.atomic_bytes(destination, previous)
        raise
      s.emit("message", "Atajos aplicados; los binds existentes tienen prioridad")
    else:
      raise ValueError("Acción desconocida")
    return True
