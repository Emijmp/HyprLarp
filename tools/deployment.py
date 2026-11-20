"""Fixed installation paths, staged copies and an owned-file manifest."""

from dataclasses import dataclass
from contextlib import contextmanager
from datetime import datetime
import fcntl
import hashlib
import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.service import atomic_bytes, read_json
from tools.package import SOURCE_DIRS, SOURCE_FILES, SOURCE_SUFFIXES, files as selected_sources

MARKER = ".hyprlarp-install.json"
DIRECTORIES, FILES, SUFFIXES = SOURCE_DIRS, SOURCE_FILES, SOURCE_SUFFIXES


def absolute(path):
  path = Path(path).expanduser()
  if any(ord(character) < 32 for character in str(path)):
    raise ValueError("La ruta contiene caracteres de control")
  return Path(os.path.abspath(path))


def no_symlinks(path):
  for candidate in [path, *path.parents]:
    if candidate.is_symlink():
      raise ValueError("La instalación no escribe a través de enlaces simbólicos: " + str(candidate))


def digest(path):
  with path.open("rb") as source:
    return hashlib.file_digest(source, "sha256").hexdigest() if hasattr(hashlib, "file_digest") else hashlib.sha256(source.read()).hexdigest()


@contextmanager
def deployment_lock(locations):
  locations.app.parent.mkdir(parents=True, exist_ok=True)
  filename = locations.app.parent / ".hyprlarp-install.lock"
  no_symlinks(filename)
  descriptor = os.open(filename, os.O_CREAT | os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600)
  try:
    try:
      fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as error:
      raise ValueError("Ya hay otra instalación o desinstalación en curso") from error
    yield
  finally:
    os.close(descriptor)


@dataclass
class Locations:
  app: Path
  config: Path
  executable: Path
  data: Path
  prefix: str = ""

  @classmethod
  def create(cls, prefix=None):
    if prefix:
      base = absolute(prefix)
      return cls(base / "share/hyprlarp", base / "config/hyprlarp", base / "bin/hyprlarp", base / "share", str(base))
    home = Path.home()
    data = absolute(os.environ.get("XDG_DATA_HOME", home / ".local/share"))
    config = absolute(os.environ.get("XDG_CONFIG_HOME", home / ".config"))
    return cls(data / "hyprlarp", config / "hyprlarp", home / ".local/bin/hyprlarp", data)

  def managed(self):
    return {"launcher": self.executable, "bindings": self.config / "bindings.lua", "prelude": self.config / "bindings-prelude.lua", "gaps": self.config / "window-gaps.conf", "session": self.config / "hyprlarp.lua",
      "idle": self.config / "hypridle.conf", "desktop": self.data / "applications/hyprlarp-settings.desktop",
      "icon": self.data / "icons/hicolor/scalable/apps/hyprlarp.svg",
      "service": self.config.parent / "systemd/user/hyprlarp.service"}

  def validate(self, installing=False):
    roots = (self.app, self.config, self.executable)
    for index, left in enumerate(roots):
      for right in roots[index + 1:]:
        if left == right or left.is_relative_to(right) or right.is_relative_to(left):
          raise ValueError("Las rutas de programa, ajustes y ejecutable no pueden solaparse")
    if installing and (self.app == ROOT or self.app.is_relative_to(ROOT) or ROOT.is_relative_to(self.app)):
      raise ValueError("El destino debe estar fuera del repositorio y de sus directorios superiores")
    for path in [self.app, self.config, self.config / "settings.json", *self.managed().values()]:
      no_symlinks(path)
    if "=" in str(self.executable):
      raise ValueError("La ruta del ejecutable no puede contener '=' en una entrada de escritorio")


def desktop_word(value):
  # Desktop Entry unescapes strings before parsing the Exec argument quoting.
  escaped = "".join("\\" + character if character in {'"', "`", "$", "\\"} else character for character in value)
  return '"' + escaped.replace("\\", "\\\\").replace("%", "%%") + '"'


def copy_sources(destination):
  result = {}
  for name, source in selected_sources(ROOT).items():
    target = destination / name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    result[name] = digest(target)
  return result


def commit(locations, stage, contents, manifest, activate=None):
  """Keep backups on success; restore them if any managed write fails."""
  stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
  backups, written = {}, []
  targets = {**locations.managed(), "settings": locations.config / "settings.json"}
  if set(contents) - set(targets):
    raise ValueError("El plan contiene destinos de instalación desconocidos")
  try:
    # Unchanged configuration is outside the write transaction: never rename it
    # merely because the application code is being updated.
    for target in [locations.app, *[targets[role] for role in contents]]:
      no_symlinks(target)
      if target.exists():
        backup = target.with_name(target.name + ".backup-" + stamp)
        target.rename(backup)
        backups[target] = backup
    os.replace(stage, locations.app)
    written.append(locations.app)
    for role, data in contents.items():
      target = targets[role]
      written.append(target)
      atomic_bytes(target, data)
      if role == "launcher":
        target.chmod(0o755)
    atomic_bytes(locations.app / MARKER, manifest)
    if activate is not None:
      activate()
    return list(backups.values())
  except BaseException:
    for target in reversed(written):
      if target == locations.app:
        shutil.rmtree(target)
      else:
        target.unlink(missing_ok=True)
    for target, backup in backups.items():
      if backup.exists():
        backup.rename(target)
    raise


def load_manifest(locations):
  manifest = read_json(locations.app / MARKER, limit=4 * 1024 * 1024)
  if not isinstance(manifest, dict) or manifest.get("type") != "hyprlarp-install" or manifest.get("version") != 1:
    raise ValueError("No hay un manifiesto de instalación válido")
  if manifest.get("prefix", "") != locations.prefix:
    raise ValueError("El prefijo no coincide con el manifiesto de instalación")
  if not isinstance(manifest.get("files"), dict) or not isinstance(manifest.get("managed"), dict):
    raise ValueError("El manifiesto no contiene los archivos gestionados")
  for name, value in manifest["files"].items():
    relative = Path(name)
    hidden = any(part.startswith(".") and part not in FILES and not (
      index == 0 and part == ".github" and len(relative.parts) >= 3 and relative.parts[1] == "workflows")
      for index, part in enumerate(relative.parts))
    if relative.is_absolute() or ".." in relative.parts or not relative.parts or hidden:
      raise ValueError("Ruta no válida en el manifiesto")
    if not isinstance(value, str) or len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
      raise ValueError("Hash de archivo no válido")
  if set(manifest["managed"]) - set(locations.managed()):
    raise ValueError("El manifiesto incluye destinos desconocidos")
  if any(not isinstance(value, str) or len(value) != 64 or any(character not in "0123456789abcdef" for character in value) for value in manifest["managed"].values()):
    raise ValueError("Hash de destino no válido")
  return manifest
