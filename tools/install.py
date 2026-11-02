#!/usr/bin/env python3
"""Install a copy into XDG directories; never rewrite the user's Hyprland config."""

import argparse
from datetime import datetime
from pathlib import Path
import os
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.service import Store, generate_bindings, lua_string


def main() -> None:
  parser = argparse.ArgumentParser()
  parser.add_argument("--dry-run", action="store_true")
  parser.add_argument("--prefix", type=Path, help="Directorio aislado para una instalación de prueba")
  args = parser.parse_args()
  home = Path.home()
  data = Path(os.environ.get("XDG_DATA_HOME", str(home / ".local/share")))
  config = Path(os.environ.get("XDG_CONFIG_HOME", str(home / ".config"))) / "hyprlarp"
  destination = data / "hyprlarp"
  executable = home / ".local/bin/hyprlarp"
  if args.prefix:
    data = args.prefix.resolve() / "share"
    config = args.prefix.resolve() / "config/hyprlarp"
    destination = data / "hyprlarp"
    executable = args.prefix.resolve() / "bin/hyprlarp"
  locations = [destination, executable, config / "hyprlarp.lua", config / "bindings.lua",
        config / "hypridle.conf", data / "applications/hyprlarp-settings.desktop",
        data / "icons/hicolor/scalable/apps/hyprlarp.svg"]
  for location in locations:
    print(location)
  if args.dry_run:
    return
  if destination.resolve() == ROOT:
    raise SystemExit("Ejecuta el instalador desde el repositorio, no desde la copia instalada")
  if destination.resolve().is_relative_to(ROOT):
    raise SystemExit("El destino de instalación debe estar fuera del repositorio")
  stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
  # Refuse symlink destinations instead of writing through them.
  for location in locations:
    if location.is_symlink():
      raise SystemExit(f"Destino con enlace simbólico: {location}. Conserva o mueve el enlace antes de instalar.")
  if destination.exists():
    destination.rename(destination.with_name(f"hyprlarp.backup-{stamp}"))
  shutil.copytree(ROOT, destination, ignore=shutil.ignore_patterns(".git", ".runtime", ".preview", "__pycache__", "*.pyc"))
  executable.parent.mkdir(parents=True, exist_ok=True)
  if executable.exists():
    executable.rename(executable.with_name(f"hyprlarp.backup-{stamp}"))
  # A wrapper preserves the installed project's root resolution.
  import shlex
  executable.write_text("#!/bin/sh\nexec " + shlex.quote(str(destination / "bin/hyprlarp")) + ' "$@"\n')
  executable.chmod(0o755)
  config.mkdir(parents=True, exist_ok=True, mode=0o700)
  store = Store(config)
  if store.warning and store.file.exists():
    shutil.copy2(store.file, store.file.with_name(f"settings.json.backup-{stamp}"))
  settings = store.update({})
  files = {
    config / "bindings.lua": generate_bindings(settings, executable),
    config / "hyprlarp.lua": "-- Load from hyprland.lua using dofile().\n"
      + "dofile(" + lua_string(str(config / "bindings.lua")) + ")\n"
      + 'hl.on("hyprland.start", function()\n'
      + "  hl.exec_cmd(" + lua_string(shlex.quote(str(executable)) + " run") + ")\n"
      + "  hl.exec_cmd(" + lua_string("hypridle -c " + shlex.quote(str(config / "hypridle.conf"))) + ")\n"
      + "end)\n",
    config / "hypridle.conf": "general {\n  lock_cmd = " + shlex.quote(str(executable)) + " lock\n"
      + "  before_sleep_cmd = loginctl lock-session\n"
      + "  after_sleep_cmd = hyprctl dispatch 'hl.dsp.dpms({action = \"on\"})'\n"
      + "  inhibit_sleep = 3\n}\n",
    data / "applications/hyprlarp-settings.desktop": "[Desktop Entry]\nType=Application\nName=HyprLarp Settings\n"
      + "Name[es]=Configuración de HyprLarp\nComment=Personaliza tu escritorio\n"
      + 'Exec="' + str(executable).replace('"', '\\"') + '" settings\nIcon=hyprlarp\nTerminal=false\nCategories=Settings;DesktopSettings;\n',
  }
  for filename, contents in files.items():
    filename.parent.mkdir(parents=True, exist_ok=True)
    if filename.exists():
      shutil.copy2(filename, filename.with_name(filename.name + f".backup-{stamp}"))
    filename.write_text(contents)
  icon = data / "icons/hicolor/scalable/apps/hyprlarp.svg"
  icon.parent.mkdir(parents=True, exist_ok=True)
  shutil.copy2(ROOT / "assets/hyprlarp.svg", icon)
  print("\nInstalado. Para iniciarlo: ~/.local/bin/hyprlarp run")
  print("Para arrancar con Hyprland, añade en hyprland.lua: dofile(" + lua_string(str(config / "hyprlarp.lua")) + ")")


if __name__ == "__main__":
  main()
