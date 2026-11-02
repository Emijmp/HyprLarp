#!/usr/bin/env python3
"""Install for the current user using staging, backups and a removal manifest."""

import argparse
import json
from pathlib import Path
import shlex
import shutil
import sys
import tempfile

from deployment import ROOT, Locations, commit, copy_sources, desktop_word, deployment_lock
sys.path.insert(0, str(ROOT))
from backend.service import Store, generate_bindings, lua_string, read_regular


def _install(locations, dry_run=False):
  locations.validate(installing=True)
  for location in [locations.app, *locations.managed().values(), locations.config / 'settings.json']:
    print(location)
  if dry_run:
    return
  locations.app.parent.mkdir(parents=True, exist_ok=True)
  stage = Path(tempfile.mkdtemp(prefix='.hyprlarp-stage-', dir=locations.app.parent))
  try:
    files = copy_sources(stage)
    with tempfile.TemporaryDirectory(prefix='hyprlarp-settings-') as temporary:
      folder = Path(temporary)
      current = locations.config / 'settings.json'
      if current.exists():
        (folder / 'settings.json').write_bytes(read_regular(current))
      settings = Store(folder).settings
    executable, config = locations.executable, locations.config
    contents = {
      'launcher': '#!/bin/sh\nexec ' + shlex.quote(str(locations.app / 'bin/hyprlarp')) + ' "$@"\n',
      'settings': json.dumps(settings, ensure_ascii=False, indent=2) + '\n',
      'bindings': generate_bindings(settings, executable),
      'prelude': '-- Load before your existing binds in hyprland.lua.\n'
        + 'local manager = dofile(' + lua_string(str(locations.app / 'config/bindings-runtime.lua')) + ')\n'
        + 'manager.begin(' + lua_string(str(locations.app / 'config/bindings-runtime.lua')) + ')\n',
      'session': '-- Load from hyprland.lua using dofile().\n'
        + 'dofile(' + lua_string(str(config / 'bindings.lua')) + ')\n'
        + 'hl.on("hyprland.start", function()\n'
        + '  hl.exec_cmd(' + lua_string(shlex.quote(str(executable)) + ' run') + ')\n'
        + '  hl.exec_cmd(' + lua_string('hypridle -c ' + shlex.quote(str(config / 'hypridle.conf'))) + ')\n'
        + 'end)\n',
      'idle': 'general {\n  lock_cmd = ' + shlex.quote(str(executable)) + ' lock\n'
        + '  before_sleep_cmd = loginctl lock-session\n'
        + '  after_sleep_cmd = hyprctl dispatch \'hl.dsp.dpms({action = "on"})\'\n'
        + '  inhibit_sleep = 3\n}\n',
      'desktop': '[Desktop Entry]\nType=Application\nName=HyprLarp Settings\n'
        + 'Name[es]=Configuración de HyprLarp\nComment=Personaliza tu escritorio\n'
        + 'Exec=env ' + desktop_word(str(executable)) + ' settings\nIcon=hyprlarp\nTerminal=false\nCategories=Settings;DesktopSettings;\n',
      'icon': (ROOT / 'assets/hyprlarp.svg').read_text(),
    }
    contents = {role: text.encode('utf-8') for role, text in contents.items()}
    import hashlib
    manifest = {'type': 'hyprlarp-install', 'version': 1, 'prefix': locations.prefix, 'files': files,
      'managed': {role: hashlib.sha256(data).hexdigest() for role, data in contents.items() if role != 'settings'}}
    locations.config.mkdir(parents=True, exist_ok=True, mode=0o700)
    locations.config.chmod(0o700)
    backups = commit(locations, stage, contents, json.dumps(manifest, indent=2).encode('utf-8') + b'\n')
    for backup in backups:
      print('Respaldo guardado: ' + str(backup))
    print('\nInstalado. Ejecuta: ' + shlex.quote(str(executable)) + ' run')
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
  parser.add_argument('--prefix', type=Path, help='Instalación aislada; usa el mismo prefijo al desinstalar')
  parser.add_argument('--dry-run', action='store_true', help='Mostrar el plan sin escribir archivos')
  args = parser.parse_args()
  try:
    install(Locations.create(args.prefix), args.dry_run)
  except (OSError, ValueError, RuntimeError) as error:
    parser.exit(1, str(error) + '\n')


if __name__ == '__main__':
  main()
