"""BlueZ operations and an agent scoped to an explicit pairing request."""

import re
import threading
import uuid

BLUEZ = "org.bluez"
PROPERTIES = "org.freedesktop.DBus.Properties"
AGENT_PATH = "/org/hyprlarp/PairingAgent"
AGENT_XML = """<node><interface name="org.bluez.Agent1">
  <method name="Release"/>
  <method name="Cancel"/>
  <method name="RequestPinCode"><arg type="o" direction="in"/><arg type="s" direction="out"/></method>
  <method name="RequestPasskey"><arg type="o" direction="in"/><arg type="u" direction="out"/></method>
  <method name="RequestConfirmation"><arg type="o" direction="in"/><arg type="u" direction="in"/></method>
  <method name="RequestAuthorization"><arg type="o" direction="in"/></method>
  <method name="AuthorizeService"><arg type="o" direction="in"/><arg type="s" direction="in"/></method>
  <method name="DisplayPinCode"><arg type="o" direction="in"/><arg type="s" direction="in"/></method>
  <method name="DisplayPasskey"><arg type="o" direction="in"/><arg type="u" direction="in"/><arg type="q" direction="in"/></method>
</interface></node>"""


class PairingAgent:
  def __init__(self, manager, path, name):
    self.manager, self.path, self.name = manager, path, name
    self.lock = threading.RLock()
    self.ready = threading.Event()
    self.closed = threading.Event()
    self.loop = None
    self.error = None
    self.pending = None
    self.token = ""
    self.kind = ""
    self.thread = None
    self.owner = None

  def start(self):
    self.owner = self.manager.bluez_owner()
    self.thread = threading.Thread(target=self.run, daemon=True)
    self.thread.start()
    if not self.ready.wait(5):
      raise RuntimeError("El agente de vinculación no respondió")
    if self.error:
      raise RuntimeError(self.error)

  def run(self):
    m, context, registration, registered, source = self.manager, None, None, False, None
    try:
      context = m.GLib.MainContext.new()
      context.push_thread_default()
      self.loop = m.GLib.MainLoop.new(context, False)
      node = m.Gio.DBusNodeInfo.new_for_xml(AGENT_XML)
      interface = node.interfaces[0]
      registration = m.connection.register_object(AGENT_PATH, interface, self.request, None, None)
      if self.closed.is_set():
        return
      m.call("/org/bluez", BLUEZ + ".AgentManager1", "RegisterAgent", m.variant("(os)", (AGENT_PATH, "KeyboardDisplay")))
      registered = True
      self.ready.set()
      source = m.GLib.idle_source_new()
      def started(*unused):
        if self.closed.is_set():
          self.loop.quit()
        return False
      source.set_callback(started)
      source.attach(context)
      self.loop.run()
    except Exception as error:
      self.error = str(error)
    finally:
      self.ready.set()
      if source:
        source.destroy()
      if registered:
        try:
          m.call("/org/bluez", BLUEZ + ".AgentManager1", "UnregisterAgent", m.variant("(o)", (AGENT_PATH,)), timeout=1000)
        except RuntimeError:
          pass
      if registration:
        m.connection.unregister_object(registration)
      if context:
        context.pop_thread_default()

  def clear(self):
    with self.lock:
      if self.pending:
        self.pending.return_dbus_error(BLUEZ + ".Error.Canceled", "Vinculación cancelada")
      self.pending, self.token = None, ""
      self.manager.s.emit("bluetooth-prompt", None)

  def request(self, connection, sender, path, interface, method, parameters, invocation):
    if not self.owner or sender != self.owner:
      invocation.return_dbus_error(BLUEZ + ".Error.Rejected", "El solicitante no es BlueZ")
      return
    values = parameters.unpack()
    if method in {"Release", "Cancel"}:
      self.clear()
      invocation.return_value(None)
      return
    if self.closed.is_set() or not values or values[0] != self.path:
      invocation.return_dbus_error(BLUEZ + ".Error.Rejected", "Dispositivo no solicitado")
      return
    kinds = {"RequestPinCode": "pin", "RequestPasskey": "passkey", "RequestConfirmation": "confirm",
      "RequestAuthorization": "authorize", "AuthorizeService": "authorize", "DisplayPinCode": "display", "DisplayPasskey": "display"}
    kind = kinds.get(method)
    if not kind:
      invocation.return_dbus_error(BLUEZ + ".Error.Rejected", "Solicitud no compatible")
      return
    with self.lock:
      if self.pending:
        invocation.return_dbus_error(BLUEZ + ".Error.Rejected", "Ya hay una solicitud pendiente")
        return
      self.kind = kind
      self.token = uuid.uuid4().hex
      if kind == "display":
        invocation.return_value(None)
      else:
        self.pending = invocation
      code = str(values[1]).zfill(6) if method in {"RequestConfirmation", "DisplayPinCode", "DisplayPasskey"} else ""
      self.manager.s.emit("bluetooth-prompt", {"token": self.token, "kind": kind, "name": self.name,
        "code": code, "entered": values[2] if method == "DisplayPasskey" else 0})

  def respond(self, data):
    with self.lock:
      if not self.pending or data.get("token") != self.token:
        raise ValueError("La solicitud de vinculación ya no está activa")
      if not isinstance(data.get("accepted"), bool):
        raise ValueError("Confirma o rechaza la solicitud")
      if not data["accepted"]:
        self.pending.return_dbus_error(BLUEZ + ".Error.Rejected", "Solicitud rechazada")
      elif self.kind == "pin":
        value = data.get("value", "")
        if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9]{1,16}", value):
          raise ValueError("El PIN debe tener entre 1 y 16 letras o números")
        self.pending.return_value(self.manager.variant("(s)", (value,)))
      elif self.kind == "passkey":
        value = data.get("value", "")
        if not isinstance(value, str) or not re.fullmatch(r"[0-9]{1,6}", value):
          raise ValueError("Introduce un código de hasta 6 dígitos")
        self.pending.return_value(self.manager.variant("(u)", (int(value),)))
      else:
        self.pending.return_value(None)
      self.pending, self.token = None, ""
      self.manager.s.emit("bluetooth-prompt", None)

  def close(self):
    self.closed.set()
    self.clear()
    if self.loop:
      self.loop.quit()
    if self.thread and self.thread is not threading.current_thread():
      self.thread.join(timeout=2)


