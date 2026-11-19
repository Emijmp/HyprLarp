import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest

from tools.benchmark import process_tree, sample


class ResourceMeasurementsTests(unittest.TestCase):
  def test_worker_thread_children_belong_to_the_measured_tree(self):
    with tempfile.TemporaryDirectory() as directory:
      marker = Path(directory) / "child.pid"
      code = '''import pathlib,subprocess,sys,threading
def worker():
 p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(15)'])
 pathlib.Path(sys.argv[1]).write_text(str(p.pid))
 p.wait()
t=threading.Thread(target=worker)
t.start()
t.join()
'''
      parent = subprocess.Popen([sys.executable, "-c", code, str(marker)], start_new_session=True)
      try:
        deadline = time.monotonic() + 3
        while not marker.exists() and time.monotonic() < deadline:
          time.sleep(0.02)
        self.assertTrue(marker.exists())
        child = int(marker.read_text())
        tree = process_tree(parent.pid)
        self.assertIn(child, tree)
        self.assertEqual(tree[child]["parent"], parent.pid)
        self.assertGreaterEqual(tree[parent.pid]["threads"], 2)
        report = sample(parent.pid, .2, "test", interval=.1)
        self.assertEqual(report["processes_end"], 2)
        self.assertGreater(report["rss_mib_end"], 0)
      finally:
        if parent.poll() is None:
          os.killpg(parent.pid, signal.SIGTERM)
        parent.wait(timeout=3)

  def test_a_finished_process_is_not_reported_as_an_empty_success(self):
    process = subprocess.Popen([sys.executable, "-c", "pass"])
    process.wait(timeout=3)
    with self.assertRaises(RuntimeError):
      sample(process.pid, .1, "test")
