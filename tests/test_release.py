"""Release preparation validates provenance and catches modified assets."""

import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from tools import package, release


class ReleaseTests(unittest.TestCase):
  def setUp(self):
    self.temporary = tempfile.TemporaryDirectory(prefix="hyprlarp-release-")
    self.addCleanup(self.temporary.cleanup)
    self.root = Path(self.temporary.name)
    (self.root / "VERSION").write_text("0.1.0\n")
    self.changelog = self.root / "CHANGELOG.md"
    self.changelog.write_text("# Cambios\n\n## [Unreleased]\n\nPendiente.\n\n## [0.1.0] - 2026-11-19\n\n- Primera versión ñ.\n")

  def prepare_package(self, output, *, epoch=123):
    template = self.root / 'packaging/arch/PKGBUILD.in'
    template.parent.mkdir(parents=True, exist_ok=True)
    template.write_bytes((package.ROOT / 'packaging/arch/PKGBUILD.in').read_bytes())
    return package.prepare(output, root=self.root, epoch=epoch)

  def test_notes_select_only_the_exact_current_release(self):
    state = release.validate(self.root, tag="v0.1.0")
    self.assertEqual(state["release"], "0.1.0")
    self.assertEqual(state["notes"], "# HyprLarp 0.1.0\n\n- Primera versión ñ.\n")
    self.assertNotIn("Pendiente", state["notes"])
    self.assertIsNone(state["commit"])

  def test_wrong_tag_empty_duplicate_and_invalid_date_are_rejected(self):
    with self.assertRaisesRegex(ValueError, "etiqueta"):
      release.validate(self.root, tag="v0.2.0")
    for body in ["## [0.1.0] - 2026-11-19\n", "## [0.1.0]\n- Cambios", "## [0.1.0] - 2026-02-31\n- Cambios",
      "## [0.1.0] - 2026-11-19\n- Uno\n## [0.1.0] - 2026-11-19\n- Dos"]:
      with self.subTest(body=body):
        self.changelog.write_text(body)
        with self.assertRaises(ValueError):
          release.validate(self.root)

  def test_changelog_budget_and_symlinks_are_checked(self):
    self.changelog.write_bytes(b"x" * (release.CHANGELOG_LIMIT + 1))
    with self.assertRaisesRegex(ValueError, "256 KiB"):
      release.validate(self.root)
    self.changelog.unlink()
    target = self.root / "elsewhere.md"
    target.write_text("kept")
    self.changelog.symlink_to(target)
    with self.assertRaises(ValueError):
      release.validate(self.root)
    self.assertEqual(target.read_text(), "kept")

  def test_checksums_are_stable_sorted_and_detect_later_modification(self):
    for name, content in [("z.tar.gz", b"z"), ("a.pkg.tar.zst", b"a")]:
      (self.root / name).write_bytes(content)
    files = [self.root / "z.tar.gz", self.root / "a.pkg.tar.zst"]
    manifest = release.write_checksums(self.root, files)
    expected = "".join(hashlib.sha256(content).hexdigest() + "  " + name + "\n"
      for name, content in [("a.pkg.tar.zst", b"a"), ("z.tar.gz", b"z")])
    self.assertEqual(manifest.read_text(), expected)
    self.assertEqual(release.verify_checksums(self.root), ["a.pkg.tar.zst", "z.tar.gz"])
    (self.root / "z.tar.gz").write_bytes(b"changed")
    with self.assertRaisesRegex(ValueError, "no coincide"):
      release.verify_checksums(self.root)

  def test_checksums_refuse_paths_duplicates_symlinks_and_bad_names(self):
    file = self.root / "source.tar.gz"
    file.write_bytes(b"source")
    with self.assertRaises(ValueError):
      release.write_checksums(self.root, [file, file])
    alias = self.root / "alias.tar.gz"
    alias.symlink_to(file)
    with self.assertRaises(ValueError):
      release.write_checksums(self.root, [alias])
    outside = self.root / "nested"
    outside.mkdir()
    other = outside / "outside.tar.gz"
    other.touch()
    with self.assertRaises(ValueError):
      release.write_checksums(self.root, [other])
    bad = self.root / "source\nprivate.tar.gz"
    bad.touch()
    with self.assertRaises(ValueError):
      release.write_checksums(self.root, [bad])
    for content in ["", "0" * 64 + "  ../VERSION\n", "0" * 64 + "  /etc/passwd\n"]:
      (self.root / "SHA256SUMS").write_text(content)
      with self.assertRaises(ValueError):
        release.verify_checksums(self.root)

  @unittest.skipUnless(shutil.which("git"), "Git unavailable")
  def test_verified_git_requires_clean_tree_and_exact_existing_tag(self):
    def git(*args):
      return subprocess.run(["git", "-C", str(self.root), *args], check=True,
        capture_output=True, text=True)
    git("init")
    git("config", "user.name", "Release fixture")
    git("config", "user.email", "fixture@example.invalid")
    git("add", "VERSION", "CHANGELOG.md")
    git("commit", "-m", "Fixture")
    with self.assertRaises(ValueError):
      release.validate(self.root, tag="v0.1.0", verify_git=True)
    git("tag", "v0.1.0")
    self.assertEqual(release.validate(self.root, tag="v0.1.0", verify_git=True)["commit"], git("rev-parse", "HEAD").stdout.strip())
    (self.root / "private.json").write_text("{}")
    with self.assertRaisesRegex(ValueError, "limpio"):
      release.validate(self.root, tag="v0.1.0", verify_git=True)
    (self.root / "private.json").unlink()
    self.changelog.write_text(self.changelog.read_text() + "\nEdit\n")
    with self.assertRaisesRegex(ValueError, "limpio"):
      release.validate(self.root, tag="v0.1.0", verify_git=True)
    git("add", "CHANGELOG.md")
    git("commit", "-m", "Later")
    with self.assertRaisesRegex(ValueError, "no apunta"):
      release.validate(self.root, tag="v0.1.0", verify_git=True)

  def test_prepare_preserves_the_packager_sources_and_checksums_exact_reviewable_assets(self):
    output = self.root / "dist"
    metadata = self.prepare_package(output)
    (output / "hyprlarp-0.1.0-1-any.pkg.tar.zst").write_bytes(b"package")
    source = output / metadata['source']
    previous = source.read_bytes(), source.stat().st_ino
    with patch('tools.package.source_archive', side_effect=AssertionError('Prepared sources must be preserved')), \
        patch.dict(os.environ, {"SOURCE_DATE_EPOCH": "999"}):
      report = release.prepare(output, root=self.root, tag="v0.1.0")
    self.assertEqual(report["source_date_epoch"], 123)
    self.assertEqual((source.read_bytes(), source.stat().st_ino), previous)
    self.assertIn(hashlib.sha256(source.read_bytes()).hexdigest(), (output / 'PKGBUILD').read_text())
    self.assertEqual(report["assets"], ["PKGBUILD", "RELEASE_NOTES.md", "hyprlarp-0.1.0-1-any.pkg.tar.zst", "hyprlarp-0.1.0.tar.gz", "SHA256SUMS"])
    self.assertEqual(set(release.verify_checksums(output)), set(report["assets"]) - {"SHA256SUMS"})
    self.assertNotIn(str(self.root), str(report))

  def test_prepare_refuses_incoherent_recipe_or_stale_sources_before_writing_release_files(self):
    output = self.root / 'dist'
    metadata = self.prepare_package(output)
    source = output / metadata['source']
    original_source = source.read_bytes()
    recipe = output / 'PKGBUILD'
    original_recipe = recipe.read_text()
    cases = ['checksum', 'source name', 'missing source', 'stale tree']
    for case in cases:
      with self.subTest(case=case):
        source.write_bytes(original_source)
        recipe.write_text(original_recipe)
        self.changelog.write_text(self.changelog.read_text().removesuffix('\nExtra change.\n'))
        if case == 'checksum':
          recipe.write_text(original_recipe.replace(metadata['sha256'], '0' * 64))
        elif case == 'source name':
          recipe.write_text(original_recipe.replace(metadata['source'], 'other.tar.gz'))
        elif case == 'missing source':
          source.unlink()
        else:
          self.changelog.write_text(self.changelog.read_text() + '\nExtra change.\n')
        with self.assertRaises(ValueError):
          release.prepare(output, root=self.root, source_only=True)
        self.assertFalse((output / 'RELEASE_NOTES.md').exists())
        self.assertFalse((output / 'SHA256SUMS').exists())

  def test_prepare_refuses_wrong_packages_or_epoch_before_creating_source(self):
    output = self.root / "dist"
    output.mkdir()
    package = output / "hyprlarp-0.2.0-1-any.pkg.tar.zst"
    package.touch()
    with self.assertRaisesRegex(ValueError, "único paquete"):
      release.prepare(output, root=self.root)
    package.unlink()
    for value in ["wrong", "-1"]:
      with patch.dict(os.environ, {"SOURCE_DATE_EPOCH": value}), self.assertRaises(ValueError):
        release.prepare(output, root=self.root, source_only=True)
    self.assertFalse((output / "hyprlarp-0.1.0.tar.gz").exists())

  def test_source_only_preparation_is_explicit_and_never_tags_or_publishes(self):
    output = self.root / "preview"
    with patch("tools.release.subprocess.run", side_effect=AssertionError("No Git or GitHub writes expected")):
      report = release.prepare(output, root=self.root, source_only=True)
    self.assertEqual(report["tag"], "v0.1.0")
    self.assertIn("hyprlarp-0.1.0.tar.gz", report["assets"])
    self.assertFalse(any(path.name.endswith(".pkg.tar.zst") for path in output.iterdir()))