class BluetoothManager:
  def __init__(self, service):
    self.s = service
    self.connection = None
    self.Gio = self.GLib = None
    self.connection_lock = threading.Lock()
    self.operation_lock = threading.Lock()
    self.agent = None
    self.scan_adapter = None
    self.scan_timer = None
    self.scan_lock = threading.RLock()

  def connect_bus(self):
    with self.connection_lock:
      if self.connection and not self.connection.is_closed():
        return
      try:
        import gi
        gi.require_version("Gio", "2.0")
        from gi.repository import Gio, GLib
        self.Gio, self.GLib = Gio, GLib
        self.connection = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
      except Exception as error:
        raise RuntimeError("Bluetooth no está disponible. Comprueba BlueZ, D-Bus y python-gobject. " + str(error)) from error

  def variant(self, signature, values):
    return self.GLib.Variant(signature, values)

  def bluez_owner(self):
    try:
      return self.connection.call_sync("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus", "GetNameOwner",
        self.variant("(s)", (BLUEZ,)), None, self.Gio.DBusCallFlags.NONE, 5000, None).unpack()[0]
    except Exception as error:
      raise RuntimeError("BlueZ no está disponible") from error

  def call(self, path, interface, method, arguments=None, timeout=5000):
    try:
      return self.connection.call_sync(BLUEZ, path, interface, method, arguments, None,
        self.Gio.DBusCallFlags.NONE, timeout, None).unpack()
    except Exception as error:
      raise RuntimeError(str(error)) from error

  def objects(self):
    self.connect_bus()
    return self.call("/", "org.freedesktop.DBus.ObjectManager", "GetManagedObjects")[0]

  def adapter(self, objects, requested=""):
    adapters = [(path, interfaces[BLUEZ + ".Adapter1"]) for path, interfaces in objects.items() if BLUEZ + ".Adapter1" in interfaces]
    if requested:
      return next((entry for entry in adapters if entry[0] == requested), (None, {}))
    return next((entry for entry in adapters if entry[1].get("Powered")), adapters[0] if adapters else (None, {}))

  def refresh(self, requested=""):
    if self.s.preview or self.s.settings_only:
      self.s.emit_changed("bluetooth", {"available": False, "enabled": False, "devices": [], "error": "Conexiones desactivadas en la vista previa."})
      return
    try:
      objects = self.objects()
      path, adapter = self.adapter(objects, requested)
      devices = []
      for ident, interfaces in objects.items():
        device = interfaces.get(BLUEZ + ".Device1")
        if device and device.get("Adapter") == path:
          devices.append({"address": device.get("Address", ""), "name": device.get("Alias") or device.get("Name") or device.get("Address", ""),
            "connected": bool(device.get("Connected")), "paired": bool(device.get("Paired")), "trusted": bool(device.get("Trusted"))})
      self.s.emit_changed("bluetooth", {"available": path is not None, "enabled": bool(adapter.get("Powered")),
        "adapter": path or "", "discovering": bool(adapter.get("Discovering")),
        "devices": sorted(devices, key=lambda entry: (not entry["connected"], not entry["paired"], entry["name"].casefold())), "error": ""})
    except RuntimeError as error:
      self.s.emit_changed("bluetooth", {"available": False, "enabled": False, "devices": [], "error": str(error)})

  def set_property(self, path, interface, name, signature, value):
    self.call(path, PROPERTIES, "Set", self.variant("(ssv)", (interface, name, self.variant(signature, value))))

  def connect_device(self, path):
    connected = self.call(path, PROPERTIES, "Get", self.variant("(ss)", (BLUEZ + ".Device1", "Connected")))[0]
    if not connected:
      try:
        self.call(path, BLUEZ + ".Device1", "Connect", timeout=30000)
      except RuntimeError as error:
        if "org.bluez.Error.AlreadyConnected" not in str(error):
          raise

  def stop_scan(self):
    with self.scan_lock:
      if self.scan_timer:
        self.scan_timer.cancel()
        self.scan_timer = None
      path, self.scan_adapter = self.scan_adapter, None
      if path:
        try:
          self.call(path, BLUEZ + ".Adapter1", "StopDiscovery", timeout=2000)
        except RuntimeError:
          pass

  def cancel(self):
    agent = self.agent
    if agent:
      agent.closed.set()
      agent.clear()
      try:
        self.call(agent.path, BLUEZ + ".Device1", "CancelPairing", timeout=2000)
      except RuntimeError:
        pass

  def handle(self, action, data):
    if action not in {"bluetooth-power", "bluetooth-scan", "bluetooth-pair", "bluetooth-connect", "bluetooth-disconnect", "bluetooth-respond", "bluetooth-cancel"}:
      return False
    if self.s.preview or self.s.settings_only:
      raise RuntimeError("Abre el shell de escritorio para gestionar Bluetooth")
    if action == "bluetooth-respond":
      if not self.agent:
        raise ValueError("No hay una solicitud de vinculación activa")
      self.agent.respond(data)
      return True
    if action == "bluetooth-cancel":
      self.cancel()
      return True
    address = data.get("address", "")
    if action in {"bluetooth-pair", "bluetooth-connect", "bluetooth-disconnect"} and (not isinstance(address, str) or not re.fullmatch(r"(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}", address)):
      raise ValueError("Dirección Bluetooth inválida")
    if not self.operation_lock.acquire(blocking=False):
      raise RuntimeError("Espera a que termine la operación Bluetooth actual")
    requested = data.get("adapter", "")
    try:
      objects = self.objects()
      adapter, properties = self.adapter(objects, requested)
      if not adapter:
        raise RuntimeError("No hay un adaptador Bluetooth disponible")
      if action == "bluetooth-power":
        if not isinstance(data.get("enabled"), bool):
          raise ValueError("Estado Bluetooth inválido")
        if not data["enabled"]:
          self.stop_scan()
        self.set_property(adapter, BLUEZ + ".Adapter1", "Powered", "b", data["enabled"])
      elif not properties.get("Powered"):
        raise RuntimeError("Activa Bluetooth antes de conectar o buscar")
      elif action == "bluetooth-scan":
        with self.scan_lock:
          if not self.scan_adapter:
            self.call(adapter, BLUEZ + ".Adapter1", "StartDiscovery")
            self.scan_adapter = adapter
          if self.scan_timer:
            self.scan_timer.cancel()
          self.scan_timer = threading.Timer(12, self.stop_scan)
          self.scan_timer.daemon = True
          self.scan_timer.start()
      else:
        self.stop_scan()
        match = next(((path, entry[BLUEZ + ".Device1"]) for path, entry in objects.items()
          if BLUEZ + ".Device1" in entry and entry[BLUEZ + ".Device1"].get("Address", "").upper() == address.upper()
          and entry[BLUEZ + ".Device1"].get("Adapter") == adapter), None)
        if not match:
          raise RuntimeError("El dispositivo ya no está disponible. Vuelve a buscarlo.")
        path, device = match
        if action == "bluetooth-disconnect":
          self.call(path, BLUEZ + ".Device1", "Disconnect", timeout=20000)
        else:
          if not device.get("Paired"):
            self.agent = PairingAgent(self, path, device.get("Alias") or device.get("Name") or address)
            try:
              self.agent.start()
              if self.agent.closed.is_set() or self.s.stopping.is_set():
                raise RuntimeError("Vinculación cancelada")
              self.call(path, BLUEZ + ".Device1", "Pair", timeout=90000)
              if self.agent.closed.is_set():
                raise RuntimeError("Vinculación cancelada")
              self.set_property(path, BLUEZ + ".Device1", "Trusted", "b", True)
              self.connect_device(path)
            finally:
              self.agent.close()
              self.agent = None
          elif not device.get("Connected"):
            if not device.get("Trusted"):
              self.set_property(path, BLUEZ + ".Device1", "Trusted", "b", True)
            self.connect_device(path)
      return True
    finally:
      self.operation_lock.release()
      self.refresh(requested)

  def close(self):
    self.cancel()
    self.stop_scan()
