"""Capture-mode regressions: frame ordering, cancellation and helper ownership."""

import copy
from contextlib import contextmanager
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from backend import captures, safety
from backend.service import DEFAULTS, ROOT, Store


def layer(pid=9876, **values):
  return {"namespace": "hyprpicker", "pid": pid, "w": 1920, "h": 1080, "alpha": 1, **values}


class CaptureTests(unittest.TestCase):
  def setUp(self):
    self.temporary = tempfile.TemporaryDirectory(prefix="hyprlarp-capture-test-")
    self.addCleanup(self.temporary.cleanup)
    self.folder = Path(self.temporary.name)
    self.events = []
    self.selection = "-100,25 400x300"
    self.monitors = [{"name": "eDP-1", "refreshRate": 60}, {"name": "DP-1", "refreshRate": 144}]
    self.surfaces = {name: {"levels": {"3": [layer()]}} for name in ("eDP-1", "DP-1")}
    self.process = SimpleNamespace(pid=9876, poll=Mock(return_value=None))
    self.service = SimpleNamespace(store=SimpleNamespace(directory=self.folder), emit=Mock(), preview=False)
    self.api = SimpleNamespace(command=Mock(side_effect=self.command),
      optional=lambda argv, fallback: str(self.folder / "Pictures"), private_directory=safety.private_directory)
    self.capture = captures.Captures(self.service, self.api)
    self.capture.copy = Mock(side_effect=lambda path: self.events.append("copy"))

  def command(self, argv, **options):
    if argv[:2] == ["hyprctl", "eval"]:
      return "ok"
    if argv == ["hyprctl", "-j", "monitors"]:
      return json.dumps(self.monitors)
    if argv == ["hyprctl", "-j", "layers"]:
      self.events.append("ready")
      return json.dumps(self.surfaces)
    if argv == ["hyprctl", "-j", "activewindow"]:
      return json.dumps({"at": [10, 20], "size": [100, 80]})
    if argv == ["slurp"]:
      self.events.append("select")
      self.assertEqual(options, {"timeout": 120, "check": False})
      return self.selection
    if argv[0] == "grim":
      self.events.append("grab")
      Path(argv[-1]).write_bytes(b"captured frame")
      return ""
    if argv[:2] == ["magick", "identify"]:
      self.events.append("identify")
      return "400 300"
    self.fail("Unexpected capture command: " + repr(argv))

  @contextmanager
  def helper(self, argv):
    self.assertEqual(argv, ["hyprpicker", "--render-inactive", "--no-zoom", "--quiet"])
    self.events.append("freeze")
    try:
      yield self.process
    finally:
      self.events.append("unfreeze")

  def frozen(self):
    return patch.object(captures, "managed_process", side_effect=self.helper)

  def test_dynamic_selection_never_starts_the_freeze_helper(self):
    with patch.object(captures, "freeze_outputs") as freeze:
      self.capture.capture({"mode": "region"})
    freeze.assert_not_called()
    self.assertEqual(self.events, ["select", "grab", "copy"])
    grim = next(call.args[0] for call in self.api.command.call_args_list if call.args[0][0] == "grim")
    self.assertEqual(grim[1:3], ["-g", self.selection])
    self.assertTrue(Path(grim[-1]).is_file())

  def test_static_selection_waits_then_grabs_before_unfreezing_and_copying(self):
    with self.frozen(), patch.object(captures.shutil, "which", return_value="/usr/bin/hyprpicker"), \
        patch.object(captures.time, "sleep"):
      self.capture.capture({"mode": "region", "freeze": True})
    self.assertEqual(self.events, ["freeze", "ready", "select", "grab", "unfreeze", "copy"])
    self.capture.copy.assert_called_once()

  def test_static_editor_opens_after_unfreezing_and_keeps_a_private_draft(self):
    with self.frozen(), patch.object(captures.shutil, "which", return_value="/usr/bin/helper"), \
        patch.object(captures.time, "sleep"):
      self.capture.capture({"mode": "region", "freeze": True, "annotate": True})
    self.assertEqual(self.events, ["freeze", "ready", "select", "grab", "unfreeze", "identify"])
    self.capture.copy.assert_not_called()
    event, draft = self.service.emit.call_args.args
    self.assertEqual(event, "capture-edit")
    self.assertEqual((draft["width"], draft["height"]), (400, 300))
    path = self.capture.drafts[draft["token"]]["path"]
    self.assertEqual(path.stat().st_mode & 0o777, 0o600)
    self.assertFalse((self.folder / "Pictures").exists())

  def test_cancel_static_selection_unfreezes_without_creating_or_copying_a_file(self):
    self.selection = ""
    with self.frozen(), patch.object(captures.shutil, "which", return_value="/usr/bin/hyprpicker"), \
        patch.object(captures.time, "sleep"):
      self.capture.capture({"mode": "region", "freeze": True})
    self.assertEqual(self.events, ["freeze", "ready", "select", "unfreeze"])
    self.capture.copy.assert_not_called()
    self.assertFalse((self.folder / "Pictures").exists())
    self.assertFalse(self.capture.capture_lock.locked())

  def test_failed_grim_removes_partial_png_and_unfreezes(self):
    original = self.command
    def command(argv, **options):
      result = original(argv, **options)
      if argv[0] == "grim":
        raise RuntimeError("grab failed")
      return result
    self.api.command.side_effect = command
    with self.frozen(), patch.object(captures.shutil, "which", return_value="/usr/bin/hyprpicker"), \
        patch.object(captures.time, "sleep"), self.assertRaisesRegex(RuntimeError, "grab failed"):
      self.capture.capture({"mode": "region", "freeze": True})
    self.assertEqual(self.events, ["freeze", "ready", "select", "grab", "unfreeze"])
    self.assertEqual(list((self.folder / "Pictures/Screenshots").glob("*.png")), [])
    self.capture.copy.assert_not_called()
    self.assertFalse(self.capture.capture_lock.locked())

  def test_clipboard_failure_preserves_the_successfully_saved_capture(self):
    self.capture.copy.side_effect = RuntimeError("clipboard unavailable")
    self.capture.capture({"mode": "region"})
    images = list((self.folder / "Pictures/Screenshots").glob("*.png"))
    self.assertEqual(len(images), 1)
    self.assertEqual(images[0].read_bytes(), b"captured frame")
    self.assertFalse(self.capture.capture_lock.locked())
    self.assertIn("no se pudo copiar", self.service.emit.call_args.args[1])

  def editor_draft(self):
    self.capture.directory.mkdir()
    source = self.capture.directory / "draft.png"
    source.write_bytes(b"original draft")
    self.capture.drafts["test"] = {"path": source, "width": 400, "height": 300}
    return source

  def test_failed_editor_conversion_removes_partial_output_and_allows_retry(self):
    source = self.editor_draft()
    def convert(argv, **options):
      Path(argv[-1]).write_bytes(b"partial PNG")
      raise RuntimeError("conversion failed")
    self.api.command.side_effect = convert
    with self.assertRaisesRegex(RuntimeError, "conversion failed"):
      self.capture.handle("capture-save", {"token": "test"})
    self.assertEqual(list((self.folder / "Pictures/Screenshots").glob("*.png")), [])
    self.assertEqual(source.read_bytes(), b"original draft")
    self.assertIn("test", self.capture.drafts)
    self.capture.copy.assert_not_called()
    self.api.command.side_effect = lambda argv, **options: Path(argv[-1]).write_bytes(b"finished PNG")
    self.assertTrue(self.capture.handle("capture-save", {"token": "test"}))
    images = list((self.folder / "Pictures/Screenshots").glob("*.png"))
    self.assertEqual([image.read_bytes() for image in images], [b"finished PNG"])
    self.assertFalse(source.exists())
    self.assertEqual(self.capture.drafts, {})

  def test_editor_clipboard_failure_completes_save_and_cleans_draft(self):
    source = self.editor_draft()
    self.api.command.side_effect = lambda argv, **options: Path(argv[-1]).write_bytes(b"finished PNG")
    self.capture.copy.side_effect = subprocess.CalledProcessError(1, ["wl-copy"])
    self.assertTrue(self.capture.handle("capture-save", {"token": "test"}))
    images = list((self.folder / "Pictures/Screenshots").glob("*.png"))
    self.assertEqual([image.read_bytes() for image in images], [b"finished PNG"])
    self.assertEqual(self.capture.drafts, {})
    self.assertFalse(source.exists())
    self.assertEqual(list(self.capture.directory.iterdir()), [])
    self.assertIn("no se pudo copiar", self.service.emit.call_args.args[1])

  def test_open_editor_keeps_its_draft_until_finished_without_blocking_plain_captures(self):
    with patch.object(captures.shutil, "which", return_value="/usr/bin/magick"):
      self.capture.capture({"mode": "region", "annotate": True})
      token = next(iter(self.capture.drafts))
      path = self.capture.drafts[token]["path"]
      self.api.command.reset_mock()
      with patch.object(captures, "freeze_outputs", side_effect=AssertionError("An open editor must not start another selector")), \
          self.assertRaisesRegex(RuntimeError, "editor"):
        self.capture.capture({"mode": "region", "annotate": True, "freeze": True})
      self.api.command.assert_not_called()
      self.assertEqual(list(self.capture.drafts), [token])
      self.assertEqual(path.read_bytes(), b"captured frame")
      self.capture.capture({"mode": "region"})
      self.assertEqual(list(self.capture.drafts), [token])
      self.assertTrue(self.capture.handle("capture-discard", {"token": token}))
      self.capture.capture({"mode": "region", "annotate": True})
      self.assertEqual(len(self.capture.drafts), 1)
      self.assertNotIn(token, self.capture.drafts)

  def test_freeze_failure_during_selection_cannot_save_a_live_frame(self):
    self.process.poll.side_effect = [None, 1]
    with self.frozen(), patch.object(captures.shutil, "which", return_value="/usr/bin/hyprpicker"), \
        patch.object(captures.time, "sleep"), self.assertRaisesRegex(RuntimeError, "dejó de estar congelada"):
      self.capture.capture({"mode": "region", "freeze": True})
    self.assertEqual(self.events, ["freeze", "ready", "select", "unfreeze"])
    self.capture.copy.assert_not_called()
    self.assertFalse((self.folder / "Pictures").exists())

  def test_invalid_selection_is_rejected_before_grim(self):
    for geometry in ("1,2 0x10", "1,2 10x0", "1,2 10x10\n--help", "invalid"):
      with self.subTest(geometry=geometry):
        self.selection = geometry
        with self.assertRaisesRegex(ValueError, "selección"):
          self.capture.capture({"mode": "region"})
    self.capture.copy.assert_not_called()
    self.assertFalse((self.folder / "Pictures").exists())

  def test_freeze_requires_a_boolean_before_starting_any_command(self):
    for value in ("true", 1, 0, None, [], {}):
      with self.subTest(value=value), self.assertRaisesRegex(ValueError, "booleano"):
        self.capture.capture({"mode": "region", "freeze": value})
    self.api.command.assert_not_called()

  def test_simultaneous_capture_is_rejected_while_first_selector_is_open(self):
    entered, release = threading.Event(), threading.Event()
    failures = []
    original = self.command
    def command(argv, **options):
      if argv == ["slurp"]:
        entered.set()
        if not release.wait(3):
          raise RuntimeError("test selector timed out")
      return original(argv, **options)
    def first():
      try:
        self.capture.capture({"mode": "region"})
      except BaseException as error:
        failures.append(error)
    self.api.command.side_effect = command
    worker = threading.Thread(target=first)
    worker.start()
    try:
      self.assertTrue(entered.wait(2))
      with self.assertRaisesRegex(RuntimeError, "captura en curso"):
        self.capture.capture({"mode": "region", "freeze": True})
    finally:
      release.set()
      worker.join(timeout=3)
    self.assertFalse(worker.is_alive())
    self.assertEqual(failures, [])
    self.assertEqual(self.events.count("select"), 1)
    self.capture.copy.assert_called_once()
    self.assertFalse(self.capture.capture_lock.locked())

  def test_freeze_startup_failure_and_deadline_always_release_the_helper(self):
    for exited in (True, False):
      self.events.clear()
      self.surfaces = {}
      self.process.poll.side_effect = None
      self.process.poll.return_value = 1 if exited else None
      with self.subTest(exited=exited), self.frozen(), \
          patch.object(captures.shutil, "which", return_value="/usr/bin/hyprpicker"), \
          patch.object(captures.time, "monotonic", side_effect=[0, 4]), \
          self.assertRaises(RuntimeError):
        with captures.freeze_outputs(self.api):
          self.fail("A failed helper must not start selection")
      self.assertEqual(self.events[0], "freeze")
      self.assertEqual(self.events[-1], "unfreeze")

  def test_missing_dependency_or_monitors_does_not_start_a_helper(self):
    with patch.object(captures.shutil, "which", return_value=None), \
        patch.object(captures, "managed_process") as helper, self.assertRaisesRegex(RuntimeError, "Instala hyprpicker"):
      with captures.freeze_outputs(self.api):
        self.fail("Missing dependency")
    helper.assert_not_called()
    self.api.command.assert_not_called()
    self.monitors = []
    with patch.object(captures.shutil, "which", return_value="/usr/bin/hyprpicker"), \
        patch.object(captures, "managed_process") as helper, self.assertRaisesRegex(RuntimeError, "No hay pantallas"):
      with captures.freeze_outputs(self.api):
        self.fail("Missing monitor")
    helper.assert_not_called()

  def test_freeze_waits_for_all_outputs_and_ignores_disabled_or_mirrored_outputs(self):
    self.monitors += [{"name": "HDMI-A-1", "disabled": True}, {"name": "DP-2", "mirrorOf": "DP-1"}]
    original = self.command
    count = 0
    def command(argv, **options):
      nonlocal count
      if argv == ["hyprctl", "-j", "layers"]:
        count += 1
        if count == 1:
          return json.dumps({"eDP-1": [layer()]})
      return original(argv, **options)
    self.api.command.side_effect = command
    with self.frozen(), patch.object(captures.shutil, "which", return_value="/usr/bin/hyprpicker"), \
        patch.object(captures.time, "sleep"):
      with captures.freeze_outputs(self.api) as process:
        self.assertIs(process, self.process)
        self.assertEqual(count, 2)
        self.assertNotIn("unfreeze", self.events)
    self.assertEqual(self.events[-1], "unfreeze")


