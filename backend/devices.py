"""On-demand power profiles and USB storage through native GIO D-Bus."""

import os
from pathlib import Path
import re
import subprocess
import threading

try:
  from .udev import UdevEvents
except ImportError:
  from udev import UdevEvents

PROFILES = [("org.freedesktop.UPower.PowerProfiles", "/org/freedesktop/UPower/PowerProfiles"),
  ("net.hadess.PowerProfiles", "/net/hadess/PowerProfiles")]
UDISKS = "org.freedesktop.UDisks2"
ROOT = "/org/freedesktop/UDisks2"
PROPERTIES = "org.freedesktop.DBus.Properties"
PROTECTED = {"/", "/boot", "/boot/efi", "/efi", "/home", "/usr", "/var", "/etc", "/opt", "/srv", str(Path.home())}


def decode_path(value):
  if isinstance(value, str):
    return value.rstrip("\0")
  return os.fsdecode(bytes(value or []).rstrip(b"\0"))


def usb_devices(base=Path("/sys/bus/usb/devices")):
  """Physical USB devices, without duplicate interfaces or root hubs."""
  devices = []
  if not base.is_dir():
    return devices
  for device in base.iterdir():
    def read(name):
      try:
        return (device / name).read_text().strip()
      except OSError:
        return ""
    vendor, product = read("idVendor"), read("idProduct")
    if not vendor or not product or device.name.startswith("usb"):
      continue
    devices.append({"id": device.name, "name": read("product") or "Dispositivo USB",
      "manufacturer": read("manufacturer"), "vendor": vendor, "product": product,
      "speed": read("speed"), "class": read("bDeviceClass")})
  return sorted(devices, key=lambda device: (device["name"].lower(), device["id"]))


def usb_snapshot(objects):
  drives = {}
  for path, interfaces in objects.items():
    drive = interfaces.get(UDISKS + ".Drive")
    if drive and drive.get("ConnectionBus") == "usb":
      drives[path] = {"id": path, "name": " ".join(str(drive.get(key, "")).strip() for key in ("Vendor", "Model")).strip() or "Unidad USB",
        "size": int(drive.get("Size", 0)), "canEject": bool(drive.get("CanPowerOff")), "protected": False, "volumes": []}
  for path, interfaces in objects.items():
    block = interfaces.get(UDISKS + ".Block")
    if not block or block.get("Drive") not in drives:
      continue
    drive = drives[block["Drive"]]
    filesystem = interfaces.get(UDISKS + ".Filesystem")
    mounts = [decode_path(value) for value in (filesystem or {}).get("MountPoints", [])]
    protected = bool(block.get("HintSystem")) or any(mount in PROTECTED for mount in mounts)
    drive["protected"] = drive["protected"] or protected
    if block.get("HintIgnore"):
      continue
    if not filesystem and not block.get("IdType"):
      continue
    free, total = None, None
    if mounts:
      try:
        stats = os.statvfs(mounts[0])
        total, free = stats.f_blocks * stats.f_frsize, stats.f_bavail * stats.f_frsize
      except OSError:
        pass
    drive["volumes"].append({"id": path, "device": decode_path(block.get("PreferredDevice") or block.get("Device")),
      "name": block.get("IdLabel") or decode_path(block.get("PreferredDevice") or block.get("Device")),
      "filesystem": block.get("IdType", ""), "size": int(block.get("Size", 0)),
      "mounts": mounts, "mounted": bool(mounts), "mountable": filesystem is not None,
      "readOnly": bool(block.get("ReadOnly")), "protected": protected, "free": free, "total": total})
  for drive in drives.values():
    drive["canEject"] = drive["canEject"] and not drive["protected"]
  return sorted(drives.values(), key=lambda drive: drive["name"].lower())


