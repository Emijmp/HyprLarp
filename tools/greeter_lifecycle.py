"""Bounded, private snapshots for the optional greeter's two-phase lifecycle."""

from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat

LIMIT = 512 * 1024 * 1024
FILE_LIMIT = 64 * 1024 * 1024
COUNT_LIMIT = 4096


def no_symlinks(path):
  path = Path(path)
  for entry in [path, *path.parents]:
    if entry.is_symlink():
      raise ValueError('No se escribe a través de enlaces simbólicos: ' + str(entry))


def fingerprint(path):
  path = Path(path)
  no_symlinks(path)
  if not path.exists():
    return None
  info = path.stat()
  if not stat.S_ISREG(info.st_mode) or info.st_size > FILE_LIMIT:
    raise ValueError('El archivo debe ser regular y respetar el límite: ' + str(path))
  with path.open('rb') as source:
    digest = hashlib.file_digest(source, 'sha256').hexdigest()
  return {'sha256': digest, 'mode': stat.S_IMODE(info.st_mode), 'uid': info.st_uid, 'gid': info.st_gid}


def atomic_write(path, data, *, mode=0o600, uid=None, gid=None):
  from backend.greeter import atomic_write as write
  no_symlinks(path)
  write(path, data)
  if uid is not None and gid is not None and os.geteuid() == 0:
    os.chown(path, uid, gid)
  path.chmod(mode)


@contextmanager
def locked(path):
  no_symlinks(path)
  path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
  descriptor = os.open(path, os.O_CREAT | os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600)
  try:
    try:
      fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
      raise RuntimeError('Hay otra operación del greeter en curso') from None
    yield
  finally:
    os.close(descriptor)


