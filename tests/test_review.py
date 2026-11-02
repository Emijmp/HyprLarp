import copy
import io
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
import signal
import unittest
from unittest.mock import Mock, patch

from backend.bluetooth import PairingAgent
from backend.safety import BoundedExecutor, JSON_LIMIT, bounded_process, read_json, read_regular, idle_processes
from backend.service import Metrics, NOTIFICATION_JSON_LIMIT, ROOT, Service, Store, clean_history, validate_setting
from backend.wifi import WifiSecrets
from backend.clipboard_store import bounded_input


class SafetyTests(unittest.TestCase):
  def setUp(self):
    self.temp = tempfile.TemporaryDirectory()
    self.addCleanup(self.temp.cleanup)
    self.root = Path(self.temp.name)

  def test_regular_reads_reject_large_files_fifos_and_nonfinite_json(self):
    large = self.root / "large"
    large.write_bytes(b"x" * 1025)
    with self.assertRaises(ValueError):
      read_regular(large, 1024)
    fifo = self.root / "fifo"
    os.mkfifo(fifo)
    with self.assertRaises(ValueError):
      read_regular(fifo)
    large.write_text('{"value": NaN}')
    with self.assertRaises(ValueError):
      read_json(large)

  def test_huge_integers_and_nested_json_are_rejected_without_overflowing(self):
    with self.assertRaises(ValueError):
      validate_setting("barSize", 10 ** 1000)
    self.assertEqual(clean_history([{"time": 10 ** 1000}], 1)[0]["time"], 0)
    nested = self.root / "nested"
    nested.write_text("[" * 2000 + "0" + "]" * 2000)
    with self.assertRaises(ValueError):
      read_json(nested)
    for value in ("1e10000", "1" + "0" * 1000):
      nested.write_text('{"value":' + value + '}')
      with self.assertRaises(ValueError):
        read_json(nested)

  def test_json_rejects_unpaired_unicode_surrogates(self):
    path = self.root / "unicode"
    path.write_text('{"font":"\\ud800"}')
    with self.assertRaises(ValueError):
      read_json(path)
    path.write_text('{"font":"\\ud83d\\ude00"}')
    self.assertTrue(read_json(path)["font"])

  def test_idle_detection_matches_exact_config_argument_including_spaces(self):
    expected = str(self.root / "my config/hypridle.conf")
    for pid, args in [(1, ["hypridle", "-c", expected]), (2, ["hypridle", "-c", "other", expected]), (3, ["other-program", "-c", expected])]:
      process = self.root / str(pid)
      process.mkdir()
      (process / "cmdline").write_bytes(b"\0".join(argument.encode() for argument in args) + b"\0")
    self.assertEqual([pid for pid, args in idle_processes(expected, self.root)], [1])

  def test_clipboard_capture_has_a_size_limit_before_cliphist_storage(self):
    source = self.root / "input"
    source.write_bytes(b"private text")
    with source.open("rb") as handle:
      descriptor = bounded_input(handle.fileno(), limit=1024)
    try:
      self.assertEqual(os.read(descriptor, 1024), b"private text")
    finally:
      os.close(descriptor)
    source.write_bytes(b"x" * 1025)
    with source.open("rb") as handle:
      self.assertIsNone(bounded_input(handle.fileno(), limit=1024))

  def test_process_output_and_timeout_are_bounded(self):
    with self.assertRaises(ValueError):
      bounded_process([sys.executable, "-c", "import os; os.write(1, b'x' * 1000000)"], limit=1024)
    with self.assertRaises(RuntimeError):
      bounded_process([sys.executable, "-c", "import os,time; os.close(1); os.close(2); time.sleep(10)"], timeout=0.2)
    data = b"x" * 100000
    result = bounded_process([sys.executable, "-c", "import sys; sys.stdout.write('ready\\n'); sys.stdout.flush(); print(len(sys.stdin.buffer.read()))"], content=data)
    self.assertEqual(result, b"ready\n100000\n")

  def test_work_queue_is_bounded_and_recovers_after_completion(self):
    release, entered = threading.Event(), threading.Event()
    pool = BoundedExecutor(max_workers=1, pending=1)
    def slow():
      entered.set()
      release.wait(3)
    try:
      first = pool.submit(slow)
      self.assertTrue(entered.wait(1))
      second = pool.submit(lambda: 2)
      with self.assertRaises(RuntimeError):
        pool.submit(lambda: 3)
      release.set()
      first.result(2)
      self.assertEqual(second.result(2), 2)
      self.assertEqual(pool.submit(lambda: 4).result(2), 4)
    finally:
      release.set()
      pool.shutdown(wait=True)

  def test_protocol_survives_invalid_action_types_and_oversized_requests(self):
    state = self.root / "state"
    ordinary = json.dumps({"action": "settings", "data": {"font": "x" * JSON_LIMIT}})
    text = '{"action": []}\n' + ordinary + '\n' + ' ' * (NOTIFICATION_JSON_LIMIT + 32) + '\n{"action":"history","data":[]}\n'
    result = subprocess.run([sys.executable, str(ROOT / "backend/service.py"), "--preview"],
      input=text, text=True, capture_output=True, timeout=6, env={**os.environ, "HYPRLARP_STATE_DIR": str(state)})
    self.assertEqual(result.returncode, 0, result.stderr)
    events = [json.loads(line) for line in result.stdout.splitlines()]
    self.assertGreaterEqual(sum(entry["type"] == "error" for entry in events), 3)
    self.assertEqual(json.loads((state / "notifications.json").read_text()), [])

  def test_sensitive_files_are_private_and_histories_are_normalized(self):
    state = self.root / "state"
    state.mkdir(mode=0o755)
    store = Store(state)
    store.update({"barSpacing": 11})
    self.assertEqual(stat.S_IMODE(state.stat().st_mode), 0o700)
    self.assertEqual(stat.S_IMODE(store.file.stat().st_mode), 0o600)
    result = clean_history([{"app": "__proto__", "body": "x" * 100000, "summary": None, "time": float("inf"), "id": []}], 1)
    self.assertEqual(len(result[0]["body"]), 2048)
    self.assertEqual(result[0]["summary"], "")
    self.assertEqual(result[0]["time"], 0)

  def test_full_unicode_notification_history_survives_persistence_and_reload(self):
    state = self.root / "state"
    store = Store(state)
    store.update({"notificationHistoryLimit": 500})
    entries = [{"id": index + 1, "token": str(index), "app": "Aplicación", "summary": "Aviso", "body": "漢" * 2048, "time": 1} for index in range(500)]
    payload = json.dumps({"action": "history", "data": entries}, ensure_ascii=False).encode() + b"\n"
    self.assertGreater(len(payload), JSON_LIMIT)
    result = subprocess.run([sys.executable, str(ROOT / "backend/service.py"), "--preview"],
      input=payload, capture_output=True, timeout=8, env={**os.environ, "HYPRLARP_STATE_DIR": str(state)})
    self.assertEqual(result.returncode, 0, result.stderr.decode())
    self.assertFalse([event for event in map(json.loads, result.stdout.splitlines()) if event["type"] == "error"])
    history_path = state / "notifications.json"
    self.assertGreater(history_path.stat().st_size, JSON_LIMIT)
    service = Service(Store(state))
    self.addCleanup(service.executor.shutdown, wait=True)
    service.emit = Mock()
    service.load_history()
    saved = service.emit.call_args.args[1]
    self.assertEqual(len(saved), 500)
    self.assertEqual(saved[-1]["body"], entries[-1]["body"])

  def test_clipboard_does_not_render_vector_or_script_formats(self):
    service = Service(Store(self.root / "state"))
    self.addCleanup(service.executor.shutdown, wait=True)
    with patch.object(service.clipboard_manager, "decode", return_value=b"push graphic-context\nimage over 0,0 1,1 'label:@/etc/passwd'"), patch("backend.clipboard.shutil.which", return_value="magick"), patch("backend.service.bounded_process") as run:
      service.clipboard_manager.handle("clipboard-thumbnail", {"id": "1", "raw": "1\t[[ binary data ]]"})
      run.assert_not_called()

  @unittest.skipUnless(shutil.which("magick"), "ImageMagick opcional")
  def test_raster_thumbnail_is_bounded_and_saved_privately(self):
    image = bounded_process(["magick", "-size", "3840x2160", "xc:white", "png:-"], timeout=10)
    service = Service(Store(self.root / "state"))
    self.addCleanup(service.executor.shutdown, wait=True)
    service.emit = Mock()
    with patch.object(service.clipboard_manager, "decode", return_value=image):
      service.clipboard_manager.handle("clipboard-thumbnail", {"id": "1"})
    files = list((service.clipboard_manager.directory / "thumbnails").glob("*.png"))
    self.assertEqual(len(files), 1)
    import struct
    width, height = struct.unpack(">II", files[0].read_bytes()[16:24])
    self.assertLessEqual(width, 192)
    self.assertLessEqual(height, 128)
    self.assertEqual(stat.S_IMODE(files[0].stat().st_mode), 0o600)

  def test_capture_cleanup_does_not_follow_directory_symlinks_or_remove_foreign_files(self):
    external = self.root / "external"
    external.mkdir()
    sentinel = external / ("a" * 32 + ".png")
    sentinel.write_text("keep")
    state = self.root / "state"
    state.mkdir()
    (state / "capture-drafts").symlink_to(external, target_is_directory=True)
    service = Service(Store(state))
    self.addCleanup(service.executor.shutdown, wait=True)
    self.assertEqual(sentinel.read_text(), "keep")
    with patch("backend.service.optional", return_value=str(self.root)):
      capture = service.captures.destination()
    self.assertEqual(stat.S_IMODE(capture.stat().st_mode), 0o600)

  def test_wifi_profile_serializes_secrets_only_into_dbus_settings(self):
    try:
      import gi
      gi.require_version("NM", "1.0")
      from gi.repository import NM, GLib
    except (ImportError, ValueError):
      self.skipTest("libnm opcional no disponible")
    helper = WifiSecrets()
    helper.NM, helper.GLib = NM, GLib
    calls = []
    def call(path, interface, method, parameters=None):
      calls.append((method, parameters))
      if method == "GetAll":
        return GLib.Variant("(a{sv})", ({"DeviceType": GLib.Variant("u", 2), "AvailableConnections": GLib.Variant("ao", [])},))
      return GLib.Variant("(o)", ("/new_profile",))
    helper.call = call
    with patch.object(helper, "load"):
      ident = helper.prepare("Private", "wlan0", "secret123", "WPA2")
    settings = calls[-1][1].unpack()[0]
    self.assertEqual(calls[-1][0], "AddConnection")
    self.assertEqual(settings["802-11-wireless-security"]["psk"], "secret123")
    self.assertEqual(settings["connection"]["uuid"], ident)

  @unittest.skipUnless(hasattr(os, "pidfd_open"), "Linux pidfd requerido")
  def test_managed_child_exits_when_its_parent_is_killed(self):
    program = "import subprocess,sys,os; child=subprocess.Popen([sys.executable, sys.argv[1], str(os.getpid()), sys.executable, '-u', '-c', \"import time; print('READY', flush=True); time.sleep(60)\"], stdout=subprocess.PIPE, text=True); print(child.pid, flush=True); print(child.stdout.readline().strip(), flush=True); sys.stdin.read()"
    parent = subprocess.Popen([sys.executable, "-u", "-c", program, str(ROOT / "backend/child.py")], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    descriptor = None
    try:
      pid = int(parent.stdout.readline())
      self.assertEqual(parent.stdout.readline().strip(), "READY")
      descriptor = os.pidfd_open(pid)
      parent.kill()
      parent.wait(timeout=2)
      deadline = time.monotonic() + 2
      running = True
      while time.monotonic() < deadline:
        try:
          running = (Path("/proc") / str(pid) / "stat").read_text().rsplit(")", 1)[1].split()[0] != "Z"
        except FileNotFoundError:
          running = False
        if not running:
          break
        time.sleep(0.01)
      self.assertFalse(running, "el proceso hijo no debe quedar activo sin su padre")
    finally:
      if parent.poll() is None:
        parent.kill()
      parent.wait()
      parent.stdin.close()
      parent.stdout.close()
      if descriptor is not None:
        try:
          signal.pidfd_send_signal(descriptor, signal.SIGKILL)
        except ProcessLookupError:
          pass
        os.close(descriptor)

  def test_wifi_secret_does_not_appear_in_process_arguments(self):
    service = Service(Store(self.root / "state"))
    self.addCleanup(service.executor.shutdown, wait=True)
    with patch.object(service.wifi_secrets, "prepare", return_value="profile-uuid") as prepare, patch.object(service, "refresh_network"), patch("backend.service.command") as run:
      service.action({"action": "wifi-connect", "data": {"ssid": "Private", "interface": "wlan0", "password": "secret123"}})
      prepare.assert_called_once()
      self.assertNotIn("secret123", str(run.call_args))
      self.assertIn("profile-uuid", run.call_args.args[0])

  def test_pairing_rejects_other_bus_senders_even_for_cancellation(self):
    manager = Mock()
    agent = PairingAgent(manager, "/org/bluez/hci0/dev_AA", "Device")
    agent.owner = ":1.bluez"
    for method in ("RequestPinCode", "Cancel", "Release"):
      invocation = Mock()
      agent.request(None, ":1.attacker", None, None, method, Mock(), invocation)
      invocation.return_dbus_error.assert_called_once()
    manager.s.emit.assert_not_called()

  def test_bar_metrics_do_not_read_disk_network_or_thermal_sensors(self):
    with patch("backend.service.shutil.disk_usage") as disk, patch("backend.service.Path.glob") as thermal:
      data = Metrics().read(detailed=False)
    self.assertIn("memory", data)
    self.assertNotIn("disk", data)
    self.assertNotIn("upload", data)
    disk.assert_not_called()
    thermal.assert_not_called()

  def test_detailed_metrics_cache_disk_and_thermal_discovery(self):
    metrics = Metrics()
    with patch("backend.service.shutil.disk_usage", return_value=shutil.disk_usage(self.root)) as disk, patch("backend.service.Path.glob", return_value=[]) as sensors:
      metrics.read()
      metrics.read()
    disk.assert_called_once()
    sensors.assert_called_once()

  def test_decoration_choices_persist_and_undo_as_a_single_edit(self):
    store = Store(self.root / "state")
    original = copy.deepcopy(store.settings)
    store.update({"decorationOptions": {"panelCorners": False, "separators": False}})
    self.assertFalse(Store(store.directory).settings["decorationOptions"]["panelCorners"])
    store.undo()
    self.assertEqual(store.settings, original)
    with self.assertRaises(ValueError):
      store.update({"decorationOptions": {"unknown": True}})
