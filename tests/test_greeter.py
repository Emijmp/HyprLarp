"""Appearance payloads must be usable before login and stay within secure-sync-v1."""

import copy
import json
import os
from pathlib import Path
import tempfile
import shlex
import shutil
import subprocess
import time
import unittest
from unittest.mock import patch

try:
  import tomllib
except ModuleNotFoundError:
  raise unittest.SkipTest('La instalación opcional del greeter requiere Python 3.11+')

from backend import greeter
from greeter import model as greeter_model
from tools.deployment import copy_sources
from tools.install_greeter import merge_greeter, session_launcher


@unittest.skipUnless(shutil.which('quickshell'), 'Quickshell unavailable')
class GreeterWindowTests(unittest.TestCase):
  """Run the actual login window, including Qt close-event delivery."""

  def setUp(self):
    temporary = tempfile.TemporaryDirectory(prefix='hyprlarp-greeter-window-')
    self.addCleanup(temporary.cleanup)
    self.folder = Path(temporary.name)
    self.configuration = greeter.ROOT / 'greeter/shell.qml'

  def start(self, *, fullscreen, caps=False):
    runtime = self.folder / 'runtime'
    runtime.mkdir(mode=0o700)
    state = self.folder / 'state'
    state.mkdir()
    led = self.folder / 'leds/input3::capslock'
    led.mkdir(parents=True)
    self.caps = led / 'brightness'
    self.caps.write_text('1' if caps else '0')
    (state / 'sync.toml').write_text('[appearance.wallpaper]\npath = "color:#000000"\n')
    self.environment = {**os.environ, 'QT_QPA_PLATFORM': 'offscreen', 'QT_QUICK_BACKEND': 'software',
      'QT_QUICK_CONTROLS_STYLE': 'Basic', 'XDG_RUNTIME_DIR': str(runtime),
      'XDG_CACHE_HOME': str(self.folder / 'cache'), 'HYPRLARP_GREETER_PREVIEW': '1',
      'HYPRLARP_GREETER_TEST': '1', 'HYPRLARP_GREETER_TEST_FULLSCREEN': '1' if fullscreen else '0',
      'HYPRLARP_GREETER_STATE_DIR': str(state), 'HYPRLARP_GREETER_PREFERENCES': str(state / 'layout.json')}
    self.environment['HYPRLARP_GREETER_TEST_LEDS'] = str(led.parent)
    for name in ['GREETD_SOCK', 'WAYLAND_DISPLAY', 'DISPLAY']:
      self.environment.pop(name, None)
    self.log = self.folder / 'window.log'
    output = self.log.open('w')
    self.addCleanup(output.close)
    self.process = subprocess.Popen(['quickshell', '--path', str(self.configuration), '--no-color'],
      env=self.environment, stdout=output, stderr=subprocess.STDOUT)
    self.addCleanup(self.stop)
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
      if self.process.poll() is not None:
        self.fail('Greeter exited during startup:\n' + self.log.read_text())
      try:
        if json.loads(self.ipc('status'))['ready'] and json.loads(self.ipc('windows')):
          return
      except (RuntimeError, ValueError):
        pass
      time.sleep(0.05)
    self.fail('Greeter did not become ready:\n' + self.log.read_text())

  def stop(self):
    if self.process.poll() is None:
      self.process.terminate()
      try:
        self.process.wait(timeout=3)
      except subprocess.TimeoutExpired:
        self.process.kill()
        self.process.wait(timeout=3)

  def ipc(self, method, *arguments):
    result = subprocess.run(['quickshell', '--path', str(self.configuration), 'ipc', 'call',
      'greeterTest', method, *arguments], env=self.environment, capture_output=True, text=True, timeout=3)
    if result.returncode:
      raise RuntimeError(result.stdout + result.stderr)
    return result.stdout.strip()

  def test_login_covers_output_without_decorations_and_rejects_close_requests(self):
    self.start(fullscreen=True)
    windows = json.loads(self.ipc('windows'))
    self.assertTrue(windows)
    for index, window in enumerate(windows):
      self.assertTrue(window['visible'])
      self.assertTrue(window['frameless'])
      self.assertEqual((window['width'], window['height']), (window['screenWidth'], window['screenHeight']))
      self.assertEqual(self.ipc('closeWindow', str(index)), 'false')
    self.assertTrue(json.loads(self.ipc('status'))['ready'])
    self.assertTrue(all(window['visible'] for window in json.loads(self.ipc('windows'))))
    self.assertIsNone(self.process.poll())

  def test_preview_remains_a_normal_window_and_can_close(self):
    self.start(fullscreen=False)
    self.assertTrue(all(not window['frameless'] for window in json.loads(self.ipc('windows'))))
    # Qt.quit may stop the IPC connection before its reply is flushed.
    try:
      self.ipc('closeWindow', '0')
    except RuntimeError:
      pass
    self.assertEqual(self.process.wait(timeout=5), 0, self.log.read_text())

  def test_caps_lock_is_detected_on_startup_and_updates_without_typing(self):
    self.start(fullscreen=True, caps=True)
    for expected, value in [(True, '1'), (False, '0')]:
      self.caps.write_text(value)
      deadline = time.monotonic() + 3
      while time.monotonic() < deadline:
        current = json.loads(self.ipc('status'))['keyboard']
        if current['capsLock'] is expected:
          break
        time.sleep(.05)
      self.assertIs(current['capsLock'], expected)
      self.assertTrue(current['layout'])