class Devices:
  def __init__(self, service):
    self.s = service
    self.lock = threading.RLock()
    self.lifecycle = threading.RLock()
    self.generation = 0
    self.thread = None
    self.loop = None
    self.context = None
    self.connection = None
    self.Gio = self.GLib = None
    self.need_power = self.need_usb = False
    self.attempted = False
    self.busy = False
    self.power_endpoint = None
    self.usb_events = UdevEvents("usb", lambda: self.s.queue_refresh("usb", self.refresh_usb, latest=True))

  def call(self, name, path, interface, method, arguments=None, timeout=4000):
    if self.connection is None:
      raise RuntimeError("D-Bus del sistema no está disponible")
    try:
      result = self.connection.call_sync(name, path, interface, method, arguments, None,
        self.Gio.DBusCallFlags.NONE, timeout, None)
      return result.unpack()
    except Exception as error:
      raise RuntimeError(str(error)) from error

  def sync(self, power=False, usb=False):
    changed = (power, usb) != (self.need_power, self.need_usb)
    self.need_power, self.need_usb = power, usb
    if self.s.preview or self.s.settings_only:
      return
    if usb:
      self.usb_events.start()
    else:
      self.usb_events.stop()
    if not (power or usb):
      if not self.busy: self.stop()
    elif not self.attempted:
      with self.lifecycle:
        self.attempted = True
        self.generation += 1
        self.thread = threading.Thread(target=self.run, args=(self.generation,), daemon=True)
        self.thread.start()
    elif changed and self.connection:
      if power:
        self.s.queue_refresh("power", self.refresh_power, latest=True)
      if usb:
        self.s.queue_refresh("usb", self.refresh_usb, latest=True)

  def run(self, generation):
    subscriptions = []
    context = loop = connection = None
    try:
      import gi
      gi.require_version("Gio", "2.0")
      from gi.repository import Gio, GLib
      context = GLib.MainContext.new()
      context.push_thread_default()
      loop = GLib.MainLoop.new(context, False)
      connection = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
      for name, path in [(UDISKS, None)] + PROFILES:
        subscriptions.append(connection.signal_subscribe(name, PROPERTIES, "PropertiesChanged", path, None, Gio.DBusSignalFlags.NONE, self.changed))
      for member in ("InterfacesAdded", "InterfacesRemoved"):
        subscriptions.append(connection.signal_subscribe(UDISKS, "org.freedesktop.DBus.ObjectManager", member, ROOT, None, Gio.DBusSignalFlags.NONE, self.changed))
      for name in [UDISKS] + [entry[0] for entry in PROFILES]:
        subscriptions.append(connection.signal_subscribe("org.freedesktop.DBus", "org.freedesktop.DBus", "NameOwnerChanged", "/org/freedesktop/DBus", name, Gio.DBusSignalFlags.NONE, self.owner_changed))
      with self.lifecycle:
        if generation != self.generation or not (self.need_power or self.need_usb):
          return
        self.Gio, self.GLib = Gio, GLib
        self.context, self.loop, self.connection = context, loop, connection
      if self.need_power:
        self.s.queue_refresh("power", self.refresh_power, latest=True)
      if self.need_usb:
        self.s.queue_refresh("usb", self.refresh_usb, latest=True)
      # An idle callback also catches stop() between publication and run().
      def started(*unused):
        if generation != self.generation or not (self.need_power or self.need_usb):
          loop.quit()
        return False
      source = GLib.idle_source_new()
      source.set_callback(started)
      source.attach(context)
      loop.run()
    except Exception as error:
      if generation == self.generation and self.need_power:
        self.s.emit_changed("power", {"available": False, "profiles": [], "profile": "", "error": str(error)})
      if generation == self.generation and self.need_usb:
        self.s.emit_changed("usb", {"available": False, "drives": [], "devices": usb_devices(), "error": str(error)})
    finally:
      if connection:
        for subscription in subscriptions:
          connection.signal_unsubscribe(subscription)
      if context:
        context.pop_thread_default()
      with self.lifecycle:
        if generation == self.generation:
          self.connection = self.loop = self.context = None

  def changed(self, connection, sender, path, interface, signal, parameters, *unused):
    if connection is not self.connection:
      return
    if self.need_usb and path.startswith(ROOT):
      self.s.queue_refresh("usb", self.refresh_usb, latest=True)
    if self.need_power and any(path == endpoint[1] for endpoint in PROFILES):
      self.s.queue_refresh("power", self.refresh_power, latest=True)

  def owner_changed(self, connection, sender, path, interface, signal, parameters, *unused):
    if connection is not self.connection:
      return
    name = parameters.unpack()[0]
    if self.need_usb and name == UDISKS:
      self.s.queue_refresh("usb", self.refresh_usb, latest=True)
    if self.need_power and name in {entry[0] for entry in PROFILES}:
      self.s.queue_refresh("power", self.refresh_power, latest=True)

  def power_properties(self):
    error = None
    for name, path in PROFILES:
      try:
        properties = self.call(name, path, PROPERTIES, "GetAll", self.GLib.Variant("(s)", (name,)))[0]
        self.power_endpoint = (name, path)
        return properties
      except Exception as failure:
        error = failure
    raise RuntimeError("power-profiles-daemon no está disponible") from error

  def refresh_power(self):
    try:
      with self.lock:
        if self.s.preview:
          raise RuntimeError("Perfiles de energía desactivados en la vista previa")
        if not self.GLib:
          raise RuntimeError("Conectando al servicio de energía")
        properties = self.power_properties()
        profiles = [entry["Profile"] for entry in properties.get("Profiles", []) if entry.get("Profile") in {"power-saver", "balanced", "performance"}]
        self.s.emit_changed("power", {"available": bool(profiles), "profiles": profiles,
          "profile": properties.get("ActiveProfile", ""), "reason": properties.get("PerformanceDegraded", ""),
          "holds": properties.get("ActiveProfileHolds", []), "error": ""})
    except Exception as error:
      self.s.emit_changed("power", {"available": False, "profiles": [], "profile": "", "error": str(error)})

  def objects(self):
    return self.call(UDISKS, ROOT, "org.freedesktop.DBus.ObjectManager", "GetManagedObjects")[0]

  def refresh_usb(self):
    devices = [] if self.s.preview else usb_devices()
    try:
      with self.lock:
        if self.s.preview:
          raise RuntimeError("Las unidades se consultan en la sesión real")
        drives = usb_snapshot(self.objects())
        self.s.emit_changed("usb", {"available": True, "drives": drives, "devices": devices, "error": ""})
    except Exception as error:
      self.s.emit_changed("usb", {"available": False, "drives": [], "devices": devices, "error": str(error)})

  def refresh(self, name):
    if self.connection is None and not self.s.preview and not self.s.settings_only:
      power, usb = self.need_power or name == "power", self.need_usb or name == "usb"
      self.stop()
      self.sync(power=power, usb=usb)
      return
    (self.refresh_power if name == "power" else self.refresh_usb)()

  def handle(self, action, data):
    if action not in {"power-profile", "usb-mount", "usb-unmount", "usb-eject", "usb-open"}:
      return False
    with self.lock:
      self.busy = True
      try:
        return self.perform(action, data)
      finally:
        self.busy = False
        if not (self.need_power or self.need_usb): self.stop()

  def perform(self, action, data):
    if action not in {"power-profile", "usb-mount", "usb-unmount", "usb-eject", "usb-open"}:
      return False
    if self.s.preview or self.s.settings_only:
      raise RuntimeError("Esta acción requiere el shell activo en una sesión real")
    with self.lock:
      if action == "power-profile":
        profile = data.get("profile")
        if profile not in {"power-saver", "balanced", "performance"}:
          raise ValueError("Perfil de energía desconocido")
        if not self.GLib:
          raise RuntimeError("El servicio de energía no está disponible")
        properties = self.power_properties()
        if profile not in {entry.get("Profile") for entry in properties.get("Profiles", [])}:
          raise ValueError("El equipo no ofrece ese perfil")
        name, path = self.power_endpoint
        self.call(name, path, PROPERTIES, "Set", self.GLib.Variant("(ssv)", (name, "ActiveProfile", self.GLib.Variant("s", profile))))
        self.refresh_power()
        return True
      ident = data.get("id", "")
      if not isinstance(ident, str) or not re.fullmatch(r"/org/freedesktop/UDisks2/(drives|block_devices)/[A-Za-z0-9_]+", ident):
        raise ValueError("Unidad USB inválida")
      drives = usb_snapshot(self.objects())
      drive = next((drive for drive in drives if drive["id"] == ident), None)
      volume = next((volume for drive in drives for volume in drive["volumes"] if volume["id"] == ident), None)
      options = self.GLib.Variant("(a{sv})", ({},))
      if action == "usb-eject":
        if not drive or not drive["canEject"] or drive["protected"]:
          raise ValueError("La unidad no admite esta expulsión segura")
        for entry in drive["volumes"]:
          if entry["mounted"]:
            self.call(UDISKS, entry["id"], UDISKS + ".Filesystem", "Unmount", options, 30000)
        self.call(UDISKS, drive["id"], UDISKS + ".Drive", "PowerOff", options, 30000)
      elif not volume or volume["protected"]:
        raise ValueError("La unidad no es un volumen USB de datos disponible")
      elif action == "usb-open":
        if not volume["mounts"]:
          raise ValueError("Monta primero el volumen")
        subprocess.Popen(["xdg-open", Path(volume["mounts"][0]).as_uri()], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
      elif action == "usb-mount":
        if not volume["mountable"] or volume["mounted"]:
          raise ValueError("El volumen no se puede montar en este estado")
        self.call(UDISKS, ident, UDISKS + ".Filesystem", "Mount", options, 30000)
      else:
        if not volume["mounted"]:
          raise ValueError("El volumen ya está desmontado")
        self.call(UDISKS, ident, UDISKS + ".Filesystem", "Unmount", options, 30000)
      self.refresh_usb()
    return True

  def stop(self):
    with self.lifecycle:
      self.need_power = self.need_usb = False
      self.generation += 1
      thread, loop = self.thread, self.loop
      self.thread = self.loop = self.context = self.connection = None
      self.attempted = False
      if loop:
        loop.quit()
    self.usb_events.stop()
    if thread and thread is not threading.current_thread():
      thread.join(timeout=1)
