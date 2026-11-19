"""Minimal recovery helpers: no shell UI or main service imports."""

import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys


def preferences():
  directory = Path(os.environ.get('HYPRLARP_STATE_DIR', Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config')) / 'hyprlarp'))
  try:
    source = directory / 'settings.json'
    if source.stat().st_size > 2 * 1024 * 1024:
      raise ValueError('Oversized settings')
    saved = json.loads(source.read_text())
    scale = saved.get('accessibilityTextScale', 1)
    return {'textScale': scale if type(scale) in {int, float} and 1 <= scale <= 2 else 1}
  except (OSError, ValueError, TypeError, AttributeError):
    return {'textScale': 1}


def terminal():
  preferred = shlex.split(os.environ.get('TERMINAL', ''))
  for arguments in [preferred, ['kitty'], ['foot'], ['alacritty'], ['konsole'], ['xterm']]:
    if arguments and shutil.which(arguments[0]):
      subprocess.Popen(arguments, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
      return
  raise RuntimeError('No se encontró una terminal instalada')


if __name__ == '__main__':
  try:
    if sys.argv[1:] == ['preferences']:
      print(json.dumps(preferences()))
    elif sys.argv[1:] == ['terminal']:
      terminal()
    else:
      raise ValueError('Acción de recuperación desconocida')
  except (OSError, ValueError, RuntimeError) as error:
    print(str(error), file=sys.stderr)
    raise SystemExit(1)
