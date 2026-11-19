import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from backend import displays
from backend.service import DEFAULTS, ROOT, Store


def fixture():
  return displays.normalize([
    {'id': 0, 'name': 'eDP-1', 'description': 'Laptop', 'make': 'BOE', 'width': 1920, 'height': 1080,
      'scale': 1.25, 'refreshRate': 60, 'x': 0, 'y': 0, 'mirrorOf': 'none',
      'availableModes': ['1920x1080@60.00Hz', '1920x1080@40.00Hz', '1280x720@60.00Hz']},
    {'id': 1, 'name': 'HDMI-A-1', 'description': 'Projector', 'make': 'TEST', 'width': 1920, 'height': 1080,
      'scale': 1, 'refreshRate': 60, 'x': 1536, 'y': 0, 'mirrorOf': 'none',
      'availableModes': ['1920x1080@60.00Hz', '1280x720@60.00Hz', '1024x768@60.00Hz']}
  ])


class DisplayModelTests(unittest.TestCase):
  def setUp(self):
    self.outputs = fixture()
    self.plan = displays.plan_for(self.outputs)

  def test_native_mirror_id_strings_are_resolved_to_connector_names(self):
    outputs = displays.normalize([{'id': 0, 'name': 'eDP-1'}, {'id': 1, 'name': 'HDMI-A-1', 'mirrorOf': '0'}])
    self.assertEqual(outputs[1]['mirror'], 'eDP-1')

  def test_compositor_emergency_output_does_not_hide_disabled_physical_screens(self):
    outputs = displays.normalize([{'id': 0, 'name': 'eDP-1', 'disabled': True}, {'id': 2, 'name': 'FALLBACK'}])
    self.assertEqual([output['name'] for output in outputs], ['eDP-1'])
    self.assertFalse(outputs[0]['enabled'])

  def test_current_native_modes_are_normalized_without_inventing_displays(self):
    self.assertEqual(self.outputs[0]['mode'], '1920x1080@60')
    self.assertEqual(self.outputs[0]['modes'][1], '1920x1080@40')
    self.assertEqual(displays.normalize([]), [])
    self.assertEqual(displays.validate(self.plan, self.outputs), self.plan)

  def test_all_off_self_mirroring_and_mirror_chains_are_rejected(self):
    for change in [lambda plan: [entry.update(enabled=False) for entry in plan],
        lambda plan: plan[0].update(mirror='eDP-1'),
        lambda plan: (plan[0].update(mirror='HDMI-A-1'), plan[1].update(mirror='eDP-1')),
        lambda plan: (plan[0].update(enabled=False), plan[1].update(mirror='eDP-1'))]:
      plan = copy.deepcopy(self.plan)
      change(plan)
      with self.assertRaises(ValueError):
        displays.validate(plan, self.outputs)

  def test_only_advertised_modes_can_be_selected(self):
    for mode in ['10000x10000@999', '1920x1080@144', '1920x1080@60; os.execute("bad")']:
      with self.assertRaises(ValueError):
        displays.validate([{**self.plan[0], 'mode': mode}, self.plan[1]], self.outputs)

  def test_new_or_removed_outputs_invalidate_an_unapplied_draft(self):
    with self.assertRaises(ValueError):
      displays.validate(self.plan, self.outputs[:1])
    with self.assertRaises(ValueError):
      displays.validate(self.plan[:1], self.outputs)

  def test_invalid_scales_coordinates_and_transforms_are_rejected(self):
    for change in [{'scale': True}, {'scale': 0}, {'scale': float('nan')}, {'scale': 1.3},
        {'x': 3.4}, {'y': 40000}, {'transform': True}, {'transform': 8}]:
      with self.assertRaises(ValueError):
        displays.validate([{**self.plan[0], **change}, self.plan[1]], self.outputs)

  def test_extended_screens_cannot_overlap_and_mirroring_is_explicit(self):
    plan = [self.plan[0], {**self.plan[1], 'x': 0}]
    with self.assertRaises(ValueError):
      displays.validate(plan, self.outputs)
    plan[1]['mirror'] = 'eDP-1'
    self.assertEqual(displays.validate(plan, self.outputs)[1]['mirror'], 'eDP-1')

  def test_logical_placement_accounts_for_scale_and_rotation(self):
    self.assertEqual(displays.logical_size(self.plan[0], self.outputs), (1536, 864))
    self.assertEqual(displays.logical_size({**self.plan[0], 'transform': 1}, self.outputs), (864, 1536))

  def test_four_projection_presets_preserve_source_and_input_data(self):
    original = copy.deepcopy(self.outputs)
    one = displays.preset('internal-only', self.outputs)
    duplicate = displays.preset('duplicate', self.outputs)
    extended = displays.preset('extend', self.outputs)
    external = displays.preset('external-only', self.outputs)
    self.assertEqual([entry['name'] for entry in one if entry['enabled']], ['eDP-1'])
    self.assertEqual(duplicate[1]['mirror'], 'eDP-1')
    self.assertEqual(extended[1]['x'], 1536)
    self.assertEqual([entry['name'] for entry in external if entry['enabled']], ['HDMI-A-1'])
    self.assertEqual(self.outputs, original)

  def test_projection_requires_a_real_secondary_output(self):
    for mode in ['duplicate', 'extend', 'external-only']:
      with self.assertRaises(ValueError):
        displays.preset(mode, self.outputs[:1])
    self.assertTrue(displays.preset('internal-only', self.outputs[:1])[0]['enabled'])

  def test_user_can_choose_the_projector_and_mirror_source(self):
    plan = displays.preset('duplicate', self.outputs, 'HDMI-A-1', 'eDP-1')
    self.assertEqual(next(entry for entry in plan if entry['name'] == 'eDP-1')['mirror'], 'HDMI-A-1')

  def test_new_destination_is_enabled_before_the_old_source_is_disabled(self):
    with patch.object(displays, 'native') as native:
      displays.apply(displays.preset('external-only', self.outputs))
    expression = native.call_args.args[0][1]
    self.assertLess(expression.index('HDMI-A-1'), expression.index('eDP-1'))

  def test_confirmation_requires_the_image_actually_applied(self):
    self.assertTrue(displays.matches(self.plan, self.outputs))
    changed = copy.deepcopy(self.plan)
    changed[0]['scale'] = 1
    self.assertFalse(displays.matches(changed, self.outputs))
    changed = displays.preset('duplicate', self.outputs)
    self.assertFalse(displays.matches(changed, self.outputs))

  def test_profile_identity_includes_hardware_not_just_connector_names(self):
    changed = copy.deepcopy(self.outputs)
    changed[1]['identity'] += '|different-projector'
    self.assertNotEqual(displays.topology(changed), displays.topology(self.outputs))
    self.assertEqual(displays.topology(list(reversed(changed))), displays.topology(changed))

  def test_disconnect_restoration_never_leaves_the_remaining_laptop_disabled(self):
    before = displays.preset('external-only', self.outputs)
    with patch.object(displays, 'query', return_value=self.outputs[:1]), patch.object(displays, 'apply') as apply, patch.object(displays, 'wait_applied'):
      displays.restore(before)
    self.assertTrue(apply.call_args.args[0][0]['enabled'])
    self.assertEqual(apply.call_args.args[0][0]['mirror'], '')

  def test_projection_shortcut_migration_preserves_existing_bindings(self):
    with tempfile.TemporaryDirectory() as temporary:
      directory = Path(temporary)
      settings = copy.deepcopy(DEFAULTS)
      settings['shortcuts'].pop('displays')
      settings['shortcuts']['launcher'] = 'SUPER, R'
      (directory / 'settings.json').write_text(json.dumps(settings))
      store = Store(directory)
      self.assertEqual(store.settings['shortcuts']['launcher'], 'SUPER, R')
      self.assertEqual(store.settings['shortcuts']['displays'], 'SUPER SHIFT, P')

  @unittest.skipUnless(shutil.which('node'), 'Node verifies the shared layout helpers')
  def test_visual_layout_helpers(self):
    subprocess.run(['node', str(ROOT / 'tests/test_displays.js')], check=True, capture_output=True, text=True)


