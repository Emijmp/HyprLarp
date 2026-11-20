"""Pure renderers shared by a user installation and system-package setup."""

import json
from pathlib import Path
import shlex

from backend.service import generate_bindings, lua_string
from backend.gaps import render as render_window_gaps
from backend import recovery
try:
  from .deployment import desktop_word
except ImportError:
  from deployment import desktop_word


def contents(root, config, executable, settings, *, icon=""):
  root, config, executable = Path(root), Path(config), Path(executable)
  contents = {
    'launcher': '#!/bin/sh\nexec ' + shlex.quote(str(root / 'bin/hyprlarp')) + ' "$@"\n',
    'settings': json.dumps(settings, ensure_ascii=False, indent=2) + '\n',
    'bindings': generate_bindings(settings, executable),
    'gaps': render_window_gaps(settings),
    'prelude': '-- Load before your existing binds in hyprland.lua.\n'
      + 'local manager = dofile(' + lua_string(str(root / 'config/bindings-runtime.lua')) + ')\n'
      + 'manager.begin(' + lua_string(str(root / 'config/bindings-runtime.lua')) + ')\n',
    'session': '-- Load from hyprland.lua using dofile().\n'
      + 'dofile(' + lua_string(str(config / 'bindings.lua')) + ')\n'
      + 'local loadWindowGaps = dofile(' + lua_string(str(root / 'config/window-gaps-loader.lua')) + ')\n'
      + 'HyprLarpApplyWindowGaps = function()\n'
      + '  loadWindowGaps(' + lua_string(str(config / 'window-gaps.conf')) + ')\n'
      + 'end\n'
      + 'HyprLarpApplyWindowGaps()\n'
      + 'hl.on("hyprland.start", function()\n'
      + '  hl.exec_cmd(' + lua_string(shlex.quote(str(executable)) + ' start') + ')\n'
      + '  hl.exec_cmd(' + lua_string('hypridle -c ' + shlex.quote(str(config / 'hypridle.conf'))) + ')\n'
      + 'end)\n',
    'idle': 'general {\n  lock_cmd = ' + shlex.quote(str(executable)) + ' lock\n'
      + '  before_sleep_cmd = loginctl lock-session\n'
      + '  after_sleep_cmd = hyprctl dispatch \'hl.dsp.dpms({action = "on"})\'\n'
      + '  inhibit_sleep = 3\n}\n',
    'desktop': '[Desktop Entry]\nType=Application\nName=HyprLarp Settings\n'
      + 'Name[es]=Configuración de HyprLarp\nComment=Personaliza tu escritorio\n'
      + 'Exec=env ' + desktop_word(str(executable)) + ' settings\nIcon=hyprlarp\nTerminal=false\nCategories=Settings;DesktopSettings;\n',
    'icon': icon,
    'service': recovery.render_unit(executable, root),
  }
  return {role: text.encode('utf-8') for role, text in contents.items()}
