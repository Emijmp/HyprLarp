#!/usr/bin/env python3
"""Validate a release and prepare reviewable local assets; never publish or tag."""

from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
from backend.version import read_version

CHANGELOG_LIMIT = 256 * 1024
MANIFEST_LIMIT = 64 * 1024


def release_notes(root, release):
  path = Path(root) / "CHANGELOG.md"
  if path.is_symlink():
    raise ValueError("CHANGELOG.md debe ser un archivo regular")
  with path.open("rb") as source:
    content = source.read(CHANGELOG_LIMIT + 1)
  if len(content) > CHANGELOG_LIMIT:
    raise ValueError("CHANGELOG.md supera 256 KiB")
  text = content.decode("utf-8")
  headings = list(re.finditer(r"^## \[([^\]\r\n]+)\](?: - (\d{4}-\d{2}-\d{2}))?\s*$", text, re.MULTILINE))
  selected = [(index, heading) for index, heading in enumerate(headings) if heading[1] == release]
  if len(selected) != 1:
    raise ValueError("CHANGELOG.md debe contener una única sección para " + release)
  index, heading = selected[0]
  if not heading[2]:
    raise ValueError("La sección de publicación necesita fecha YYYY-MM-DD")
  date.fromisoformat(heading[2])
  end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
  body = text[heading.end():end].strip()
  if not body or not re.search(r"[\w]", body):
    raise ValueError("La publicación no tiene una descripción de cambios")
  return "# HyprLarp " + release + "\n\n" + body + "\n"


def git_output(root, *arguments):
  result = subprocess.run(["git", "-C", str(root), *arguments], capture_output=True, text=True, timeout=15)
  if result.returncode:
    raise ValueError("No se pudo verificar Git: " + (result.stderr.strip() or " ".join(arguments)))
  return result.stdout.strip()


def validate(root=ROOT, *, tag=None, verify_git=False):
  root = Path(root)
  release = read_version(root)
  expected = "v" + release
  if tag is not None and tag != expected:
    raise ValueError("La etiqueta debe ser " + expected + ", según VERSION")
  notes = release_notes(root, release)
  commit = None
  if verify_git:
    if tag is None:
      raise ValueError("La verificación de Git requiere --tag")
    commit = git_output(root, "rev-parse", "--verify", "HEAD^{commit}")
    tagged = git_output(root, "rev-parse", "--verify", "refs/tags/" + tag + "^{commit}")
    if tagged != commit:
      raise ValueError("La etiqueta no apunta al commit que se está construyendo")
    if git_output(root, "status", "--porcelain=v1", "--untracked-files=normal"):
      raise ValueError("La publicación requiere un árbol de trabajo limpio")
  return {"release": release, "tag": expected, "commit": commit, "notes": notes}


def digest(path):
  hasher = hashlib.sha256()
  with path.open("rb") as source:
    for chunk in iter(lambda: source.read(1024 * 1024), b""):
      hasher.update(chunk)
  return hasher.hexdigest()


def regular_asset(path, directory):
  path = Path(path)
  if (path.parent.resolve() != Path(directory).resolve() or path.is_symlink() or not path.is_file()
      or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.+\-]*", path.name)):
    raise ValueError("Artefacto de publicación no válido: " + path.name)
  return path


def write_checksums(directory, assets):
  directory = Path(directory)
  entries = sorted(regular_asset(path, directory) for path in assets)
  if not entries or len({path.name for path in entries}) != len(entries):
    raise ValueError("La lista de artefactos está vacía o contiene duplicados")
  destination = directory / "SHA256SUMS"
  if destination.is_symlink():
    raise ValueError("SHA256SUMS no puede ser un enlace simbólico")
  destination.write_text("".join(digest(path) + "  " + path.name + "\n" for path in entries), encoding="ascii")
  return destination


def verify_checksums(directory):
  directory = Path(directory)
  manifest = regular_asset(directory / "SHA256SUMS", directory)
  with manifest.open("rb") as source:
    content = source.read(MANIFEST_LIMIT + 1)
  if len(content) > MANIFEST_LIMIT:
    raise ValueError("SHA256SUMS supera 64 KiB")
  entries = []
  for line in content.decode("ascii").splitlines():
    match = re.fullmatch(r"([a-f0-9]{64})  ([A-Za-z0-9][A-Za-z0-9_.+\-]*)", line)
    if not match or match[2] == "SHA256SUMS":
      raise ValueError("SHA256SUMS contiene una entrada inválida")
    path = regular_asset(directory / match[2], directory)
    if path.name in entries:
      raise ValueError("SHA256SUMS contiene nombres duplicados")
    if digest(path) != match[1]:
      raise ValueError("La suma SHA-256 no coincide: " + path.name)
    entries.append(path.name)
  if not entries:
    raise ValueError("SHA256SUMS está vacío")
  return entries


