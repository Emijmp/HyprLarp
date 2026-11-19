#!/usr/bin/env python3
"""Remove only manifest-owned files; preserve configuration by default."""

import argparse
import os
from pathlib import Path
import shutil
import signal
import subprocess

from deployment import ROOT, Locations, MARKER, digest, load_manifest, no_symlinks, read_json, deployment_lock
from backend.safety import idle_processes
from backend.service import lua_string
from backend import recovery


def stop_runtime(locations):
  binary = shutil.which('quickshell') or shutil.which('qs')
  if not locations.prefix and binary:
    recovery.stop(locations.app, binary, destination=locations.managed()['service'])
  hyprctl = shutil.which('hyprctl')
  if hyprctl:
    owned = lua_string(str(locations.app / 'config/bindings-runtime.lua'))
    expression = 'if HyprLarpBinds and HyprLarpBinds.runtimePath == ' + owned + ' then HyprLarpBinds.stop() end'
    try:
      subprocess.run([hyprctl, 'eval', expression], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)
    except (OSError, subprocess.TimeoutExpired):
      pass
  binary = shutil.which('quickshell') or shutil.which('qs')
  if binary:
    for entry in ('shell.qml', 'settings.qml', 'preview.qml'):
      subprocess.run([binary, 'kill', '--path', str(locations.app / entry), '--any-display'],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
  # Stop only our idle process, identified by its exact configuration argument.
  expected = str(locations.config / 'hypridle.conf')
  for pid, args in idle_processes(expected):
    try:
      descriptor = os.pidfd_open(pid)
      try:
        if (Path('/proc') / str(pid) / 'cmdline').read_bytes().split(b'\0') == args:
          signal.pidfd_send_signal(descriptor, signal.SIGTERM)
      finally:
        os.close(descriptor)
    except (OSError, ValueError):
      continue


def _uninstall(locations, *, dry_run=False, purge=False, stop=True):
  locations.validate()
  if not locations.app.exists():
    if purge:
      raise ValueError('Sin manifiesto de instalación no se borran ajustes; se han conservado.')
    print('HyprLarp no está instalado en este destino. Los ajustes se conservan.')
    return
  manifest = load_manifest(locations)
  files = [(locations.app / name, checksum) for name, checksum in manifest['files'].items()]
  files += [(locations.managed()[role], checksum) for role, checksum in manifest['managed'].items()]
  removable, preserved = [], []
  for path, checksum in files:
    no_symlinks(path)
    if path.is_file():
      (removable if digest(path) == checksum else preserved).append(path)
  for path in removable:
    print('Quitar: ' + str(path))
  for path in preserved:
    print('Conservar modificado: ' + str(path))
  print(('Quitar carpeta de ajustes completa, incluidos respaldos internos: ' if purge else 'Conservar ajustes: ') + str(locations.config))
  if dry_run:
    return
  if stop:
    stop_runtime(locations)
  for path in removable:
    path.unlink()
  if stop and not locations.prefix:
    recovery.run(['systemctl', '--user', 'daemon-reload'], check=False)
  for name in manifest['files']:
    source = locations.app / name
    if source.suffix == '.py':
      cache = source.parent / '__pycache__'
      if cache.is_symlink():
        continue
      no_symlinks(cache)
      for compiled in cache.glob(source.stem + '.cpython-*.pyc'):
        if not compiled.is_symlink():
          compiled.unlink()
  for path in sorted(locations.app.rglob('*'), key=lambda item: len(item.parts), reverse=True):
    if path.is_dir() and not path.is_symlink():
      try:
        path.rmdir()
      except OSError:
        pass
  remaining = [path for path in locations.app.iterdir() if path.name != MARKER]
  if remaining:
    print('Se han conservado archivos modificados o ajenos en ' + str(locations.app))
  else:
    (locations.app / MARKER).unlink()
    locations.app.rmdir()
  if purge and locations.config.exists():
    shutil.rmtree(locations.config)
  print('Desinstalación terminada. ' + ('Los respaldos fuera de la carpeta de ajustes se conservan.' if purge else 'Los respaldos se conservan.'))
  print('Retira el dofile de HyprLarp de tu hyprland.lua si lo añadiste.')


def uninstall(locations, *, dry_run=False, purge=False, stop=True):
  locations.validate()
  if dry_run or not locations.app.exists():
    return _uninstall(locations, dry_run=dry_run, purge=purge, stop=stop)
  with deployment_lock(locations):
    return _uninstall(locations, purge=purge, stop=stop)


def main():
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument('--prefix', type=Path)
  parser.add_argument('--dry-run', action='store_true')
  parser.add_argument('--purge', action='store_true', help='Eliminar toda la carpeta de ajustes e historiales, incluidos sus respaldos internos')
  args = parser.parse_args()
  try:
    if args.prefix is None and (ROOT / MARKER).is_file() and read_json(ROOT / MARKER).get('prefix'):
      raise ValueError('Esta instalación usa --prefix; especifica el mismo prefijo al desinstalar.')
    uninstall(Locations.create(args.prefix), dry_run=args.dry_run, purge=args.purge)
  except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
    parser.exit(1, str(error) + '\n')


if __name__ == '__main__':
  main()