class FreezeReadinessTests(unittest.TestCase):
  def test_only_own_mapped_opaque_hyprpicker_layers_count_for_every_output(self):
    outputs = {"eDP-1", "DP-1"}
    good = {"eDP-1": {"levels": {"3": [layer()]}}, "DP-1": [layer()]}
    self.assertTrue(captures.frozen_layers(good, 9876, outputs))
    for replacement in (layer(pid=123), layer(namespace="another-helper"), layer(alpha=0.5),
        layer(w=0), layer(h=0), {}, []):
      with self.subTest(replacement=replacement):
        invalid = {**good, "DP-1": [replacement]}
        self.assertFalse(captures.frozen_layers(invalid, 9876, outputs))
    self.assertFalse(captures.frozen_layers({"eDP-1": good["eDP-1"]}, 9876, outputs))
    self.assertFalse(captures.frozen_layers(good, 9876, set()))
    self.assertFalse(captures.frozen_layers([], 9876, outputs))


class CaptureShortcutMigrationTests(unittest.TestCase):
  def test_existing_custom_ctrl_print_survives_default_shortcut_migration(self):
    for version in (2, 3):
      for enabled in (True, False):
        with self.subTest(version=version, enabled=enabled), tempfile.TemporaryDirectory() as temporary:
          directory = Path(temporary)
          saved = copy.deepcopy(DEFAULTS)
          saved["version"] = version
          saved["shortcuts"].pop("screenshot-region-frozen")
          saved["customBindings"] = [{"id": "my-capture", "name": "My capture", "type": "command",
            "chord": "CTRL, Print", "command": "my-personal-capture", "enabled": enabled}]
          (directory / "settings.json").write_text(json.dumps(saved))
          store = Store(directory)
          self.assertEqual(store.warning, "")
          self.assertEqual(len(store.settings["customBindings"]), 1)
          self.assertEqual(store.settings["customBindings"][0]["command"], "my-personal-capture")
          self.assertEqual(store.settings["customBindings"][0]["enabled"], enabled)
          self.assertEqual(store.settings["shortcuts"]["screenshot-region-frozen"], "" if enabled else "CTRL, Print")
          self.assertEqual(store.settings["shortcuts"]["screenshot-region"], ", Print")
          self.assertEqual(store.settings["shortcuts"]["screenshot-screen"], "SHIFT, Print")


