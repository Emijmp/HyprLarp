"""The release shared by the frontend, backend and standalone greeter."""

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
_NUMBER = r'(?:0|[1-9][0-9]*)'
_RELEASE = re.compile(rf'{_NUMBER}\.{_NUMBER}\.{_NUMBER}(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?')


def read_version(root=ROOT):
  """Read a bounded SemVer value from the installed bundle, without Git."""
  with (Path(root) / 'VERSION').open('rb') as source:
    content = source.read(129)
  if len(content) > 128:
    raise ValueError('VERSION supera el límite de 128 bytes')
  try:
    value = content.decode('ascii').strip()
  except UnicodeDecodeError as error:
    raise ValueError('VERSION debe contener una versión ASCII válida') from error
  match = _RELEASE.fullmatch(value)
  if not match or (match.group(1) and any(part.isdecimal() and len(part) > 1 and part.startswith('0') for part in match.group(1).split('.'))):
    raise ValueError('VERSION debe contener una versión semántica válida')
  return value


VERSION = read_version()