class GreeterTests(unittest.TestCase):
  def setUp(self):
    self.temporary = tempfile.TemporaryDirectory(prefix='hyprlarp-greeter-test-')
    self.addCleanup(self.temporary.cleanup)
    self.root = Path(self.temporary.name)
    self.settings = self.root / 'settings.json'
    self.waypaper = self.root / 'waypaper.ini'
    self.palettes = json.loads((greeter.ROOT / 'config/palettes.json').read_text())
    self.settings.write_text(json.dumps({'theme': 'amoled', 'wallpaper': '', 'radius': 8}))

  def update(self, **values):
    current = json.loads(self.settings.read_text())
    self.settings.write_text(json.dumps({**current, **values}))

  @unittest.skipUnless(Path('/usr/bin/noctalia-greeter-session').is_file(), 'native session launcher unavailable')
  def test_full_native_session_launcher_selects_hyprlarp_instead_of_noctalia(self):
    frontend = self.root / 'hyprlarp-ui'
    frontend.write_text('#!/bin/sh\nexit 0\n')
    frontend.chmod(0o755)
    marker = self.root / 'selected-ui'
    compositor = self.root / 'compositor'
    compositor.write_text('#!/bin/sh\nprintf "%s" "$GREETER_BIN" > ' + shlex.quote(str(marker)) + '\n')
    compositor.chmod(0o755)
    session = self.root / 'session'
    session.write_text(session_launcher(frontend))
    session.chmod(0o755)
    binaries = self.root / 'bin'
    binaries.mkdir()
    bus = binaries / 'dbus-run-session'
    bus.write_text('#!/bin/sh\nif [ "$1" = "--" ]; then shift; fi\nexec "$@"\n')
    bus.chmod(0o755)
    environment = {**os.environ, 'PATH': str(binaries) + ':' + os.environ.get('PATH', ''),
      'NOCTALIA_GREETER_COMPOSITOR_BIN': str(compositor), 'NOCTALIA_GREETER_LOG': 'stderr'}
    environment.pop('GREETD_SOCK', None)
    result = subprocess.run([str(session)], env=environment, capture_output=True, text=True, timeout=5)
    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
    self.assertEqual(marker.read_text(), str(frontend))

  def test_amoled_exports_complete_monochrome_palette_and_readable_buttons(self):
    look = greeter.appearance(json.loads(self.settings.read_text()), self.palettes)
    self.assertEqual(len(look['palette']), 16)
    self.assertEqual(look['palette']['surface'], '#000000')
    self.assertEqual(look['palette']['outline'], '#ffffff')
    self.assertEqual(look['palette']['on_primary'], '#000000')
    self.assertEqual(look['font_family'], 'Inter')
    self.assertEqual(look['theme_mode'], 'dark')
    self.assertAlmostEqual(look['corner_radius_scale'], 8 / 12)

  def test_custom_light_palette_and_panel_override_follow_shell(self):
    custom = {**self.palettes['amoled'], 'background': '#eeeeee', 'surface': '#eeeeee',
      'raised': '#e0e0e0', 'moduleSurface': '#e5e5e5', 'accent': '#111111'}
    look = greeter.appearance({'theme': 'custom', 'customPalette': custom, 'accent': '#ff0000',
      'font': 'JetBrains Mono', 'radius': 8, 'cornerRadii': {'panel': 0}}, self.palettes)
    self.assertEqual(look['theme_mode'], 'light')
    self.assertEqual(look['palette']['primary'], '#111111')
    self.assertEqual(look['palette']['on_primary'], '#ffffff')
    self.assertEqual(look['corner_radius_scale'], 0)

  def test_wallpaper_is_copied_and_never_references_private_home_path(self):
    image = self.root / 'fondo ñ # 100% ".jpg'
    image.write_bytes(b'wallpaper fixture')
    self.update(wallpaper=image.as_uri())
    files, information = greeter.payload(self.settings, self.waypaper)
    config = tomllib.loads(files['sync.toml'].decode())
    self.assertEqual(files['wallpaper.jpg'], image.read_bytes())
    self.assertEqual(config['appearance']['wallpaper']['path'], '/var/lib/noctalia-greeter/wallpaper.jpg')
    self.assertEqual(information['wallpaper'], str(image))
    self.assertEqual(set(config), {'appearance'})

  def test_solid_theme_removes_previous_staged_image(self):
    destination = self.root / 'staging'
    image = self.root / 'wallpaper.png'
    image.write_bytes(b'fixture')
    self.update(wallpaper=str(image))
    greeter.export(greeter.payload(self.settings, self.waypaper)[0], destination)
    self.update(wallpaper='')
    files, information = greeter.payload(self.settings, self.waypaper)
    greeter.export(files, destination)
    self.assertEqual([path.name for path in destination.iterdir()], ['sync.toml'])
    self.assertEqual(tomllib.loads((destination / 'sync.toml').read_text())['appearance']['wallpaper']['path'], 'color:#000000')

  def test_waypaper_uses_its_current_file_and_fill_without_interpolation(self):
    image = self.root / 'actual 100%.webp'
    image.write_bytes(b'external fixture')
    self.waypaper.write_text('[Settings]\nwallpaper = ' + str(image) + '\nfill = fit\n')
    self.update(wallpaperProvider='external', wallpaper='/old/internal.jpg')
    files, _ = greeter.payload(self.settings, self.waypaper)
    look = tomllib.loads(files['sync.toml'].decode())['appearance']
    self.assertEqual(files['wallpaper.webp'], image.read_bytes())
    self.assertEqual(look['wallpaper']['fill_mode'], 'fit')

  def test_failed_image_read_keeps_previous_staged_payload(self):
    destination = self.root / 'staging'
    initial = greeter.payload(self.settings, self.waypaper)[0]
    greeter.export(initial, destination)
    self.update(wallpaper=str(self.root / 'missing.jpg'))
    with self.assertRaises(OSError):
      greeter.payload(self.settings, self.waypaper)
    self.assertEqual((destination / 'sync.toml').read_bytes(), initial['sync.toml'])

  def test_export_rejects_symlinks_and_unrelated_files_without_removing_them(self):
    folder = self.root / 'folder'
    folder.mkdir()
    link = self.root / 'link'
    link.symlink_to(folder, target_is_directory=True)
    with self.assertRaises(ValueError):
      greeter.export({'sync.toml': b''}, link)
    unrelated = folder / 'do-not-delete'
    unrelated.write_text('important')
    with self.assertRaises(ValueError):
      greeter.export({'sync.toml': b''}, folder)
    self.assertEqual(unrelated.read_text(), 'important')

  def test_unrelated_shell_changes_do_not_trigger_another_sync(self):
    first = greeter.payload(self.settings, self.waypaper)[0]
    self.update(barSize=80, doNotDisturb=True, shortcuts={'launcher': 'SUPER, A'})
    second = greeter.payload(self.settings, self.waypaper)[0]
    self.assertEqual(greeter.fingerprint(first), greeter.fingerprint(second))
    self.update(theme='gruvbox')
    self.assertNotEqual(greeter.fingerprint(first), greeter.fingerprint(greeter.payload(self.settings, self.waypaper)[0]))

  def test_layout_changes_reach_the_greeter_without_recopied_appearance_or_a_helper_call(self):
    runtime, state = self.root / 'runtime', self.root / 'state'
    runtime.mkdir()
    state.mkdir()
    preferences = self.root / 'layout.json'
    greeter.sync_layout('sidebar', preferences)
    files, information = greeter.payload(self.settings, self.waypaper)
    digest = greeter.fingerprint(files)
    (state / 'last-sync.json').write_text(json.dumps({**information, 'fingerprint': digest, 'status': 'synced'}))
    self.update(greeterLayout='centered')
    with patch.object(greeter, 'PREFERENCES', preferences), \
        patch.object(greeter, 'private_directory', side_effect=[runtime, state]), \
        patch.object(greeter.os, 'geteuid', return_value=1000), \
        patch.object(greeter.subprocess, 'run') as helper:
      report = greeter.sync(self.settings, self.waypaper)
    helper.assert_not_called()
    self.assertEqual(report['layout'], 'centered')
    self.assertEqual(report['fingerprint'], digest)
    self.assertEqual(greeter_model.read_layout(preferences), 'centered')
    self.assertEqual(json.loads((state / 'last-sync.json').read_text())['layout'], 'centered')
    self.assertEqual(preferences.stat().st_mode & 0o777, 0o640)

  def test_layout_preferences_are_validated_and_atomic_replacements_reload(self):
    preferences = self.root / 'layout.json'
    self.assertEqual(greeter_model.read_layout(preferences), 'sidebar')
    for value in ['centered', 'sidebar', 'centered']:
      self.assertTrue(greeter.sync_layout(value, preferences))
      look = greeter_model.load(self.root, preferences)
      self.assertEqual(look['appearance']['layout'], value)
      self.assertFalse(greeter.sync_layout(value, preferences))
    for value in ['invalid', [], {}, True, 42, None]:
      preferences.write_text(json.dumps({'layout': value}))
      self.assertEqual(greeter_model.read_layout(preferences), 'sidebar')
      with self.assertRaises(ValueError):
        greeter.sync_layout(value, preferences)
    preferences.write_text('broken json')
    self.assertEqual(greeter_model.read_layout(preferences), 'sidebar')

  def test_layout_reader_rejects_symlinks_and_oversized_files(self):
    preferences = self.root / 'layout.json'
    greeter.sync_layout('centered', preferences)
    linked = self.root / 'linked.json'
    linked.symlink_to(preferences)
    self.assertEqual(greeter_model.read_layout(linked), 'sidebar')
    with self.assertRaises(ValueError):
      greeter.sync_layout('sidebar', linked)
    preferences.write_text(' ' * 1025 + '{"layout":"centered"}')
    self.assertEqual(greeter_model.read_layout(preferences), 'sidebar')

  def test_toml_roundtrip_preserves_session_commands_and_quoted_keys(self):
    data = {'appearance': {'font_family': 'Fuente "ñ" \\ test'}, 'session': {
      'power': {'shutdown': 'sh -c "command --flag"'},
      'actions': [{'action': 'command', 'label': 'Custom', 'command': 'echo "$USER"'}]},
      'display name': {'scale': 1.25}, 'keyboard': {'numlock': True}}
    self.assertEqual(tomllib.loads(greeter.dump_toml(data)), data)

  def test_merge_removes_declarative_appearance_overrides_and_keeps_login_settings(self):
    original = {'appearance': {'palette': {'old': 'color'}, 'wallpaper': {'path': '/old.jpg'},
      'font_family': 'Old', 'theme_mode': 'light', 'corner_radius_scale': 2,
      'password_style': 'random'}, 'keyboard': {'layout': 'us'},
      'session': {'default': 'hyprland'}, 'auth': {'request_timeout': 60},
      'output': {'scale': 1.25}, 'clock': {'position': 'bottom-left'}}
    before = copy.deepcopy(original)
    merged = merge_greeter(original)
    self.assertEqual(original, before)
    self.assertNotIn('wallpaper', merged['appearance'])
    self.assertNotIn('palette', merged['appearance'])
    self.assertEqual(merged['appearance']['scheme'], 'Synced')
    self.assertEqual(merged['appearance']['password_style'], 'random')
    for key in ['keyboard', 'session', 'auth', 'output']:
      self.assertEqual(merged[key], original[key])
    self.assertEqual(merged['clock']['position'], 'bottom-left')
    self.assertEqual(tomllib.loads(greeter.dump_toml(merged)), merged)

  def test_model_tracks_every_shell_palette_including_light_custom(self):
    settings = {'radius': 8}
    for name, palette in self.palettes.items():
      look = greeter.appearance({**settings, 'theme': name, 'accent': palette['accent']}, self.palettes)
      displayed = greeter_model.appearance({'appearance': look})
      self.assertEqual(displayed['surface'], palette['surface'])
      self.assertEqual(displayed['accent'], look['palette']['primary'])
      self.assertEqual(displayed['text'], palette['text'])
    custom = {**self.palettes['amoled'], 'background': '#eeeeee', 'surface': '#eeeeee',
      'raised': '#e0e0e0', 'moduleSurface': '#e5e5e5', 'text': '#111111', 'accent': '#225599'}
    look = greeter.appearance({'theme': 'custom', 'customPalette': custom}, self.palettes)
    self.assertEqual(greeter_model.appearance({'appearance': look})['accent'], '#225599')

  def test_wallpaper_replacement_updates_url_even_with_same_name_and_content(self):
    image = self.root / 'wallpaper ñ %.jpg'
    image.write_bytes(b'fixture')
    data = {'appearance': {'wallpaper': {'path': str(image)}}}
    first = greeter_model.appearance(data)['wallpaper']
    replacement = self.root / 'replacement'
    replacement.write_bytes(b'fixture')
    replacement.replace(image)
    second = greeter_model.appearance(data)['wallpaper']
    self.assertNotEqual(first, second)
    self.assertIn(image.as_uri(), second)

  def test_session_desktop_entry_keeps_arguments_without_a_shell(self):
    entry = self.root / 'hyprland.desktop'
    entry.write_text('[Desktop Entry]\nType=Application\nName=Hyprland\n'
      'Exec=/usr/bin/start-hyprland "literal $(command)" %% %f\nDesktopNames=Hyprland;\n')
    session = greeter_model.session_entry(entry)
    self.assertEqual(session['command'], ['/usr/bin/start-hyprland', 'literal $(command)', '%'])
    self.assertIn('XDG_SESSION_TYPE=wayland', session['environment'])
    self.assertIn('XDG_CURRENT_DESKTOP=Hyprland', session['environment'])

  def test_hidden_or_unavailable_sessions_do_not_appear(self):
    entry = self.root / 'hidden.desktop'
    entry.write_text('[Desktop Entry]\nName=Hidden\nExec=/bin/true\nHidden=true\n')
    self.assertIsNone(greeter_model.session_entry(entry))
    entry.write_text('[Desktop Entry]\nName=Missing\nExec=missing\nTryExec=hyprlarp-missing-test\n')
    self.assertIsNone(greeter_model.session_entry(entry))

  def test_deployment_keeps_the_custom_frontend_and_optional_launcher(self):
    destination = self.root / 'package'
    destination.mkdir()
    manifest = copy_sources(destination)
    for name in ['greeter/shell.qml', 'greeter/Controller.qml', 'greeter/model.py', 'bin/hyprlarp-greeter']:
      self.assertIn(name, manifest)
      self.assertTrue((destination / name).is_file())


if __name__ == '__main__':
  unittest.main()
