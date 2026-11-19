import copy
import json
import os
from pathlib import Path
import resource
import re
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from backend import lockscreen
from backend.service import DEFAULTS, PALETTES, Service, render_lock_config


class LockScreenTests(unittest.TestCase):
  def test_layout_font_palette_and_independent_radii_follow_settings(self):
    settings = copy.deepcopy(DEFAULTS)
    settings.update(greeterLayout='centered', theme='gruvbox', accent='#abcdef', font='Monospace',
      radius=4, cornerRadii={'panel': 8, 'field': 2})
    result = render_lock_config(settings)
    self.assertIn('$surface = rgb(' + PALETTES['gruvbox']['surface'][1:] + ')', result)
    self.assertIn('$accent = rgb(abcdef)', result)
    self.assertIn('$font = Monospace', result)
    self.assertIn('rounding = 8', result)
    self.assertIn('rounding = 2', result)
    self.assertIn('text = HYPRLARP', result)
    self.assertNotIn('@WALLPAPER@', result)
    self.assertNotIn('cmd[', result)

  def test_sidebar_and_centered_layouts_differ_and_cover_each_output(self):
    outputs = [{'name': 'eDP-1', 'width': 1920, 'height': 1080, 'scale': 1.25},
      {'name': 'DP-1', 'width': 2560, 'height': 1440, 'scale': 1}]
    sidebar = render_lock_config(DEFAULTS, outputs=outputs)
    centered = render_lock_config({**DEFAULTS, 'greeterLayout': 'centered'}, outputs=outputs)
    self.assertNotEqual(sidebar, centered)
    self.assertEqual(sidebar.count('input-field {'), 2)
    self.assertIn('monitor = eDP-1', sidebar)
    self.assertIn('monitor = DP-1', sidebar)
    self.assertIn('size = 28.645833%, 100.000000%', sidebar)

  def test_fractional_and_integer_scales_keep_the_card_and_field_centered(self):
    for scale in [1, 1.25, 1.5, 2]:
      with self.subTest(scale=scale):
        result = render_lock_config({**DEFAULTS, 'greeterLayout': 'centered'},
          outputs=[{'name': 'eDP-1', 'width': 1920, 'height': 1080, 'scale': scale}])
        blocks = re.findall(r'(shape|input-field) \{\n(.*?)\n\}', result, re.S)
        card = next(text for kind, text in blocks if kind == 'shape' and 'color = $surface' in text)
        field = next(text for kind, text in blocks if kind == 'input-field')
        self.assertIn('position = 0, 0', card)
        self.assertIn('halign = center', card)
        self.assertIn('valign = center', card)
        size = re.search(r'size = ([\d.]+)%, ([\d.]+)%', card)
        field_size = re.search(r'size = ([\d.]+)%, ([\d.]+)%', field)
        position = re.search(r'position = ([\d.]+)%, -([\d.]+)%', field)
        card_width = float(size[1]) / 100 * 1920
        input_width = float(field_size[1]) / 100 * 1920
        input_x = float(position[1]) / 100 * 1920
        self.assertAlmostEqual(input_x + input_width / 2, 960, delta=1)
        self.assertLess(input_width, card_width)
        self.assertAlmostEqual(card_width, min(448, 1920 / scale - 72) * scale, delta=2)

  def test_font_and_asset_paths_cannot_add_configuration_or_commands(self):
    for font in ['Bad\nsource = /tmp/other.conf', '$other', 'Bad#comment', 'Bad{font}']:
      result = render_lock_config({**DEFAULTS, 'font': font})
      self.assertIn('$font = Inter', result)
      self.assertNotIn(font, result)
    with self.assertRaises(ValueError):
      render_lock_config(DEFAULTS, asset_path='/tmp/image\nsource = another.conf')
    result = render_lock_config(DEFAULTS, asset_path='/proc/self/fd/7', assets={'wallpaper': '../../other'})
    self.assertNotIn('../../other', result)

  def test_missing_wallpaper_or_converter_still_produces_a_lock_screen(self):
    with tempfile.TemporaryDirectory() as temporary, patch.object(lockscreen.shutil, 'which', return_value=None):
      folder, assets = lockscreen.prepare({**DEFAULTS, 'wallpaper': '/missing/image.jpg'}, Path(temporary))
      self.assertEqual(assets['wallpaper'], '')
      self.assertEqual(assets['logo'], '')
      self.assertEqual(folder.stat().st_mode & 0o777, 0o700)
      result = render_lock_config(DEFAULTS, assets=assets)
      self.assertIn('input-field {', result)
      self.assertIn('color = $background', result)

  @unittest.skipUnless(shutil.which('magick'), 'ImageMagick required for vector artwork')
  def test_artwork_is_tinted_cached_and_does_not_rewrite_source_images(self):
    with tempfile.TemporaryDirectory() as temporary:
      settings = {**DEFAULTS, 'accent': '#abcdef'}
      folder, assets = lockscreen.prepare(settings, Path(temporary))
      self.assertEqual(assets['logo'], 'logo.png')
      self.assertTrue((folder / 'logo.png').read_bytes().startswith(b'\x89PNG'))
      with patch.object(lockscreen, 'bounded_process', side_effect=AssertionError('cached artwork decoded again')):
        _, second = lockscreen.prepare(settings, Path(temporary))
      self.assertEqual(second, assets)

  def test_wallpaper_with_special_characters_is_copied_and_reused(self):
    with tempfile.TemporaryDirectory(prefix='hyprlarp # $ ñ ') as temporary, patch.object(lockscreen.shutil, 'which', return_value=None):
      directory = Path(temporary)
      source = directory / 'fondo # $ ñ.jpg'
      source.write_bytes(b'fixture image')
      settings = {**DEFAULTS, 'wallpaper': str(source)}
      folder, assets = lockscreen.prepare(settings, directory)
      self.assertEqual((folder / assets['wallpaper']).read_bytes(), source.read_bytes())
      stamp = (folder / assets['wallpaper']).stat().st_mtime_ns
      lockscreen.prepare(settings, directory)
      self.assertEqual((folder / assets['wallpaper']).stat().st_mtime_ns, stamp)
      _, plain = lockscreen.prepare({**settings, 'wallpaper': ''}, directory)
      self.assertEqual(plain['wallpaper'], '')

  def test_lock_launch_preserves_native_authentication_and_resource_descriptor(self):
    with tempfile.TemporaryDirectory() as temporary, patch('backend.service.subprocess.Popen') as launch, \
        patch.object(lockscreen, 'monitors', return_value=[]):
      directory = Path(temporary)
      with patch.object(lockscreen.shutil, 'which', side_effect=lambda name: '/usr/bin/hyprlock' if name == 'hyprlock' else None):
        Service.session('lock', directory)
      args = launch.call_args.args[0]
      self.assertEqual(args[:3], ['hyprlock', '--grace', '0'])
      self.assertTrue(launch.call_args.kwargs['pass_fds'])
      self.assertTrue(launch.call_args.kwargs['start_new_session'])
      self.assertIn('input-field {', (directory / 'generated-lock.conf').read_text())

  @unittest.skipUnless(shutil.which('hyprlock'), 'native parser unavailable')
  def test_native_hyprlock_accepts_both_layouts_without_connecting_to_desktop(self):
    # hyprlock parses its entire configuration before opening a Wayland display.
    def disable_core():
      resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    with tempfile.TemporaryDirectory() as temporary:
      config = Path(temporary) / 'lock.conf'
      for layout in ['sidebar', 'centered']:
        for theme in PALETTES:
          config.write_text(render_lock_config({**DEFAULTS, 'greeterLayout': layout, 'theme': theme}))
          result = subprocess.run(['hyprlock', '--config', str(config), '--display', 'hyprlarp-test-no-display'],
            env={**os.environ, 'WAYLAND_DISPLAY': 'hyprlarp-test-no-display'}, capture_output=True, text=True,
            preexec_fn=disable_core, timeout=5)
          output = result.stdout + result.stderr
          self.assertIn("Couldn't connect to a wayland compositor", output, output)
          self.assertNotIn('Config threw', output)