class Snapshot:
  """Targets are supplied by code, never taken from an untrusted manifest."""
  def __init__(self, directory, targets):
    self.directory = Path(directory)
    self.targets = {name: Path(path) for name, path in targets.items()}
    no_symlinks(self.directory)
    document = json.loads((self.directory / 'snapshot.json').read_text())
    if document.get('type') != 'hyprlarp-greeter-snapshot' or document.get('version') != 1:
      raise ValueError('Copia del greeter inválida')
    if set(document.get('targets', {})) != set(self.targets):
      raise ValueError('Los destinos de la copia no coinciden')
    self.records = document['targets']
    for name, record in self.records.items():
      if record.get('path') != str(self.targets[name]) or record.get('kind') not in {'missing', 'file', 'directory'}:
        raise ValueError('Destino de copia inválido')
      if not isinstance(record.get('entries'), dict) or len(record['entries']) > COUNT_LIMIT:
        raise ValueError('Contenido de copia inválido')
      for relative, item in record['entries'].items():
        part = Path(relative)
        if part.is_absolute() or '..' in part.parts or (relative == '.' and record['kind'] != 'file'):
          raise ValueError('Ruta de copia inválida')
        if item.get('kind') not in {'file', 'directory'}:
          raise ValueError('Tipo de copia inválido')
        if item['kind'] == 'file':
          blob = item.get('blob', '')
          if not isinstance(blob, str) or not blob.isdecimal() or not fingerprint(self.directory / 'files' / blob):
            raise ValueError('Archivo de copia no disponible')
          if fingerprint(self.directory / 'files' / blob)['sha256'] != item.get('sha256'):
            raise ValueError('La copia del greeter fue modificada')

  @classmethod
  def capture(cls, directory, targets):
    directory = Path(directory)
    no_symlinks(directory)
    directory.mkdir(parents=True, mode=0o700)
    directory.chmod(0o700)
    (directory / 'files').mkdir(mode=0o700)
    records, count, total = {}, 0, 0
    for name, path in targets.items():
      path = Path(path)
      no_symlinks(path)
      record = {'path': str(path), 'kind': 'missing', 'entries': {}}
      if path.exists():
        info = path.stat()
        if not (path.is_file() or path.is_dir()):
          raise ValueError('Destino de copia no regular: ' + str(path))
        record.update(kind='file' if path.is_file() else 'directory', mode=stat.S_IMODE(info.st_mode), uid=info.st_uid, gid=info.st_gid)
        candidates = [path] if path.is_file() else sorted(path.rglob('*'))
        for entry in candidates:
          no_symlinks(entry)
          info = entry.stat()
          if not (entry.is_file() or entry.is_dir()):
            raise ValueError('Destino de copia no regular: ' + str(entry))
          count += 1
          if count > COUNT_LIMIT:
            raise ValueError('La copia del greeter contiene demasiados archivos')
          relative = '.' if path.is_file() else entry.relative_to(path).as_posix()
          item = {'kind': 'file' if entry.is_file() else 'directory', 'mode': stat.S_IMODE(info.st_mode), 'uid': info.st_uid, 'gid': info.st_gid}
          if entry.is_file():
            total += info.st_size
            if info.st_size > FILE_LIMIT or total > LIMIT:
              raise ValueError('La copia del greeter supera el límite de tamaño')
            item.update(fingerprint(entry), blob=str(count))
            shutil.copyfile(entry, directory / 'files' / str(count))
          record['entries'][relative] = item
      records[name] = record
    atomic_write(directory / 'snapshot.json', (json.dumps({'type': 'hyprlarp-greeter-snapshot', 'version': 1, 'targets': records}, indent=2) + '\n').encode())
    return cls(directory, targets)

  def data(self, name, relative='.'):
    item = self.records[name]['entries'].get(relative)
    if item is None or item['kind'] != 'file':
      return None
    return (self.directory / 'files' / item['blob']).read_bytes()

  @staticmethod
  def remove(path):
    no_symlinks(path)
    if path.is_dir():
      # Refuse links inside a tree before rmtree; never traverse another target.
      for item in path.rglob('*'):
        no_symlinks(item)
      shutil.rmtree(path)
    else:
      path.unlink(missing_ok=True)

  @staticmethod
  def metadata(path, item):
    if os.geteuid() == 0:
      os.chown(path, item['uid'], item['gid'])
    path.chmod(item['mode'])

  def restore(self):
    for name, target in self.targets.items():
      self.remove(target)
      record = self.records[name]
      if record['kind'] == 'missing':
        continue
      if record['kind'] == 'directory':
        target.mkdir(parents=True, mode=record['mode'])
      for relative, item in sorted(record['entries'].items(), key=lambda pair: len(Path(pair[0]).parts)):
        path = target if relative == '.' else target / relative
        if item['kind'] == 'directory':
          path.mkdir(parents=True, exist_ok=True, mode=item['mode'])
        else:
          path.parent.mkdir(parents=True, exist_ok=True)
          atomic_write(path, self.data(name, relative), mode=item['mode'], uid=item['uid'], gid=item['gid'])
        self.metadata(path, item)
      if record['kind'] == 'directory':
        self.metadata(target, record)

  def restore_owned(self, owned, *, skip=()):
    """Restore original files only if the installed version is still present."""
    restored, preserved = [], []
    for name, target in self.targets.items():
      if name in skip:
        continue
      original, installed = self.records[name], owned.records[name]
      # A baseline file absent from our ownership list belongs to someone else.
      # In particular, never recreate an administrator-deleted unrelated file.
      relatives = set(installed['entries'])
      for relative in sorted(relatives, key=lambda value: len(Path(value).parts), reverse=True):
        path = target if relative == '.' else target / relative
        old, current = original['entries'].get(relative), installed['entries'].get(relative)
        if (old or current)['kind'] == 'directory':
          continue
        if path.is_symlink() or (path.exists() and not path.is_file()):
          preserved.append(str(path))
          continue
        actual = fingerprint(path)
        wanted = {key: current[key] for key in ['sha256', 'mode', 'uid', 'gid']} if current and current['kind'] == 'file' else None
        if actual != wanted:
          if actual is not None:
            preserved.append(str(path))
          continue
        if old and old['kind'] == 'file':
          atomic_write(path, self.data(name, relative), mode=old['mode'], uid=old['uid'], gid=old['gid'])
        else:
          path.unlink(missing_ok=True)
        restored.append(str(path))
      # Keep unknown files and nonempty directories. Restore original permissions.
      dirs = [target / relative for relative, item in installed['entries'].items()
        if item['kind'] == 'directory' and relative not in original['entries']]
      if installed['kind'] == 'directory' and original['kind'] == 'missing':
        dirs.append(target)
      for path in sorted(dirs, key=lambda value: len(value.parts), reverse=True):
        no_symlinks(path)
        if path.is_dir():
          try:
            path.rmdir()
          except OSError:
            pass
      if original['kind'] == 'directory' and target.is_dir():
        directory_records = [('.', original)] + [(relative, item) for relative, item in original['entries'].items()
          if item['kind'] == 'directory' and relative in installed['entries']]
        for relative, item in directory_records:
          path = target if relative == '.' else target / relative
          no_symlinks(path)
          if not path.exists():
            continue
          created = False
          if path.exists() and not path.is_dir():
            preserved.append(str(path))
            continue
          path.mkdir(parents=True, exist_ok=True, mode=item['mode'])
          installed_item = installed if relative == '.' else installed['entries'].get(relative)
          actual = path.stat()
          if created or (installed_item and all(actual_value == installed_item[key]
              for key, actual_value in [('mode', stat.S_IMODE(actual.st_mode)), ('uid', actual.st_uid), ('gid', actual.st_gid)])):
            self.metadata(path, item)
          elif installed_item:
            preserved.append(str(path))
    return {'restored': restored, 'preserved': preserved}