class DisplayGuardianTests(unittest.TestCase):
  def setUp(self):
    self.temporary = tempfile.TemporaryDirectory(prefix='dp-')
    self.addCleanup(self.temporary.cleanup)
    self.directory = Path(self.temporary.name)
    self.store = Store(self.directory / 'config')
    self.fake = self.directory / 'bin'
    self.fake.mkdir()
    self.state = self.directory / 'native.json'
    self.state.write_text(json.dumps(fixture()))
    # This helper is the entire fake native service; it never addresses Wayland.
    script = self.fake / 'hyprctl'
    script.write_text('''#!''' + sys.executable + r'''
import json,os,re,sys
from pathlib import Path
path=Path(os.environ['HYPRLARP_FAKE_DISPLAYS'])
outputs=json.loads(path.read_text())
if sys.argv[1:]==['-j','monitors','all']:
 raw=[]
 for i,p in enumerate(outputs):
  w,h,r=p['mode'].replace('@','x').split('x')
  raw.append({'id':i,'name':p['name'],'description':p['description'],'make':'BOE' if i==0 else 'TEST',
   'width':int(w),'height':int(h),'refreshRate':float(r),'scale':p['scale'],'transform':p['transform'],
   'x':p['x'],'y':p['y'],'disabled':not p['enabled'],'mirrorOf':p['mirror'] or 'none','availableModes':p['modes']})
 print(json.dumps(raw))
elif sys.argv[1]=='eval':
 for table in re.findall(r'hl.monitor\(\{(.*?)\}\)',sys.argv[2]):
  name=re.search(r'output = "([^"]+)"',table)[1]
  p=next(p for p in outputs if p['name']==name)
  for key,target in [('disabled','enabled'),('scale','scale'),('transform','transform'),('mode','mode'),('mirror','mirror'),('position','position')]:
   match=re.search(r'\b'+key+r' = ("[^"]*"|true|false|[0-9.]+)',table)
   if not match:continue
   value=json.loads(match[1])
   if key=='disabled':p['enabled']=not value
   elif key=='position':p['x'],p['y']=map(int,value.split('x'))
   elif key=='mode' and value=='preferred':p['mode']=p['modes'][0]
   else:p[target]=value
 path.write_text(json.dumps(outputs));print('ok')
else:sys.exit(1)
''')
    script.chmod(0o755)
    self.environment = {'PATH': str(self.fake) + ':' + os.environ.get('PATH', ''),
      'XDG_RUNTIME_DIR': str(self.directory), 'HYPRLAND_INSTANCE_SIGNATURE': 'fixture',
      'HYPRLARP_FAKE_DISPLAYS': str(self.state)}
    self.patch = patch.dict(os.environ, self.environment)
    self.patch.start()
    self.addCleanup(self.patch.stop)
    self.events = []
    self.service = SimpleNamespace(store=self.store, preview=False, emit=lambda *value: self.events.append(value))
    self.controller = displays.Displays(self.service, None)
    self.addCleanup(self.cancel)

  def cancel(self):
    try:
      pending = self.controller.pending()
      if pending:
        displays.request(self.controller.folder, 'revert')
    except (OSError, ValueError, RuntimeError):
      pass
    if self.controller.timer:
      self.controller.timer.cancel()

  def test_confirmed_layout_is_saved_and_cancelled_layout_is_restored(self):
    outputs = displays.query()
    self.controller.test(displays.preset('duplicate', outputs))
    pending = self.controller.pending()
    self.assertIsNotNone(pending)
    self.assertFalse(self.controller.profiles.exists())
    self.controller.handle('displays-confirm', {'token': pending['token']})
    saved = displays.read_profiles(self.controller.profiles)
    self.assertEqual(len(saved['profiles']), 1)
    self.assertEqual(displays.query()[1]['mirror'], 'eDP-1')
    self.controller.test(displays.preset('external-only', displays.query()))
    pending = self.controller.pending()
    self.controller.handle('displays-revert', {'token': pending['token']})
    self.assertTrue(displays.query()[0]['enabled'])
    self.assertEqual(displays.query()[1]['mirror'], 'eDP-1')

  def test_reconnected_controller_can_confirm_an_existing_trial(self):
    self.controller.test(displays.preset('duplicate', displays.query()))
    other = displays.Displays(self.service, None)
    pending = other.pending()
    self.assertIsNotNone(pending)
    other.handle('displays-confirm', {'token': pending['token']})
    self.assertIsNone(self.controller.pending())

  def test_late_or_wrong_confirmation_cannot_save_a_layout(self):
    self.controller.test(displays.preset('duplicate', displays.query()))
    with self.assertRaises(ValueError):
      self.controller.handle('displays-confirm', {'token': 'wrong'})
    self.assertFalse(self.controller.profiles.exists())

  def test_preview_never_changes_native_outputs(self):
    self.service.preview = True
    before = self.state.read_bytes()
    with self.assertRaises(RuntimeError):
      self.controller.test(displays.preset('duplicate', displays.query()))
    self.assertEqual(self.state.read_bytes(), before)

  def test_guardian_restores_after_the_requesting_backend_exits(self):
    client = self.directory / 'client.py'
    client.write_text('import os,sys,json\nfrom pathlib import Path\nfrom types import SimpleNamespace\n'
      + 'sys.path.insert(0,' + repr(str(ROOT)) + ')\nfrom backend import displays\nfrom backend.service import Store\n'
      + 'controller=displays.Displays(SimpleNamespace(store=Store(Path(' + repr(str(self.store.directory)) + ')),preview=False,emit=lambda *args:None),None)\n'
      + 'controller.test(displays.preset("duplicate",displays.query()))\n'
      + 'print(json.dumps(controller.pending()),flush=True)\nos._exit(0)\n')
    result = subprocess.run([sys.executable, str(client)], capture_output=True, text=True, timeout=8)
    self.assertEqual(result.returncode, 0, result.stderr)
    pending = json.loads(result.stdout)
    self.assertEqual(displays.query()[1]['mirror'], 'eDP-1')
    deadline = time.monotonic() + displays.CONFIRM_SECONDS + 5
    while time.monotonic() < deadline:
      folder = self.controller.runtime() / pending['token']
      if (folder / 'result.json').exists():
        break
      time.sleep(.2)
    status = json.loads((folder / 'result.json').read_text())
    self.assertEqual(status['status'], 'reverted')
    self.assertEqual(displays.query()[1]['mirror'], '')
    self.assertTrue(displays.query()[0]['enabled'])
    self.assertFalse(self.controller.profiles.exists())
