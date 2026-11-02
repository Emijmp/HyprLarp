import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from backend.bluetooth import BLUEZ, PairingAgent, PROPERTIES
from backend.service import ROOT, Service, Store, parse_networks, validate_setting
from backend.wallpapers import catalogue, local_path

ADAPTER = "/org/bluez/hci0"
DEVICE = ADAPTER + "/dev_AA_BB_CC_DD_EE_FF"
ADDRESS = "AA:BB:CC:DD:EE:FF"


def bluez_objects(paired=False, connected=False):
  return {ADAPTER: {BLUEZ + ".Adapter1": {"Powered": True}},
    DEVICE: {BLUEZ + ".Device1": {"Address": ADDRESS, "Adapter": ADAPTER, "Alias": "Headphones", "Paired": paired, "Connected": connected, "Trusted": paired}}}


class ConnectionTests(unittest.TestCase):
  def setUp(self):
    self.temp = tempfile.TemporaryDirectory()
    self.addCleanup(self.temp.cleanup)
    self.service = Service(Store(Path(self.temp.name)), preview=False)
    self.addCleanup(self.service.executor.shutdown, wait=True)
    self.events = []
    self.service.emit = lambda kind, data: self.events.append((kind, copy.deepcopy(data)))

  def test_wifi_uses_the_selected_adapter_and_saved_credentials(self):
    with patch("backend.service.command", return_value="") as command, patch.object(self.service, "refresh_network"):
      self.service.action({"action": "wifi-connect", "data": {"ssid": "Studio:5G", "interface": "wlan1", "password": ""}})
    argv = command.call_args.args[0]
    self.assertEqual(argv[-3:], ["Studio:5G", "ifname", "wlan1"])
    self.assertNotIn("password", argv)
    self.assertGreater(command.call_args.kwargs["timeout"], 45)
    self.assertIn(("done", {"action": "wifi-connect"}), self.events)

  def test_wifi_keeps_the_real_error_without_echoing_the_password(self):
    with patch("backend.service.command", side_effect=RuntimeError("bad password secret123")), patch.object(self.service.wifi_secrets, "prepare", return_value="uuid"):
      self.service.action({"action": "wifi-connect", "data": {"ssid": "Studio", "interface": "wlan0", "password": "secret123"}})
    errors = [data["message"] for kind, data in self.events if kind == "action-error"]
    self.assertEqual(len(errors), 1)
    self.assertIn("bad password", errors[0])
    self.assertNotIn("secret123", errors[0])

  def test_wifi_invalid_adapter_and_password_do_not_execute_commands(self):
    with patch("backend.service.command") as command:
      for data in ({"ssid": "Studio", "interface": "wlan0; reboot"}, {"ssid": "Studio", "interface": "wlan0", "password": False}):
        self.service.action({"action": "wifi-connect", "data": data})
    command.assert_not_called()

  def test_wifi_scan_waits_for_fresh_results_and_exposes_service_failures(self):
    with patch("backend.service.command", side_effect=["*:Studio:88:WPA2:wlan0", "enabled", "wifi:connected:Studio"]) as command:
      self.service.refresh_network(True)
    self.assertEqual(command.call_args_list[0].args[0][-2:], ["--rescan", "yes"])
    self.assertEqual(self.events[-1][1]["ssid"], "Studio")
    with patch("backend.service.command", side_effect=RuntimeError("NetworkManager is not running")):
      self.service.refresh_network()
    self.assertFalse(self.events[-1][1]["available"])
    self.assertIn("not running", self.events[-1][1]["error"])

  def test_wifi_retains_the_same_ssid_on_different_adapters(self):
    networks = parse_networks(":Studio:70:WPA2:wlan0\n:Studio:80:WPA2:wlan1\n:Studio:40:WPA2:wlan0")
    self.assertEqual({entry["interface"] for entry in networks}, {"wlan0", "wlan1"})
    self.assertEqual(len(networks), 2)

  def test_bluetooth_connect_remembers_an_existing_untrusted_pairing(self):
    manager = self.setup_bluetooth(paired=True)
    manager.objects.return_value[DEVICE][BLUEZ + ".Device1"]["Trusted"] = False
    manager.handle("bluetooth-connect", {"address": ADDRESS})
    self.assertEqual([call.args[2] for call in manager.call.call_args_list], ["Set", "Get", "Connect"])

  def setup_bluetooth(self, paired=False, connected=False):
    manager = self.service.bluetooth_manager
    manager.GLib = Mock()
    manager.GLib.Variant.side_effect = lambda signature, values: (signature, values)
    manager.objects = Mock(return_value=bluez_objects(paired, connected))
    manager.call = Mock(side_effect=lambda path, interface, method, *args, **kwargs: (False,) if method == "Get" else ())
    manager.refresh = Mock()
    return manager

  def test_bluetooth_pair_confirms_then_trusts_and_connects(self):
    manager = self.setup_bluetooth()
    invocation = Mock()
    def call(path, interface, method, *args, **kwargs):
      if method == "Pair":
        manager.agent.owner = ":1.bluez"
        manager.agent.request(None, ":1.bluez", None, None, "RequestConfirmation", Mock(unpack=lambda: (DEVICE, 123)), invocation)
        prompt = self.events[-1][1]
        self.assertEqual(prompt["code"], "000123")
        manager.handle("bluetooth-respond", {"token": prompt["token"], "accepted": True})
        invocation.return_value.assert_called_once_with(None)
      return (False,) if method == "Get" else ()
    manager.call.side_effect = call
    with patch.object(PairingAgent, "start"):
      manager.handle("bluetooth-pair", {"address": ADDRESS, "adapter": ADAPTER})
    methods = [call.args[2] for call in manager.call.call_args_list]
    self.assertEqual(methods, ["Pair", "Set", "Get", "Connect"])
    self.assertIsNone(manager.agent)
    self.assertIn(("bluetooth-prompt", None), self.events)

  def test_bluetooth_existing_pairing_is_reused_and_connected_devices_are_unchanged(self):
    manager = self.setup_bluetooth(paired=True)
    manager.handle("bluetooth-connect", {"address": ADDRESS})
    self.assertEqual([call.args[2] for call in manager.call.call_args_list], ["Get", "Connect"])
    manager = self.setup_bluetooth(paired=True, connected=True)
    manager.handle("bluetooth-connect", {"address": ADDRESS})
    manager.call.assert_not_called()

  def test_bluetooth_pair_does_not_report_already_connected_as_failure(self):
    manager = self.setup_bluetooth()
    manager.call.side_effect = lambda path, interface, method, *args, **kwargs: (True,) if method == "Get" else ()
    with patch.object(PairingAgent, "start"):
      manager.handle("bluetooth-pair", {"address": ADDRESS})
    self.assertNotIn("Connect", [call.args[2] for call in manager.call.call_args_list])

  def test_pairing_pin_validation_preserves_the_pending_request(self):
    manager = self.setup_bluetooth()
    agent = PairingAgent(manager, DEVICE, "Headphones")
    agent.owner = ":1.bluez"
    invocation = Mock()
    agent.request(None, ":1.bluez", None, None, "RequestPasskey", Mock(unpack=lambda: (DEVICE,)), invocation)
    token = self.events[-1][1]["token"]
    for data in ({"token": "old", "accepted": True, "value": "123"}, {"token": token, "accepted": True, "value": "1234567"}):
      with self.assertRaises(ValueError):
        agent.respond(data)
    invocation.return_value.assert_not_called()
    agent.respond({"token": token, "accepted": True, "value": "000123"})
    invocation.return_value.assert_called_once_with(("(u)", (123,)))

  def test_pairing_can_be_rejected_and_only_accepts_the_requested_device(self):
    manager = self.setup_bluetooth()
    agent = PairingAgent(manager, DEVICE, "Headphones")
    agent.owner = ":1.bluez"
    wrong = Mock()
    agent.request(None, ":1.bluez", None, None, "RequestPinCode", Mock(unpack=lambda: ("/other",)), wrong)
    wrong.return_dbus_error.assert_called_once()
    self.assertEqual(self.events, [])
    invocation = Mock()
    agent.request(None, ":1.bluez", None, None, "RequestPinCode", Mock(unpack=lambda: (DEVICE,)), invocation)
    agent.respond({"token": self.events[-1][1]["token"], "accepted": False})
    invocation.return_dbus_error.assert_called_once()

  def test_pairing_displays_keyboard_code_and_clears_on_cancel(self):
    manager = self.setup_bluetooth()
    agent = PairingAgent(manager, DEVICE, "Keyboard")
    agent.owner = ":1.bluez"
    invocation = Mock()
    agent.request(None, ":1.bluez", None, None, "DisplayPasskey", Mock(unpack=lambda: (DEVICE, 5, 2)), invocation)
    self.assertEqual(self.events[-1][1]["code"], "000005")
    self.assertEqual(self.events[-1][1]["entered"], 2)
    invocation.return_value.assert_called_once_with(None)
    agent.clear()
    self.assertEqual(self.events[-1], ("bluetooth-prompt", None))

  def test_bluetooth_scan_is_bounded_and_stops_only_its_own_discovery(self):
    manager = self.setup_bluetooth()
    manager.stop_scan()
    manager.call.assert_not_called()
    with patch("backend.bluetooth.threading.Timer") as timer:
      manager.handle("bluetooth-scan", {})
      timer.assert_called_once_with(12, manager.stop_scan)
      manager.stop_scan()
      timer.return_value.cancel.assert_called_once()
    self.assertEqual([call.args[2] for call in manager.call.call_args_list], ["StartDiscovery", "StopDiscovery"])

  def test_closing_bluetooth_panel_cancels_pending_pairing(self):
    self.service.active_panel = "bluetooth"
    with patch.object(self.service.bluetooth_manager, "cancel") as cancel, patch.object(self.service.bluetooth_manager, "stop_scan") as stop:
      self.service.action({"action": "panel", "data": {"name": "control"}})
    cancel.assert_called_once()
    stop.assert_called_once()


