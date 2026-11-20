#!/usr/bin/env python3
"""A JSON-lines bridge with a standard-library core and optional GIO devices."""

from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
import signal
import shutil
import subprocess
import sys
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
  from .battery_alerts import BatteryAlerts
  from .faults import FaultRegistry
  from .performance import Performance
  from .udev import UdevEvents
  from .devices import Devices
  from .night import NightLight
  from .wallpapers import EXTENSIONS, catalogue, local_path
  from .wallpaper_palette import PaletteExtractor
  from .theme_context import effective_name
  from .bluetooth import BluetoothManager
  from .wifi import WifiSecrets
  from .gaps import WindowGaps, values as window_gaps_values
  from .displays import Displays
  from .shortcuts import chord_parts, chord_key, validate_custom, validate_combined, render as render_bindings
  from .safety import BoundedExecutor, JSON_LIMIT, bounded_process, private_directory, read_json, read_regular, stop_processes, idle_processes, parse_json
else:
  from icons import IconResolver
  from layouts import BAR_KEYS, flatten, section_updates, synchronize_layout, validate_monitor_bars, validate_zones, zones_for
  from features import Features
  from clipboard import Clipboard
  from captures import Captures
  from battery import battery_state
  from battery_alerts import BatteryAlerts
  from faults import FaultRegistry
  from performance import Performance
  from udev import UdevEvents
  from devices import Devices
  from night import NightLight
  from wallpapers import EXTENSIONS, catalogue, local_path
  from wallpaper_palette import PaletteExtractor
  from theme_context import effective_name
  from bluetooth import BluetoothManager
  from wifi import WifiSecrets
  from gaps import WindowGaps, values as window_gaps_values
  from displays import Displays
  from shortcuts import chord_parts, chord_key, validate_custom, validate_combined, render as render_bindings
  from safety import BoundedExecutor, JSON_LIMIT, bounded_process, private_directory, read_json, read_regular, stop_processes, idle_processes, parse_json

try:
  from .settings_schema import ROOT, MODULE_DEFINITIONS, MODULES, PANELS, PALETTES, THEMES, COLOR_ROLES, SETTINGS_ACTIONS, SETTINGS_HISTORY_LIMIT, NOTIFICATION_JSON_LIMIT, DEFAULTS, COMMAND_PROFILE, number, validate_setting, migrate_settings, shortcut_key, geometry_minimum, validate_geometry
  from .persistence import atomic_bytes, atomic_text, atomic_json
  from .settings_store import Store as SettingsStore
  from .onboarding import Onboarding
  from .version import VERSION
except ImportError:
  from settings_schema import ROOT, MODULE_DEFINITIONS, MODULES, PANELS, PALETTES, THEMES, COLOR_ROLES, SETTINGS_ACTIONS, SETTINGS_HISTORY_LIMIT, NOTIFICATION_JSON_LIMIT, DEFAULTS, COMMAND_PROFILE, number, validate_setting, migrate_settings, shortcut_key, geometry_minimum, validate_geometry
  from persistence import atomic_bytes, atomic_text, atomic_json
  from settings_store import Store as SettingsStore
  from onboarding import Onboarding
  from version import VERSION


class Store(SettingsStore):
  # Keep the existing public import and injectable writer used by integrations.
  def __init__(self, directory: Path):
    super().__init__(directory, writer=lambda path, value: atomic_json(path, value))


def palette_for(settings: dict) -> dict:
  return settings["customPalette"] if settings["theme"] == "custom" else PALETTES[settings["theme"]]


def render_lock_config(settings: dict, **options) -> str:
  if __package__:
    from .lockscreen import render
  else:
    from lockscreen import render
  return render(settings, PALETTES, **options)


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


try:
  from .metrics import Metrics, brightness_state, poll_intervals
