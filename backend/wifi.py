"""Send Wi-Fi secrets directly to NetworkManager, never through process argv."""

import uuid
import os
import pwd

NAME = "org.freedesktop.NetworkManager"
SETTINGS = NAME + ".Settings"


class WifiSecrets:
  def __init__(self):
    self.connection = None
    self.NM = self.GLib = self.Gio = None

  def load(self):
    try:
      import gi
      gi.require_version("NM", "1.0")
      from gi.repository import Gio, GLib, NM
      self.NM, self.GLib, self.Gio = NM, GLib, Gio
      self.connection = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
    except Exception as error:
      raise RuntimeError("Para guardar la contraseña necesitas NetworkManager, libnm y python-gobject") from error

  def call(self, path, interface, method, parameters=None):
    try:
      return self.connection.call_sync(NAME, path, interface, method, parameters, None,
        self.Gio.DBusCallFlags.NONE, 10000, None)
    except Exception as error:
      raise RuntimeError(str(error)) from error

  def prepare(self, ssid, interface, password, security):
    try:
      return self.configure(ssid, interface, password, security)
    except (ValueError, RuntimeError):
      raise
    except Exception as error:
      raise RuntimeError(str(error)) from error

  def configure(self, ssid, interface, password, security):
    self.load()
    device = self.call("/org/freedesktop/NetworkManager", NAME, "GetDeviceByIpIface", self.GLib.Variant("(s)", (interface,))).unpack()[0]
    properties = self.call(device, "org.freedesktop.DBus.Properties", "GetAll", self.GLib.Variant("(s)", (NAME + ".Device",))).unpack()[0]
    if properties.get("DeviceType") != 2:
      raise ValueError("El adaptador elegido no es Wi-Fi")
    profiles = properties.get("AvailableConnections", [])
    matches = []
    for path in profiles:
      settings = self.call(path, SETTINGS + ".Connection", "GetSettings").get_child_value(0)
      data = settings.unpack()
      connection, wireless = data.get("connection", {}), data.get("802-11-wireless", {})
      if connection.get("type") == "802-11-wireless" and bytes(wireless.get("ssid", [])) == ssid.encode() and connection.get("interface-name", "") in {"", interface} and wireless.get("mode", "infrastructure") == "infrastructure":
        matches.append((connection.get("timestamp", 0), path, settings))
    if matches:
      _, path, settings = max(matches, key=lambda entry: entry[0])
      profile = self.NM.SimpleConnection.new_from_dbus(settings)
      encryption = profile.get_setting_wireless_security()
      if not encryption or encryption.props.key_mgmt not in {"wpa-psk", "sae"}:
        raise ValueError("Configura las credenciales de esta red con el editor de conexiones")
    else:
      if "WEP" in security or "802.1X" in security or "EAP" in security:
        raise ValueError("Configura esta red con el editor de conexiones")
      profile = self.NM.SimpleConnection.new()
      connection = self.NM.SettingConnection.new()
      connection.props.id, connection.props.uuid = ssid, str(uuid.uuid4())
      connection.props.type, connection.props.interface_name = "802-11-wireless", interface
      connection.props.permissions = ["user:" + pwd.getpwuid(os.getuid()).pw_name + ":"]
      profile.add_setting(connection)
      wireless = self.NM.SettingWireless.new()
      wireless.props.ssid = self.GLib.Bytes.new(ssid.encode())
      wireless.props.mode = "infrastructure"
      profile.add_setting(wireless)
      encryption = self.NM.SettingWirelessSecurity.new()
      encryption.props.key_mgmt = "sae" if "WPA3" in security and "WPA2" not in security else "wpa-psk"
      profile.add_setting(encryption)
      for cls in (self.NM.SettingIP4Config, self.NM.SettingIP6Config):
        setting = cls.new()
        setting.props.method = "auto"
        profile.add_setting(setting)
    encryption.props.psk = password
    profile.normalize()
    profile.verify()
    settings = profile.to_dbus(self.NM.ConnectionSerializationFlags.ALL)
    arguments = self.GLib.Variant.new_tuple(settings)
    if matches:
      self.call(path, SETTINGS + ".Connection", "Update", arguments)
    else:
      self.call("/org/freedesktop/NetworkManager/Settings", SETTINGS, "AddConnection", arguments)
    return profile.get_uuid()