class WallpaperTests(unittest.TestCase):
  def setUp(self):
    self.temp = tempfile.TemporaryDirectory()
    self.addCleanup(self.temp.cleanup)
    self.root = Path(self.temp.name)
    self.folder = self.root / "Mis fondos # ñ"
    self.folder.mkdir()
    self.image = self.folder / "fondo # 100% $USER.svg"
    self.image.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16"/>')

  def test_folder_url_and_image_special_characters_are_normalized_and_persist(self):
    self.assertEqual(validate_setting("wallpaperDirectory", self.folder.as_uri()), str(self.folder))
    self.assertEqual(validate_setting("wallpaper", self.image.as_uri()), str(self.image))
    self.assertEqual(validate_setting("wallpaper", str(self.image)), str(self.image))
    store = Store(self.root / "state")
    store.update({"wallpaperDirectory": self.folder.as_uri(), "wallpaper": self.image.as_uri()})
    self.assertEqual(Store(self.root / "state").settings["wallpaper"], str(self.image))

  def test_invalid_directory_does_not_change_settings_or_history(self):
    store = Store(self.root / "state")
    before = copy.deepcopy(store.settings)
    with self.assertRaises(ValueError):
      store.update({"wallpaperDirectory": str(self.root / "missing"), "barSpacing": 20})
    self.assertEqual(store.settings, before)
    self.assertEqual(store.history_state(), {"undo": 0, "redo": 0})

  def test_catalogue_encodes_urls_deduplicates_and_reports_missing_folder(self):
    images, state = catalogue(str(self.folder), self.folder, self.folder)
    self.assertEqual(len(images), 1)
    self.assertEqual(images[0]["url"], self.image.as_uri())
    self.assertEqual(local_path(images[0]["url"]), self.image)
    self.assertEqual(state["error"], "")
    images, state = catalogue(str(self.root / "missing"), self.folder, self.folder)
    self.assertEqual(len(images), 1)
    self.assertTrue(state["error"])
    self.assertEqual(state["browseUrl"], self.root.as_uri())

  def test_catalogue_has_a_global_limit_and_does_not_descend_into_subfolders(self):
    for index in range(5):
      (self.folder / f"{index}.png").touch()
    (self.folder / "nested").mkdir()
    (self.folder / "nested/invisible.png").touch()
    images, state = catalogue(str(self.folder), ROOT / "assets/wallpapers", self.folder, limit=3)
    self.assertEqual(len(images), 3)
    self.assertTrue(state["truncated"])
    self.assertTrue(all(Path(image["path"]).parent == self.folder for image in images))
