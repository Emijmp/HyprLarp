"""The standalone bridge keeps a noninteractive removal preview without core."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from backend.service import ROOT
from tools.install_greeter import SYNC_FILES


class StandaloneGreeterCliTests(unittest.TestCase):
  def test_standalone_removal_finishes_after_deleting_its_own_controller(self):
    with tempfile.TemporaryDirectory(prefix='hyprlarp-greeter-self-removal-') as folder:
      home = Path(folder) / 'home'
      bridge = home / '.local/share/hyprlarp-greeter'
      for name in SYNC_FILES:
        target = bridge / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, target)
      (bridge / 'installation.json').write_text(json.dumps({'backup': '/var/backups/hyprlarp-greeter/20261116-175438-932805'}))
      foreign = bridge / 'personal-notes.txt'
      foreign.write_text('preserve this personal file')
      calls = home / 'calls.json'
      environment = {**os.environ, 'HOME': str(home), 'XDG_DATA_HOME': str(home / '.local/share'),
        'XDG_CONFIG_HOME': str(home / '.config'), 'XDG_STATE_HOME': str(home / '.local/state'),
        'PYTHONDONTWRITEBYTECODE': '1'}
      code = '''
import json,sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from tools import install_greeter as controller
from backend import greeter
bridge=Path(sys.argv[1])
assert Path(controller.__file__).is_relative_to(bridge)
assert Path(greeter.__file__).is_relative_to(bridge)
calls=[]
def privileged(flag, username, token=None, *, script=None):
  assert script and script.is_file()
  # The copied controller must remain usable after its installed files vanish.
  assert (script.parents[1]/'greeter/shell.qml').is_file()
  assert (script.parents[1]/'assets/hyprlarp.svg').is_file()
  if flag=='--system-commit':
    assert not (bridge/'backend/greeter.py').exists()
  calls.append(flag)
  return {'status':'uninstalled' if flag=='--system-uninstall' else 'committed','transaction':'a'*32}
controller.ensure_privileges=lambda:None
controller.privileged=privileged
controller.unit_state=lambda:{name:{'enabled':False,'active':False,'present':True,'runtime':False} for name in ['path','service']}
controller.stop_units=lambda:None
controller.restore_units=lambda previous:None
sys.argv=['hyprlarp-greeter','uninstall']
greeter.main()
Path.home().joinpath('calls.json').write_text(json.dumps(calls))
'''
      result = subprocess.run([sys.executable, '-c', code, str(bridge)], cwd=folder,
        env=environment, capture_output=True, text=True, timeout=8)
      self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
      self.assertEqual(json.loads(result.stdout)['status'], 'uninstalled')
      self.assertEqual(json.loads(calls.read_text()), ['--system-uninstall', '--system-commit'])
      self.assertFalse((bridge / 'backend/greeter.py').exists())
      self.assertEqual(foreign.read_text(), 'preserve this personal file')

  def test_removal_preview_works_with_only_the_standalone_bundle_and_writes_nothing(self):
    with tempfile.TemporaryDirectory(prefix='hyprlarp-greeter-cli-') as folder:
      home = Path(folder) / 'home with spaces'
      data = home / '.local/share'
      bridge = data / 'hyprlarp-greeter'
      for name in SYNC_FILES:
        target = bridge / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, target)
      (bridge / 'installation.json').write_text(json.dumps({'backup': '/var/backups/hyprlarp-greeter/20261116-175438-932805'}))
      binaries = home / 'guard-bin'
      binaries.mkdir()
      called = home / 'unexpected-command'
      for name in ['sudo', 'pkexec', 'systemctl']:
        script = binaries / name
        script.write_text('#!' + sys.executable + '\nfrom pathlib import Path\nPath(' + repr(str(called)) + ').write_text("called")\nraise SystemExit(1)\n')
        script.chmod(0o700)
      environment = {**os.environ, 'HOME': str(home), 'XDG_DATA_HOME': str(data),
        'XDG_CONFIG_HOME': str(home / '.config'), 'XDG_STATE_HOME': str(home / '.local/state'),
        'PATH': str(binaries) + os.pathsep + os.environ.get('PATH', ''), 'PYTHONDONTWRITEBYTECODE': '1'}
      def snapshot():
        return {str(path.relative_to(home)): hashlib.sha256(path.read_bytes()).hexdigest()
          for path in home.rglob('*') if path.is_file()}
      before = snapshot()
      result = subprocess.run([sys.executable, str(bridge / 'backend/greeter.py'), 'uninstall', '--dry-run'],
        cwd=folder, env=environment, capture_output=True, text=True, timeout=5)
      self.assertEqual(result.returncode, 0, result.stderr)
      plan = json.loads(result.stdout)
      self.assertEqual(plan['status'], 'dry-run')
      self.assertEqual(plan['action'], 'uninstall')
      self.assertIn(str(bridge), plan['targets'])
      self.assertEqual(snapshot(), before)
      self.assertFalse(called.exists())
      self.assertFalse((data / 'hyprlarp').exists())

  def test_dry_run_cannot_accidentally_execute_a_synchronization(self):
    result = subprocess.run([sys.executable, str(ROOT / 'backend/greeter.py'), 'sync', '--dry-run'],
      capture_output=True, text=True, timeout=5)
    self.assertEqual(result.returncode, 2)
    self.assertIn('solo se admite con uninstall', result.stderr)


if __name__ == '__main__':
  unittest.main()