except ImportError:
  from metrics import Metrics, brightness_state, poll_intervals


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
    self.onboarding = Onboarding(store.directory, ROOT, automatic=not preview and not settings_only)
    self.native_services = native_services
    self.serving = False
    self.output_lock = threading.Lock()
    self.stopping = threading.Event()
    self.wakeup = threading.Event()
    self.metrics = Metrics()
    self.performance = Performance(ROOT, store.directory, preview=preview, settings_only=settings_only)
    self.wallpaper_palette = PaletteExtractor()
    self.synced_context_theme = None
    self.battery_alerts = BatteryAlerts(store.directory)
    scopes = {'panel:' + name for name in PANELS} | {'bar:' + name for name in MODULES}
    scopes |= {'page:' + name for name in ['Appearance', 'Bar', 'Modules', 'Wallpapers', 'Shortcuts', 'General', 'Profiles', 'Displays']}
    scopes |= {'backend:' + name for name in ['wifi', 'bluetooth', 'wallpapers', 'clipboard', 'metrics', 'brightness', 'battery', 'network', 'displays', 'night-light', 'window-gaps', 'usb', 'power', 'waypaper-restore', 'performance']}
    self.faults = FaultRegistry(store.directory, scopes)
    self.system_lock = threading.Lock()
    self.system = {"user": os.environ.get("USER", "tú"), "hostname": os.uname().nodename}
    self.snapshot_lock = threading.Lock()
    self.snapshots = {}
    self.watchers: list[subprocess.Popen] = []
    self.watcher_lock = threading.RLock()
    self.watcher_slots = {}
    self.watcher_started = {}
    self.watcher_failures = {}
    self.watcher_retry = {}
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
    self.launcher_search = None
    self.executor = BoundedExecutor(max_workers=3, pending=12)
    if __package__:
      from .actions import SystemActions
    else:
      from actions import SystemActions
    self.system_actions = SystemActions(self, sys.modules[__name__])
    self.features = Features(self, sys.modules[__name__])
    self.clipboard_manager = Clipboard(self, sys.modules[__name__])
    self.captures = Captures(self, sys.modules[__name__])
    self.devices = Devices(self)
    self.bluetooth_manager = BluetoothManager(self)
    self.wifi_secrets = WifiSecrets()
    self.window_gaps = WindowGaps(self, sys.modules[__name__])
    self.displays = Displays(self, sys.modules[__name__])
    self.night = NightLight(self, sys.modules[__name__])
    self.backlight = UdevEvents("backlight", lambda: self.queue_refresh("brightness-event", lambda: self.refresh_system(brightness=True), latest=True))

  def emit(self, kind: str, data: Any) -> None:
    with self.output_lock:
      try:
        print(json.dumps({"type": kind, "data": data}, ensure_ascii=False, separators=(",", ":")), flush=True)
      except (BrokenPipeError, OSError):
        self.stopping.set()
        self.wakeup.set()

  def emit_changed(self, kind: str, data: Any) -> None:
    with self.snapshot_lock:
      if self.snapshots.get(kind) != data:
        self.snapshots[kind] = copy.deepcopy(data)
        self.emit(kind, data)

  def sync_theme_context(self):
    """Reuse the installed oneshot bridge only when the effective theme changes."""
    if self.preview or self.settings_only or self.stopping.is_set():
      return
    name = effective_name(self.store.settings)
    if name == self.synced_context_theme:
      return
    config = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config'))
    unit = config / 'systemd/user/hyprlarp-greeter-sync.service'
    if not unit.is_file() or unit.is_symlink():
      return
    command(['systemctl', '--user', 'start', '--no-block', 'hyprlarp-greeter-sync.service'], timeout=3)
    self.synced_context_theme = name

  def queue_refresh(self, name: str, function, latest: bool = False) -> bool:
    """One worker per source, with at most one coalesced follow-up for events."""
    if self.faults.blocked('backend:' + name):
      return False
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
        self.safe_refresh(current, scope='backend:' + name)
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
    self.emit_changed("wallpaper-tools", {name: bool(shutil.which(name)) for name in ("waypaper", "mpvpaper", "socat")})
    if self.store.settings["wallpaperProvider"] == "external":
      self.emit_changed("wallpapers", [])
      return
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
      if battery and not self.preview and not self.settings_only:
        alert = self.battery_alerts.update(self.system["battery"], self.store.settings)
        if alert:
          self.emit("battery-alert", alert)

  def restore_waypaper(self):
    if self.preview:
      raise RuntimeError("La vista previa no restaura fondos externos")
    if self.store.settings["wallpaperProvider"] != "external":
      raise ValueError("Selecciona Externo en Fondos antes de restaurar Waypaper")
    command(["waypaper", "--restore"], timeout=15)
    self.emit("message", "Fondo restaurado mediante Waypaper")

  def refresh_performance(self):
    with self.performance.lock:
      if self.performance.open and not self.performance.paused:
        self.emit('performance', self.performance.sample(self.store.settings))

  def start_external_wallpaper(self):
    if not self.preview and not self.settings_only and self.store.settings["wallpaperProvider"] == "external" and self.store.settings["waypaperRestoreOnStartup"]:
      self.queue_refresh("waypaper-restore", self.restore_waypaper)

  def load_history(self) -> None:
    try:
      history = read_json(self.store.directory / "notifications.json", limit=NOTIFICATION_JSON_LIMIT)
      self.emit("history", clean_history(history, self.store.settings["notificationHistoryLimit"]) if isinstance(history, list) else [])
    except (OSError, ValueError):
      self.emit("history", [])

  def stop_watchers(self) -> None:
    with self.watcher_lock:
      watchers, self.watchers = self.watchers, []
      self.watcher_slots.clear()
      self.watcher_started.clear()
      self.watcher_failures.clear()
      self.watcher_retry.clear()
      for watcher in watchers:
        try:
          if watcher.poll() is None:
            watcher.terminate()
          try:
            watcher.wait(timeout=0.3)
          except subprocess.TimeoutExpired:
            watcher.kill()
            watcher.wait(timeout=1)
        except (OSError, subprocess.TimeoutExpired):
          pass

  def sync_watchers(self) -> float | None:
    with self.watcher_lock:
      enabled = self.store.settings["clipboardEnabled"] and not self.store.settings["clipboardPaused"] and not self.preview and not self.settings_only and not self.stopping.is_set()
      if not enabled:
        self.stop_watchers()
        return None
      now = time.monotonic()
      for mime, watcher in list(self.watcher_slots.items()):
        if watcher.poll() is None:
          continue
        self.watchers.remove(watcher)
        del self.watcher_slots[mime]
        if now - self.watcher_started.pop(mime, now) >= 30:
          self.watcher_failures[mime] = 0
        self.watcher_failures[mime] = min(6, self.watcher_failures.get(mime, 0) + 1)
        self.watcher_retry[mime] = now + min(60, 2 ** self.watcher_failures[mime])
      if len(self.watcher_slots) < 2 and (not shutil.which("wl-paste") or not shutil.which("cliphist")):
        return 30
      for mime in ["text", "image"]:
        if mime in self.watcher_slots or now < self.watcher_retry.get(mime, 0):
          continue
        try:
          watcher = subprocess.Popen([sys.executable, str(ROOT / "backend/child.py"), str(os.getpid()), "wl-paste", "--type", mime, "--watch", sys.executable, str(ROOT / "backend/clipboard_store.py")],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError as error:
          self.watcher_failures[mime] = min(6, self.watcher_failures.get(mime, 0) + 1)
          self.watcher_retry[mime] = now + min(60, 2 ** self.watcher_failures[mime])
          self.emit("error", "No se pudo iniciar el portapapeles: " + str(error))
          continue
        self.watchers.append(watcher)
        self.watcher_slots[mime] = watcher
        self.watcher_started[mime] = now
        self.watcher_retry.pop(mime, None)
      # Share existing scheduler wakes for two cheap waitpid probes. Otherwise
      # check every 30 seconds, or sooner for a retry, without monitor threads.
      retry = min(self.watcher_retry.values(), default=now + 30)
      return max(0.05, min(30, retry - now))

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

  def polling_plan(self):
    plan = poll_intervals(self.store.settings, self.active_panel, self.settings_only, self.native_services, self.output_names)
    if self.performance.paused:
      plan.pop('performance', None)
    return plan

  def refresh_polled(self, name, function):
    # A device operation may keep a worker busy until after its panel closes.
    # Recheck demand when the queued read actually gets a worker.
    if not self.stopping.is_set() and name in self.polling_plan():
      function()

  def poll(self) -> None:
    due, previous = {}, {}
    while not self.stopping.is_set():
      self.wakeup.clear()
      watcher_timeout = self.sync_watchers()
      plan = self.polling_plan()
      now = time.monotonic()
      for name in set(due) - set(plan):
        del due[name]
        if name == "metrics":
          with self.system_lock:
            self.metrics.previous_cpu = None
            self.metrics.previous_network = None
        if name == 'performance':
          with self.performance.lock:
            self.performance.sampler.reset()
      sources = {"metrics": lambda: self.refresh_system(metrics=True),
            "performance": self.refresh_performance,
            "brightness": lambda: self.refresh_system(brightness=True),
            "battery": lambda: self.refresh_system(battery=True),
            "network": self.refresh_network, "bluetooth": self.refresh_bluetooth,
            "clipboard": self.refresh_clipboard,
            "clipboard-expiry": lambda: self.clipboard_manager.refresh(expire=True)}
      for name, interval in plan.items():
        if previous.get(name) != interval or now >= due.get(name, 0):
          self.queue_refresh("wifi" if name == "network" else name,
            lambda name=name, function=sources[name]: self.refresh_polled(name, function))
          due[name] = now + interval
      previous = plan
      timeout = max(0.05, min(due.values()) - time.monotonic()) if due else None
      if watcher_timeout is not None:
        timeout = watcher_timeout if timeout is None else min(timeout, watcher_timeout)
      self.wakeup.wait(timeout)

  def safe_refresh(self, function, scope=None) -> None:
    try:
      function()
    except Exception as error:
      self.emit("error", str(error))
      if scope in self.faults.allowed and not isinstance(error, (OSError, ValueError, RuntimeError, subprocess.SubprocessError)):
        self.faults.report(scope, str(error))
        self.emit('faults', self.faults.snapshot())

  def emit_settings(self) -> None:
    self.emit("settings-history", self.store.history_state())
    self.emit("settings", self.store.settings)

  def edit_settings(self, action: str, data: dict, source: str = "shell") -> None:
    if action != "settings" and (not self.configuration_focused or source != "config"):
      raise ValueError("Abre y enfoca la configuración para deshacer, rehacer o restablecer")
    previous_warning = self.store.warning
    previous = self.store.settings
    if action == "settings":
      self.store.update(data, record=source == "config")
    elif action == "settings-undo":
      self.store.undo()
    elif action == "settings-redo":
      self.store.redo()
    elif action == "settings-reset":
      self.store.reset()
    elif action == "settings-restore-revision":
      updates = self.store.revisions.get(data.get("id"))["settings"]
      self.store.update(updates)
    else:
      self.store.update(self.features.settings_updates(action, data))
    if self.store.warning and self.store.warning != previous_warning:
      self.emit("error", self.store.warning)
    # Store publishes a new settings object after a successful commit. The old
    # object stays intact, including across undo, reset and profile restores.
    changed = {key for key in self.store.settings if previous[key] != self.store.settings[key]}
    if changed & {"clipboardEnabled", "clipboardPaused"}:
      self.safe_refresh(self.sync_watchers)
    if changed & {"barEnabled", "barModules", "disabledModules", "monitorBars", "osdEnabled"}:
      self.safe_refresh(self.sync_hardware)
    if self.serving and changed & {"nightLightEnabled", "nightLightTemperature", "nightLightSchedule", "nightLightStart", "nightLightEnd"}:
      self.queue_refresh("night-light", self.night.sync, latest=True)
    if changed & {"barEnabled", "barModules", "disabledModules", "monitorBars", "batteryAlertsEnabled", "clipboardEnabled", "clipboardRetentionHours", "performanceMode"}:
      self.wakeup.set()
    if changed & {"wallpaperDirectory", "wallpaperProvider"}:
      self.queue_refresh("wallpapers", self.refresh_wallpapers, latest=True)
    if changed & {"windowGapsEnabled", "windowGapsIn", "windowGapsOut"}:
      self.queue_refresh("window-gaps", self.window_gaps.sync, latest=True)
    self.emit_settings()

  def action(self, request: dict) -> None:
    action = request.get("action")
    data = request.get("data", {})
    try:
      if action != "history" and not isinstance(data, dict):
        raise ValueError("Los datos de la acción deben ser un objeto")
      if action in {"onboarding-complete", "onboarding-skip"}:
        self.onboarding.ensure_writable()
        if action == "onboarding-complete":
          updates = self.onboarding.updates(data)
          self.edit_settings("settings", updates, "config")
        elif data:
          raise ValueError("Omitir el asistente no admite cambios de configuración")
        self.onboarding.finish("completed" if action == "onboarding-complete" else "skipped", VERSION)
        self.emit("onboarding", self.onboarding.snapshot())
        self.emit("done", {"action": action})
        return
      if action == 'fault-report':
        self.faults.report(data.get('id'), data.get('message'))
        self.emit('faults', self.faults.snapshot())
        return
      if action == 'fault-reset':
        self.faults.reset(data.get('id'))
        self.emit('faults', self.faults.snapshot())
        return
      if action.startswith('performance-'):
        self.performance.handle(action, data, self.store.settings)
        if self.performance.open or action == 'performance-ready':
          self.emit('performance', self.performance.snapshot())
        self.wakeup.set()
        self.emit('done', {'action': action})
        return
      if action == 'wallpaper-palette-extract':
        if self.store.settings.get('wallpaperProvider') == 'external':
          raise ValueError('El gestor externo no comparte su archivo actual con HyprLarp; selecciona el fondo desde Fondos para analizarlo')
        self.emit('wallpaper-palette', self.wallpaper_palette.extract(self.store.settings.get('wallpaper', '')))
        self.emit('done', {'action': action})
        return
      if action == 'theme-context-changed':
        if not self.preview and not self.settings_only:
          requested = data.get('theme')
          if requested is not None and requested != effective_name(self.store.settings):
            raise ValueError('El contexto del tema cambió; espera la actualización de la interfaz')
          self.queue_refresh('theme-context', self.sync_theme_context, latest=True)
        self.emit('done', {'action': action})
        return
      if action in SETTINGS_ACTIONS:
        self.edit_settings(action, data, request.get("source", "shell"))
        return
      if action == "settings-context":
        focused = data.get("focused")
        if not isinstance(focused, bool):
          raise ValueError("Estado de la ventana de configuración inválido")
        self.configuration_focused = focused
        return
      if action in {"settings-revisions", "settings-revision-diff"}:
        self.features.require_config(request)
        with self.store.lock:
          if action == "settings-revisions":
            self.emit("settings-revisions", self.store.revisions.listing(self.store.settings))
          else:
            self.emit("settings-revision-diff", self.store.revisions.compare(data.get("id"), self.store.settings))
        self.emit("done", {"action": action})
        return
      if action in {"diagnostics-run", "diagnostics-export"}:
        self.features.require_config(request)
        if __package__:
          from . import diagnostics
        else:
          import diagnostics
        report = diagnostics.collect(ROOT, directory=self.store.directory, include_logs=not self.preview)
        self.emit("diagnostics", report)
        if action == "diagnostics-export":
          destination = self.features.path(data.get("path"))
          diagnostics.export(report, destination)
          self.emit("message", "Diagnóstico exportado: " + destination.name)
        self.emit("done", {"action": action})
        return
      if action in {"launcher-query", "launcher-open"}:
        if action == "launcher-query" and data.get("token") == "" and self.launcher_search is None:
          return
        if self.launcher_search is None:
          if __package__:
            from .launcher import LauncherSearch
          else:
            from launcher import LauncherSearch
          self.launcher_search = LauncherSearch(self, sys.modules[__name__])
        self.launcher_search.handle(action, data)
        self.emit("done", {"action": action})
        return
      if self.features.handle(request):
        self.emit("done", {"action": action})
        return
      if self.displays.handle(action, data):
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
        if data.get("name") != "launcher" and self.launcher_search is not None:
          self.launcher_search.cancel()
        if self.active_panel == "bluetooth" and data.get("name") != "bluetooth":
          self.bluetooth_manager.cancel()
          self.bluetooth_manager.stop_scan()
        self.active_panel = str(data.get("name", ""))
        self.performance.set_open(self.active_panel == 'performance')
        if self.performance.open:
          self.emit('performance', self.performance.snapshot())
        self.sync_hardware()
        self.wakeup.set()
        refresh = {"wifi": self.refresh_network, "bluetooth": self.refresh_bluetooth,
             "clipboard": self.refresh_clipboard, "wallpapers": self.refresh_wallpapers,
             "displays": self.displays.refresh}
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
        if not self.preview:
          self.queue_refresh("displays", lambda: self.displays.refresh("event"), latest=True)
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
      if not self.system_actions.handle(action, data, request):
        raise ValueError("Acción desconocida")
      self.emit("done", {"action": action})
    except (OSError, ValueError, TypeError, RuntimeError, subprocess.SubprocessError) as error:
      self.emit("action-error", {"action": action, "message": str(error)})
      self.emit("error", str(error))
      if action in SETTINGS_ACTIONS:
        self.emit("settings-rejected", {"action": action})
        self.emit_settings()
    except Exception as error:
      scope = 'panel:' + self.active_panel
      if scope in self.faults.allowed:
        self.faults.report(scope, str(error))
        self.emit('faults', self.faults.snapshot())
      self.emit('action-error', {'action': action, 'message': str(error)})
      self.emit('error', 'Falló un componente: ' + str(error))
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
      if __package__:
        from .lockscreen import prepare, monitors
      else:
        from lockscreen import prepare, monitors
      settings = Store(directory).settings
      assets, information = prepare(settings, directory)
      descriptor = os.open(assets, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW)
      try:
        atomic_text(configuration, render_lock_config(settings, outputs=monitors(),
          asset_path=f"/proc/self/fd/{descriptor}", assets=information))
        subprocess.Popen(["hyprlock", "--grace", "0", "--immediate-render", "--config", str(configuration)],
          pass_fds=(descriptor,), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
      finally:
        os.close(descriptor)
    elif name in {"poweroff", "reboot"}:
      command(["systemctl", name])
    elif name == "logout":
      command(["hyprctl", "dispatch", "hl.dsp.exit()"])
    elif name == "suspend":
      # hypridle's sleep inhibitor waits for the session-lock protocol before sleep.
      # Require our explicit config; an arbitrary idle daemon may not lock on sleep.
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
    self.emit("version", VERSION)
    self.emit("onboarding", self.onboarding.snapshot())
    self.emit('faults', self.faults.snapshot())
    self.emit("modules", MODULE_DEFINITIONS)
    self.emit("palettes", PALETTES)
    self.features.startup()
    self.emit("wallpaper-tools", {name: bool(shutil.which(name)) for name in ("waypaper", "mpvpaper", "socat")})
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
    self.start_external_wallpaper()
    self.queue_refresh("window-gaps", lambda: self.window_gaps.sync(native=not self.settings_only))
    if not self.preview:
      self.queue_refresh("displays", lambda: self.displays.refresh("startup"))
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
          if request.get("action", "").startswith('performance-') or request.get("action") in SETTINGS_ACTIONS | {"onboarding-complete", "onboarding-skip", "fault-report", "fault-reset", "settings-context", "history", "panel", "network-status", "outputs", "profile-save", "profile-delete", "theme-save", "theme-delete", "settings-export", "bluetooth-respond", "bluetooth-cancel", "launcher-query"}:
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
      self.wallpaper_palette.close()
      stop_processes()
      self.devices.stop()
      self.bluetooth_manager.close()
      self.backlight.stop()
      self.night.close()
      self.stop_watchers()
      self.executor.shutdown(wait=False, cancel_futures=True)


def main() -> None:
  def terminate(signum, frame):
    raise SystemExit(0)
  signal.signal(signal.SIGTERM, terminate)
  os.umask(0o077)
  parser = argparse.ArgumentParser()
  parser.add_argument("--version", action="version", version="HyprLarp " + VERSION)
  parser.add_argument("--preview", action="store_true")
  parser.add_argument("--settings-only", action="store_true")
  parser.add_argument("--native-services", action="store_true")
  args = parser.parse_args()
  config = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
  directory = Path(os.environ.get("HYPRLARP_STATE_DIR", str(config / "hyprlarp")))
  Service(Store(directory), args.preview, args.settings_only, args.native_services).serve()


if __name__ == "__main__":
  main()
