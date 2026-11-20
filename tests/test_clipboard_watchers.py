"""Clipboard capture recovers per MIME without a restart loop or extra workers."""

from pathlib import Path
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch

from backend.service import Service, Store


class ClipboardWatcherTests(unittest.TestCase):
  def setUp(self):
    temporary = tempfile.TemporaryDirectory(prefix="hyprlarp-watchers-")
    self.addCleanup(temporary.cleanup)
    self.service = Service(Store(Path(temporary.name)), preview=False)
    self.addCleanup(self.service.executor.shutdown, wait=True)
    self.addCleanup(self.service.stop_watchers)
    self.service.store.settings.update({"clipboardEnabled": True, "clipboardPaused": False,
      "clipboardRetentionHours": 0, "barEnabled": False, "batteryAlertsEnabled": False})
    self.service.native_services = True
    self.service.emit = Mock()
    self.now = 100
    self.processes = []
    self.actual_popen = subprocess.Popen
    def spawn(*args, **kwargs):
      process = Mock()
      process.poll.return_value = None
      process.wait.return_value = 0
      self.processes.append(process)
      return process
    self.spawn = self.enterContext(patch("backend.service.subprocess.Popen", side_effect=spawn))
    self.enterContext(patch("backend.service.shutil.which", return_value="/fake/tool"))
    self.enterContext(patch("backend.service.time.monotonic", side_effect=lambda: self.now))

  def test_partial_exit_restarts_only_the_failed_mime_after_backoff(self):
    self.assertEqual(self.service.sync_watchers(), 30)
    text, image = self.processes
    text.poll.return_value = 1
    self.assertEqual(self.service.sync_watchers(), 2)
    self.assertNotIn(text, self.service.watchers)
    self.now += 1
    self.service.sync_watchers()
    self.assertEqual(self.spawn.call_count, 2)
    self.now += 1
    self.service.sync_watchers()
    self.assertEqual(self.spawn.call_count, 3)
    self.assertEqual(self.spawn.call_args.args[0][5], "text")
    self.assertIs(self.service.watcher_slots["image"], image)
    image.terminate.assert_not_called()

  def test_repeated_failures_back_off_and_stable_runtime_resets_delay(self):
    self.service.sync_watchers()
    for expected in [2, 4, 8, 16, 32, 60, 60]:
      self.service.watcher_slots["text"].poll.return_value = 1
      self.service.sync_watchers()
      self.assertEqual(self.service.watcher_retry["text"] - self.now, expected)
      attempts = self.spawn.call_count
      self.now += expected - .1
      self.service.sync_watchers()
      self.assertEqual(self.spawn.call_count, attempts)
      self.now += .1
      self.service.sync_watchers()
      self.assertEqual(self.spawn.call_count, attempts + 1)
    self.now += 31
    self.service.watcher_slots["text"].poll.return_value = 1
    self.service.sync_watchers()
    self.assertEqual(self.service.watcher_retry["text"] - self.now, 2)

  def test_spawn_failure_is_bounded_and_can_recover(self):
    original = self.spawn.side_effect
    self.spawn.side_effect = OSError("temporarily unavailable")
    self.assertEqual(self.service.sync_watchers(), 2)
    self.service.sync_watchers()
    self.assertEqual(self.spawn.call_count, 2)
    self.spawn.side_effect = original
    self.now += 2
    self.service.sync_watchers()
    self.assertEqual(len(self.service.watchers), 2)
    self.assertFalse(self.service.watcher_retry)

  def test_pause_disable_and_shutdown_reap_without_restarting(self):
    for reason in ["pause", "disable", "shutdown"]:
      with self.subTest(reason=reason):
        self.service.stopping.clear()
        self.service.store.settings.update({"clipboardEnabled": True, "clipboardPaused": False})
        self.service.sync_watchers()
        watchers = list(self.service.watchers)
        watchers[0].wait.side_effect = [subprocess.TimeoutExpired("wl-paste", .3), 0]
        if reason == "pause":
          self.service.store.settings["clipboardPaused"] = True
        elif reason == "disable":
          self.service.store.settings["clipboardEnabled"] = False
        else:
          self.service.stopping.set()
        self.assertIsNone(self.service.sync_watchers())
        attempts = self.spawn.call_count
        self.now += 120
        self.assertIsNone(self.service.sync_watchers())
        self.assertEqual(self.spawn.call_count, attempts)
        self.assertFalse(self.service.watchers)
        self.assertFalse(self.service.watcher_retry)
        for watcher in watchers:
          watcher.terminate.assert_called_once()
          watcher.wait.assert_called()
        watchers[0].kill.assert_called_once()
        watchers[1].kill.assert_not_called()

  def test_idle_scheduler_checks_existing_children_without_spawning_more(self):
    timeouts = []
    def wait(timeout):
      timeouts.append(timeout)
      self.now += timeout
      if len(timeouts) == 3:
        self.service.stopping.set()
    with patch.object(self.service.wakeup, "wait", side_effect=wait):
      self.service.poll()
    self.assertEqual(timeouts, [30, 30, 30])
    self.assertEqual(self.spawn.call_count, 2)

  def test_paused_scheduler_can_sleep_without_a_retry_busy_loop(self):
    self.service.sync_watchers()
    self.service.store.settings["clipboardPaused"] = True
    waits = []
    def wait(timeout):
      waits.append(timeout)
      self.service.stopping.set()
    with patch.object(self.service.wakeup, "wait", side_effect=wait):
      self.service.poll()
    self.assertEqual(waits, [None])
    self.assertFalse(self.service.watchers)
    self.assertFalse(self.service.watcher_retry)

  def test_pause_while_scheduler_waits_for_lifecycle_lock_cannot_respawn(self):
    self.service.sync_watchers()
    lock = self.service.watcher_lock
    owner = threading.current_thread()
    waiting = threading.Event()
    class ObservedLock:
      def __enter__(self):
        if threading.current_thread() is not owner:
          waiting.set()
        return lock.__enter__()
      def __exit__(self, *args):
        return lock.__exit__(*args)
    self.service.watcher_lock = ObservedLock()
    results = []
    with lock:
      worker = threading.Thread(target=lambda: results.append(self.service.sync_watchers()))
      worker.start()
      self.assertTrue(waiting.wait(1))
      self.service.store.settings["clipboardPaused"] = True
      self.service.stop_watchers()
    worker.join(timeout=1)
    self.assertFalse(worker.is_alive())
    self.assertEqual(results, [None])
    self.assertEqual(self.spawn.call_count, 2)
    self.assertFalse(self.service.watchers)

  def test_real_exited_and_stubborn_helpers_are_reaped(self):
    children = []
    directory = self.service.store.directory
    def spawn(argv, **kwargs):
      mime = argv[5]
      script = "" if mime == "text" else (
        "import pathlib,signal,time\n"
        "signal.signal(signal.SIGTERM,signal.SIG_IGN)\n"
        "pathlib.Path(" + repr(str(directory / "ready")) + ").touch()\n"
        "time.sleep(60)\n")
      child = self.actual_popen([sys.executable, "-c", script],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
      children.append(child)
      return child
    self.spawn.side_effect = spawn
    try:
      self.service.sync_watchers()
      deadline = time.perf_counter() + 3
      while time.perf_counter() < deadline:
        if children[0].poll() is not None and (directory / "ready").exists():
          break
        time.sleep(.01)
      self.assertIsNotNone(children[0].poll())
      self.assertTrue((directory / "ready").exists())
      self.service.sync_watchers()
      self.service.stopping.set()
      self.service.stop_watchers()
      for child in children:
        self.assertIsNotNone(child.poll())
        with self.assertRaises(ChildProcessError):
          os.waitpid(child.pid, os.WNOHANG)
    finally:
      for child in children:
        if child.poll() is None:
          child.kill()
          child.wait(timeout=2)
