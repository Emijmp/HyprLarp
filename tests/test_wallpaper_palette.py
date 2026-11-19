from concurrent.futures import ThreadPoolExecutor
import json
import os
import struct
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
import zlib

from backend.wallpaper_palette import CACHE_LIMIT, PaletteExtractor, extract
from backend.service import Service, Store


class WallpaperPaletteTests(unittest.TestCase):
  def test_svg_palette_is_local_deduplicated_and_limited(self):
    with tempfile.TemporaryDirectory() as folder:
      image = Path(folder) / 'gradient.svg'
      image.write_text('<svg><stop stop-color="#123"/><path fill="#123456"/><path fill="#abcdef"/></svg>')
      result = extract(str(image))
      self.assertEqual(result['name'], 'gradient.svg')
      self.assertEqual(result['colors'], ['#112233', '#123456', '#abcdef'])

  def test_raster_palette_uses_sampled_dominant_colors(self):
    try:
      from PIL import Image, ImageDraw
    except ImportError:
      self.skipTest('Pillow is not installed')
    with tempfile.TemporaryDirectory() as folder:
      image = Image.new('RGB', (80, 40), '#bb2222')
      ImageDraw.Draw(image).rectangle((56, 0, 79, 39), fill='#2255bb')
      path = Path(folder) / 'wallpaper.png'
      image.save(path)
      result = extract(str(path))
      self.assertEqual(result['colors'][:2], ['#bb2222', '#2255bb'])

  def test_missing_unsupported_and_oversized_svg_are_rejected(self):
    with self.assertRaises(ValueError):
      extract('')
    with tempfile.TemporaryDirectory() as folder:
      invalid = Path(folder) / 'file.gif'
      invalid.write_bytes(b'GIF89a')
      with self.assertRaises(ValueError):
        extract(str(invalid))
      large = Path(folder) / 'large.svg'
      large.write_text('<svg>' + ' ' * (1024 * 1024) + '</svg>')
      with self.assertRaises(ValueError):
        extract(str(large))

  def test_service_exposes_extracted_colors_without_changing_settings(self):
    with tempfile.TemporaryDirectory() as folder:
      path = Path(folder) / 'wallpaper.svg'
      path.write_text('<svg><rect fill="#445566"/><circle fill="#d1a244"/></svg>')
      store = Store(Path(folder) / 'settings')
      store.update({'wallpaper': str(path)})
      before = store.settings.copy()
      service = Service(store, preview=True)
      events = []
      service.emit = lambda kind, data: events.append((kind, data))
      service.action({'action': 'wallpaper-palette-extract', 'data': {}})
      result = next(data for kind, data in events if kind == 'wallpaper-palette')
      self.assertEqual(result['colors'], ['#445566', '#d1a244'])
      self.assertEqual(store.settings, before)

  def test_cache_reuses_unchanged_files_and_invalidates_in_place_edits(self):
    with tempfile.TemporaryDirectory() as folder:
      path = Path(folder) / 'wallpaper.svg'
      path.write_text('<svg fill="#112233"/>')
      calls = []
      def runner(argv, **options):
        calls.append(argv)
        return json.dumps({'colors': ['#112233' if len(calls) == 1 else '#445566']}).encode()
      extractor = PaletteExtractor(runner=runner)
      result = extractor.extract(str(path))
      result['colors'].clear()
      self.assertEqual(extractor.extract(str(path))['colors'], ['#112233'])
      self.assertEqual(len(calls), 1)
      before = path.stat()
      path.write_text('<svg fill="#445566"/>')
      os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns + 1_000_000))
      self.assertEqual(extractor.extract(str(path))['colors'], ['#445566'])
      self.assertEqual(len(calls), 2)
      self.assertEqual(len(extractor.cache), 1)

  def test_cache_evicts_least_recently_used_file(self):
    with tempfile.TemporaryDirectory() as folder:
      calls = []
      def runner(argv, **options):
        calls.append(argv)
        return b'{"colors": ["#112233"]}'
      extractor = PaletteExtractor(runner=runner)
      paths = [Path(folder) / f'{index}.svg' for index in range(CACHE_LIMIT + 1)]
      for path in paths:
        path.write_text('<svg fill="#112233"/>')
      for path in paths[:CACHE_LIMIT]:
        extractor.extract(str(path))
      extractor.extract(str(paths[0]))
      extractor.extract(str(paths[-1]))
      self.assertEqual(len(extractor.cache), CACHE_LIMIT)
      self.assertEqual(len(calls), CACHE_LIMIT + 1)
      extractor.extract(str(paths[0]))
      self.assertEqual(len(calls), CACHE_LIMIT + 1)
      extractor.extract(str(paths[1]))
      self.assertEqual(len(calls), CACHE_LIMIT + 2)

  def test_single_active_extraction_failure_and_close_do_not_leave_busy_state(self):
    with tempfile.TemporaryDirectory() as folder:
      path = Path(folder) / 'wallpaper.svg'
      path.write_text('<svg fill="#112233"/>')
      started, release = threading.Event(), threading.Event()
      def slow_runner(argv, **options):
        started.set()
        self.assertTrue(release.wait(3))
        return b'{"colors": ["#112233"]}'
      extractor = PaletteExtractor(runner=slow_runner)
      with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(extractor.extract, str(path))
        self.assertTrue(started.wait(3))
        try:
          with self.assertRaisesRegex(RuntimeError, 'Ya se están extrayendo'):
            extractor.extract(str(path))
          extractor.close()
        finally:
          release.set()
        with self.assertRaisesRegex(RuntimeError, 'cerrando'):
          future.result(timeout=3)
      self.assertFalse(extractor.cache)
      retry = PaletteExtractor(runner=lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError('timeout')))
      with self.assertRaisesRegex(RuntimeError, 'tiempo o recursos'):
        retry.extract(str(path))
      retry.runner = lambda *args, **kwargs: b'{"colors": ["#112233"]}'
      self.assertEqual(retry.extract(str(path))['colors'], ['#112233'])

  def test_changed_source_and_invalid_worker_output_are_never_cached(self):
    with tempfile.TemporaryDirectory() as folder:
      path = Path(folder) / 'wallpaper.svg'
      path.write_text('<svg fill="#112233"/>')
      def changing_runner(argv, **options):
        path.write_text('<svg fill="#445566" width="20"/>')
        return b'{"colors": ["#112233"]}'
      extractor = PaletteExtractor(runner=changing_runner)
      with self.assertRaisesRegex(ValueError, 'cambió'):
        extractor.extract(str(path))
      self.assertFalse(extractor.cache)
      for output in [b'not json', b'{"colors": ["red"]}', b'{"colors": []}']:
        extractor.runner = lambda *args, output=output, **kwargs: output
        with self.assertRaisesRegex(RuntimeError, 'paleta válida'):
          extractor.extract(str(path))
        self.assertFalse(extractor.cache)

  def test_worker_rejects_overlarge_dimensions_before_decoding(self):
    with tempfile.TemporaryDirectory() as folder:
      path = Path(folder) / 'too-large.png'
      def chunk(kind, data):
        return struct.pack('!I', len(data)) + kind + data + struct.pack('!I', zlib.crc32(kind + data))
      path.write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('!IIBBBBB', 6000, 6000, 8, 2, 0, 0, 0))
        + chunk(b'IDAT', zlib.compress(b'\0\0\0\0')) + chunk(b'IEND', b''))
      with self.assertRaisesRegex(ValueError, '24 megapíxeles'):
        PaletteExtractor().extract(str(path))

  def test_real_raster_worker_never_loads_pillow_in_the_parent(self):
    try:
      from PIL import Image
    except ImportError:
      self.skipTest('Pillow is not installed')
    with tempfile.TemporaryDirectory() as folder:
      path = Path(folder) / 'small.png'
      with Image.new('RGB', (4, 4), '#abcdef') as image:
        image.save(path)
      code = "import sys; sys.path.insert(0, sys.argv[1]); from backend.wallpaper_palette import extract; assert extract(sys.argv[2])['colors'] == ['#abcdef']; assert not any(name == 'PIL' or name.startswith('PIL.') for name in sys.modules); print('isolated')"
      result = subprocess.run([sys.executable, '-I', '-c', code, str(Path(__file__).resolve().parents[1]), str(path)], capture_output=True, text=True, timeout=10)
      self.assertEqual(result.returncode, 0, result.stderr)
      self.assertEqual(result.stdout.strip(), 'isolated')


if __name__ == '__main__':
  unittest.main()