def prepare(output, *, root=ROOT, tag=None, verify_git=False, source_only=False):
  state = validate(root, tag=tag, verify_git=verify_git)
  directory = Path(output).expanduser().absolute()
  if directory.is_symlink():
    raise ValueError("La carpeta de publicación no puede ser un enlace simbólico")
  directory.mkdir(parents=True, exist_ok=True)
  # Packaging owns the only source-file allowlist and the reproducible archiver.
  from tools.package import arch_version, source_archive, verify_source_archive
  release = state["release"]
  try:
    epoch = int(os.environ.get("SOURCE_DATE_EPOCH", "0"))
  except ValueError as error:
    raise ValueError("SOURCE_DATE_EPOCH debe ser un entero no negativo") from error
  if not 0 <= epoch <= 2 ** 31 - 1:
    raise ValueError("SOURCE_DATE_EPOCH fuera del rango admitido")
  source = directory / ("hyprlarp-" + release + ".tar.gz")
  if source.is_symlink():
    raise ValueError("El archivo fuente no puede ser un enlace simbólico")
  packages = list(directory.glob("*.pkg.tar.zst"))
  if not source_only:
    pattern = re.compile(r"hyprlarp-" + re.escape(arch_version(release)) + r"-[1-9][0-9]*-any\.pkg\.tar\.zst")
    if len(packages) != 1 or not pattern.fullmatch(packages[0].name):
      raise ValueError("Se requiere un único paquete Arch de la versión " + release)
  elif packages:
    raise ValueError("--source-only necesita una carpeta sin paquetes binarios")
  assets = [regular_asset(path, directory) for path in packages]
  notes = directory / "RELEASE_NOTES.md"
  if notes.is_symlink():
    raise ValueError("Las notas no pueden ser un enlace simbólico")
  recipe = directory / "PKGBUILD"
  if recipe.exists() or recipe.is_symlink():
    regular_asset(recipe, directory)
    regular_asset(source, directory)
    with recipe.open("rb") as stream:
      content = stream.read(MANIFEST_LIMIT + 1)
    if len(content) > MANIFEST_LIMIT:
      raise ValueError("PKGBUILD supera 64 KiB")
    text = content.decode("utf-8")
    names = re.findall(r"^source=\('([^'\r\n]+)'\)$", text, re.MULTILINE)
    hashes = re.findall(r"^sha256sums=\('([a-f0-9]{64})'\)$", text, re.MULTILINE)
    if names != [source.name] or hashes != [digest(source)]:
      raise ValueError("PKGBUILD no coincide con el archivo fuente preparado; reconstruye el paquete")
    epoch = verify_source_archive(source, root=Path(root))["source_date_epoch"]
  else:
    source_archive(source, root=Path(root), epoch=epoch)
  notes.write_text(state["notes"], encoding="utf-8")
  assets.extend([source, notes])
  if recipe.exists() or recipe.is_symlink():
    assets.append(regular_asset(recipe, directory))
  checksum = write_checksums(directory, assets)
  verify_checksums(directory)
  return {key: value for key, value in state.items() if key != "notes"} | {
    "assets": [path.name for path in sorted(assets)] + [checksum.name], "source_date_epoch": epoch}


def main():
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("--root", type=Path, default=ROOT, help="Árbol de fuentes a comprobar")
  commands = parser.add_subparsers(dest="command", required=True)
  for command in ["check", "prepare"]:
    item = commands.add_parser(command)
    item.add_argument("--tag", help="Etiqueta vVERSION esperada")
    item.add_argument("--verify-git", action="store_true", help="Exigir etiqueta existente, HEAD correcto y árbol limpio")
    if command == "prepare":
      item.add_argument("--output", required=True, type=Path)
      item.add_argument("--source-only", action="store_true", help="Preparar solo fuentes para revisión local")
  item = commands.add_parser("verify")
  item.add_argument("directory", type=Path)
  args = parser.parse_args()
  try:
    if args.command == "verify":
      result = {"verified": verify_checksums(args.directory)}
    elif args.command == "prepare":
      result = prepare(args.output, root=args.root, tag=args.tag, verify_git=args.verify_git, source_only=args.source_only)
    else:
      result = {key: value for key, value in validate(args.root, tag=args.tag, verify_git=args.verify_git).items() if key != "notes"}
    print(json.dumps(result, ensure_ascii=False, indent=2))
  except (OSError, ValueError, UnicodeError, subprocess.SubprocessError) as error:
    parser.exit(1, str(error) + "\n")


if __name__ == "__main__":
  main()