class ManagedCaptureHelperTests(unittest.TestCase):
  @staticmethod
  def running(pid):
    try:
      return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0] != "Z"
    except FileNotFoundError:
      return False

  def wait_ready(self, path):
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
      if path.is_file():
        try:
          return int(path.read_text())
        except (OSError, ValueError):
          pass
      time.sleep(.01)
    self.fail("The isolated helper did not become ready")

  def test_real_helper_is_reaped_after_exception(self):
    with self.assertRaisesRegex(RuntimeError, "selection failed"):
      with safety.managed_process([sys.executable, "-c", "import time; time.sleep(30)"]) as process:
        self.assertIn(process, safety._processes)
        raise RuntimeError("selection failed")
    self.assertIsNotNone(process.poll())
    self.assertNotIn(process, safety._processes)

  def test_unresponsive_helper_is_killed_after_cleanup_deadline(self):
    with tempfile.TemporaryDirectory() as temporary:
      ready = Path(temporary) / "ready"
      code = "import os,signal,sys,time; from pathlib import Path; signal.signal(signal.SIGTERM,signal.SIG_IGN); Path(sys.argv[1]).write_text(str(os.getpid())); time.sleep(30)"
      with safety.managed_process([sys.executable, "-c", code, str(ready)]) as process:
        self.assertEqual(self.wait_ready(ready), process.pid)
      self.assertEqual(process.returncode, -signal.SIGKILL)
      self.assertNotIn(process, safety._processes)

  def test_shutdown_kills_and_reaps_managed_helpers_in_an_isolated_service(self):
    code = """
import sys
from backend.safety import managed_process, stop_processes, _processes
with managed_process([sys.executable, '-c', 'import time; time.sleep(30)']) as child:
  stop_processes()
  child.wait(timeout=2)
  assert child.returncode != 0
assert not _processes
try:
  with managed_process([sys.executable, '-c', 'pass']):
    raise AssertionError('shutdown admitted a helper')
except RuntimeError:
  pass
print('cleaned')
"""
    result = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, timeout=5)
    self.assertEqual(result.returncode, 0, result.stderr)
    self.assertEqual(result.stdout.strip(), "cleaned")

  def test_helper_exits_when_its_service_owner_dies_abruptly(self):
    with tempfile.TemporaryDirectory() as temporary:
      ready = Path(temporary) / "ready"
      helper = "import os,sys,time; from pathlib import Path; Path(sys.argv[1]).write_text(str(os.getpid())); time.sleep(30)"
      owner_code = """
import sys,time
from backend.safety import managed_process
with managed_process([sys.executable, '-c', sys.argv[1], sys.argv[2]]):
  time.sleep(30)
"""
      owner = subprocess.Popen([sys.executable, "-c", owner_code, helper, str(ready)], cwd=ROOT,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
      pid = None
      try:
        pid = self.wait_ready(ready)
        self.assertTrue(self.running(pid))
        owner.kill()
        owner.wait(timeout=3)
        deadline = time.monotonic() + 3
        while self.running(pid) and time.monotonic() < deadline:
          time.sleep(.02)
        self.assertFalse(self.running(pid), "A frozen overlay must not outlive its service")
      finally:
        if owner.poll() is None:
          owner.kill()
          owner.wait(timeout=3)
        if pid and self.running(pid):
          os.killpg(pid, signal.SIGKILL)


if __name__ == "__main__":
  unittest.main()
