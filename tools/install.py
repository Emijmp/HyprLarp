#!/usr/bin/env python3
"""Install for the current user using staging, backups and a removal manifest."""

import argparse
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile

from deployment import ROOT, Locations, MARKER, commit, copy_sources, desktop_word, deployment_lock, digest, load_manifest, no_symlinks
from backend.version import VERSION, read_version
sys.path.insert(0, str(ROOT))
from backend.service import Store, generate_bindings, lua_string, read_regular
from backend.gaps import render as render_window_gaps
from backend import recovery
try:
  from .integration import contents as integration_contents
except ImportError:
  from integration import contents as integration_contents

ACTIVE_FILES = {'settings', 'bindings', 'gaps', 'idle'}


def preserve_application(locations, stage, files, previous):
  """Keep local application edits and foreign files across a code replacement."""
  if previous is None:
    return
  for source in sorted(locations.app.rglob('*')):
    relative = source.relative_to(locations.app)
    if relative.as_posix() == MARKER:
      continue
    no_symlinks(source)
    destination = stage / relative
    if source.is_dir():
      if destination.exists() and not destination.is_dir():
        raise ValueError('Un directorio local coincide con un archivo del paquete: ' + str(source))
      destination.mkdir(parents=True, exist_ok=True)
      continue
    if not source.is_file():
      raise ValueError('Archivo local no regular en la instalación: ' + str(source))
    name = relative.as_posix()
    owned = previous['files'].get(name)
    if owned is None or digest(source) != owned:
      if destination.exists() and not destination.is_file():
        raise ValueError('Un archivo local coincide con un directorio del paquete: ' + str(source))
      destination.parent.mkdir(parents=True, exist_ok=True)
      shutil.copy2(source, destination)
      if owned is None:
        files.pop(name, None)
      else:
        # Keep the old ownership hash, so uninstall preserves the local edit.
        files[name] = owned
      print('Conservar archivo local: ' + str(source))


def plan_managed(locations, contents, previous):
  """An update changes code; applying saved preferences is a separate action."""
  import hashlib
  planned, owned = {}, {}
  targets = {**locations.managed(), 'settings': locations.config / 'settings.json'}
  for role, data in contents.items():
    target = targets[role]
    previous_hash = (previous or {}).get('managed', {}).get(role)
    if target.exists():
      if not target.is_file():
        raise ValueError('El destino debe ser un archivo regular: ' + str(target))
      current_hash = digest(target)
      if role in ACTIVE_FILES or previous_hash is None or current_hash != previous_hash:
        if previous_hash is not None and role != 'settings':
          owned[role] = previous_hash
        print('Conservar configuración activa: ' + str(target))
        continue
      if target.read_bytes() == data:
        owned[role] = previous_hash
        continue
    planned[role] = data
    if role != 'settings':
      owned[role] = hashlib.sha256(data).hexdigest()
  return planned, owned


def _install(locations, dry_run=False):
  locations.validate(installing=True)
  for location in [locations.app, *locations.managed().values(), locations.config / 'settings.json']:
    print(location)
  if dry_run:
    return
  previous = None
  if locations.app.exists():
    if not (locations.app / MARKER).is_file():
      raise ValueError('El destino ya existe sin un manifiesto de HyprLarp; se ha conservado.')
    previous = load_manifest(locations)
  first_run = bool(previous.get('first_run', False)) if previous else not (locations.config / 'settings.json').exists()
  locations.app.parent.mkdir(parents=True, exist_ok=True)
  stage = Path(tempfile.mkdtemp(prefix='.hyprlarp-stage-', dir=locations.app.parent))
  try:
    files = copy_sources(stage)
    preserve_application(locations, stage, files, previous)
    with tempfile.TemporaryDirectory(prefix='hyprlarp-settings-') as temporary:
      folder = Path(temporary)
      current = locations.config / 'settings.json'
      if current.exists():
        (folder / 'settings.json').write_bytes(read_regular(current))
      settings = Store(folder).settings
    executable, config = locations.executable, locations.config
    contents = integration_contents(locations.app, config, executable, settings,
      icon=(ROOT / 'assets/hyprlarp-desktop.svg').read_text())
    contents, managed = plan_managed(locations, contents, previous)
    manifest = {'type': 'hyprlarp-install', 'version': 1, 'release': read_version(stage), 'first_run': first_run,
      'prefix': locations.prefix, 'files': files,
      'managed': managed}
    locations.config.mkdir(parents=True, exist_ok=True, mode=0o700)
    locations.config.chmod(0o700)
    # A live update is accepted only after the installed shell actually responds.
    # Isolated prefixes never address the user's running desktop or systemd bus.
    binary = shutil.which('quickshell') or shutil.which('qs')
    was_running = not locations.prefix and binary and (
      recovery.service_running(locations.app, locations.managed()['service'])
      or bool(recovery.running_pids(locations.app))
      or bool(recovery.running_pids(locations.app, 'recovery.qml')))
    if was_running:
      environment = recovery.current_session()
      os.environ['HYPRLAND_INSTANCE_SIGNATURE'] = environment['HYPRLAND_INSTANCE_SIGNATURE']
      recovery.stop(locations.app, binary, destination=locations.managed()['service'])

    def activate():
      try:
        recovery.start(locations.app, executable, binary, destination=locations.managed()['service'])
      except BaseException:
        recovery.stop(locations.app, binary, destination=locations.managed()['service'])
        raise

    try:
      backups = commit(locations, stage, contents, json.dumps(manifest, indent=2).encode('utf-8') + b'\n',
        activate=activate if was_running else None)
    except BaseException:
      if was_running:
        # commit has already restored every previous file before this recovery.
        recovery.run(['systemctl', '--user', 'daemon-reload'], check=False)
        if locations.managed()['service'].is_file():
          recovery.start(locations.app, executable, binary, destination=locations.managed()['service'])
        else:
          subprocess.Popen([str(executable), 'run'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True)
          recovery.wait_ready(locations.app, binary)
      raise
    for backup in backups:
      print('Respaldo guardado: ' + str(backup))
    print('\nInstalado. Ejecuta: ' + shlex.quote(str(executable)) + ' start')
    print('Antes de tus binds: dofile(' + lua_string(str(config / 'bindings-prelude.lua')) + ')')
    print('Al final de hyprland.lua: dofile(' + lua_string(str(config / 'hyprlarp.lua')) + ')')
    print('La configuración principal de Hyprland no se ha modificado.')
  finally:
    if stage.exists():
      shutil.rmtree(stage)


def install(locations, dry_run=False):
  locations.validate(installing=True)
  if dry_run:
    return _install(locations, dry_run=True)
  with deployment_lock(locations):
    return _install(locations)


def main():
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument('--version', action='version', version='HyprLarp ' + VERSION)
  parser.add_argument('--prefix', type=Path, help='Instalación aislada; usa el mismo prefijo al desinstalar')
  parser.add_argument('--dry-run', action='store_true', help='Mostrar el plan sin escribir archivos')
  args = parser.parse_args()
  try:
    install(Locations.create(args.prefix), args.dry_run)
  except (OSError, ValueError, RuntimeError) as error:
    parser.exit(1, str(error) + '\n')


if __name__ == '__main__':
  main()
