"""The idle supervisor sleeps while bounded recovery still replaces stuck UI."""

import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest

from backend.supervisor import notify_exit


class SupervisorEfficiencyTests(unittest.TestCase):
  def setUp(self):
    self.temporary = tempfile.TemporaryDirectory(prefix="hyprlarp-idle-supervisor-")
    self.addCleanup(self.temporary.cleanup)
    self.root = Path(self.temporary.name)
    self.runtime = self.root / "runtime"
    self.runtime.mkdir(mode=0o700)
    self.renderer = self.root / "renderer"
    self.renderer.write_text("#!" + sys.executable + "\n"
      "import os,signal,time\n"
      "signal.signal(signal.SIGTERM,signal.SIG_IGN)\n"
      "while True:time.sleep(1)\n")
    self.renderer.chmod(0o755)

  def launch(self, *, fallback=False):
    script = ("import os,sys\nfrom pathlib import Path\nimport backend.supervisor as supervisor\n"
      "counts={}\n"
      "def ready(child,mode):\n"
      " counts[child.pid]=counts.get(child.pid,0)+1\n"
      " if counts[child.pid]>=3:\n"
      "  (Path(sys.argv[1])/'ready').write_text(str(child.pid)+':'+mode)\n"
      " return True\n")
    if fallback:
      script += "def unavailable(*args):raise OSError('waitid unavailable')\nsupervisor.os.waitid=unavailable\n"
    script += "sys.exit(supervisor.supervise(sys.argv[1],sys.argv[2],readiness=ready,shutdown_timeout=.08))\n"
    environment = {**os.environ, "XDG_RUNTIME_DIR": str(self.runtime), "HYPRLAND_INSTANCE_SIGNATURE": "fixture"}
    environment.pop("WAYLAND_DISPLAY", None)
    process = subprocess.Popen([sys.executable, "-c", script, str(self.root), str(self.renderer)],
      env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    def cleanup():
      if process.poll() is None:
        process.terminate()
        try:
          process.wait(timeout=4)
        except subprocess.TimeoutExpired:
          process.kill()
          process.wait(timeout=3)
      process.stderr.close()
    self.addCleanup(cleanup)
    return process

  def ready(self, process, mode, previous=None):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
      if process.poll() is not None:
        self.fail(process.stderr.read())
      try:
        pid, actual = (self.root / "ready").read_text().split(":")
        if actual == mode and int(pid) != previous:
          os.kill(int(pid), 0)
          return int(pid)
      except (OSError, ValueError):
        pass
      time.sleep(.02)
    self.fail("The supervisor failed to start " + mode)

  @unittest.skipUnless(hasattr(os, "waitid") and hasattr(os, "WNOWAIT"), "waitid WNOWAIT required")
  def test_steady_state_has_no_periodic_supervisor_wakeups(self):
    process = self.launch()
    self.ready(process, "normal")
    # Allow the readiness callback to return and the one-shot waiter to start.
    time.sleep(.1)
    def wakeups():
      status = (Path("/proc") / str(process.pid) / "status").read_text()
      return int(next(line.split()[1] for line in status.splitlines() if line.startswith("voluntary_ctxt_switches:")))
    before = wakeups()
    time.sleep(.9)
    self.assertIsNone(process.poll())
    self.assertLess(wakeups() - before, 8, "The steady supervisor is waking repeatedly instead of waiting for child exit")

  def test_exit_notification_does_not_reap_or_lock_the_child(self):
    child = subprocess.Popen([sys.executable, "-c", "raise SystemExit(7)"])
    self.addCleanup(child.wait)
    event = threading.Event()
    watcher = threading.Thread(target=notify_exit, args=(child, event), daemon=True)
    watcher.start()
    self.assertTrue(event.wait(2))
    watcher.join(timeout=1)
    if hasattr(os, "waitid") and hasattr(os, "WNOWAIT"):
      self.assertIsNone(child.returncode)
    self.assertEqual(child.wait(timeout=2), 7)

  def test_control_replaces_stuck_renderers_without_stale_exit_notifications(self):
    process = self.launch()
    normal = self.ready(process, "normal")
    os.kill(process.pid, signal.SIGUSR2)
    recovery = self.ready(process, "recovery", normal)
    with self.assertRaises(ProcessLookupError):
      os.kill(normal, 0)
    os.kill(process.pid, signal.SIGUSR1)
    replacement = self.ready(process, "normal", normal)
    with self.assertRaises(ProcessLookupError):
      os.kill(recovery, 0)
    time.sleep(.6)
    self.assertIsNone(process.poll())
    os.kill(replacement, 0)
    self.assertEqual((self.root / "ready").read_text(), str(replacement) + ":normal")
    tasks = list((Path("/proc") / str(process.pid) / "task").iterdir())
    self.assertLessEqual(len(tasks), 3, "Previous renderer waiters must not accumulate")

  def test_fallback_waiter_keeps_shutdown_bounded_for_sigterm_ignoring_child(self):
    process = self.launch(fallback=True)
    child = self.ready(process, "normal")
    started = time.monotonic()
    process.terminate()
    self.assertEqual(process.wait(timeout=3), 0)
    self.assertLess(time.monotonic() - started, 2)
    with self.assertRaises(ProcessLookupError):
      os.kill(child, 0)
