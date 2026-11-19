#!/usr/bin/env python3
"""Run backend tests and compile every interactive QML panel offscreen."""

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
GUI_TIMEOUT = 90


def main() -> int:
  parser = argparse.ArgumentParser(description=__doc__)
  mode = parser.add_mutually_exclusive_group()
  mode.add_argument("--backend-only", action="store_true", help="Solo lógica e instalación aislada")
  mode.add_argument("--ui-only", action="store_true", help="Solo comprobaciones de interfaz")
  args = parser.parse_args()
  if not args.ui_only:
    result = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"], cwd=ROOT)
    if result.returncode:
      return result.returncode
  if args.backend_only:
    return 0
  binary = shutil.which("quickshell") or shutil.which("qs")
  if not binary:
    print("Quickshell no está instalado; falta verificar la interfaz.", file=sys.stderr)
    return 1
  with tempfile.TemporaryDirectory(prefix="hyprlarp-check-") as temporary:
    wallpapers = Path(temporary) / "fondos # % ñ"
    wallpapers.mkdir()
    image = wallpapers / "imagen # % ñ.svg"
    image.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="80" height="60"><rect width="80" height="60" fill="#454545"/></svg>')
    environment = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "QT_QUICK_BACKEND": "software",
           "XDG_RUNTIME_DIR": temporary, "HYPRLARP_STATE_DIR": str(Path(temporary) / "settings"),
           "HYPRLARP_PREVIEW": "1", "HYPRLARP_SMOKE_TEST": "1", "HYPRLARP_CAPTURE": "",
           "HYPRLARP_TEST_FILE_QUERY": str(wallpapers) + "/imagen", "HYPRLARP_TEST_FILE_PATH": str(image),
           "HYPRLARP_TEST_WALLPAPERS": str(wallpapers), "HYPRLARP_TEST_WALLPAPER_URL": image.as_uri()}
    environment.pop("WAYLAND_DISPLAY", None)
    try:
      result = subprocess.run([binary, "--path", str(ROOT), "--no-color"], env=environment,
                  text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=GUI_TIMEOUT)
    except subprocess.TimeoutExpired as error:
      print((error.stdout or b"").decode() if isinstance(error.stdout, bytes) else error.stdout)
      print(f"La prueba de interfaz superó los {GUI_TIMEOUT} segundos.", file=sys.stderr)
      return 1
    print(result.stdout)
    errors = [line for line in result.stdout.splitlines()
         if ("WARN scene:" in line or ("WARN:" in line and "qs:@" in line) or "Failed to load" in line or "unavailable" in line
           or "TypeError:" in line or "ReferenceError:" in line or "Cannot assign" in line
           or "Unable to assign" in line or "Binding loop" in line
           or "Could not convert argument" in line or "WARN: Context2D:" in line)]
    if result.returncode or errors or "SMOKE COMPLETE" not in result.stdout:
      print("La interfaz necesita correcciones.", file=sys.stderr)
      return 1
    # An ordinary preview must stay open when capture variables are absent.
    environment.pop("HYPRLARP_CAPTURE", None)
    environment.pop("HYPRLARP_SETTINGS_CAPTURE", None)
    environment.pop("HYPRLARP_SMOKE_TEST", None)
    preview = subprocess.Popen([str(ROOT / "bin/hyprlarp"), "preview"], env=environment,
                 text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
      output, _ = preview.communicate(timeout=3.5)
      print(output)
      print("La vista previa se cerró antes de tiempo.", file=sys.stderr)
      return 1
    except subprocess.TimeoutExpired:
      preview.terminate()
      try:
        output, _ = preview.communicate(timeout=5)
      except subprocess.TimeoutExpired:
        preview.kill()
        output, _ = preview.communicate()
      if any(marker in output for marker in ("WARN scene:", "Failed to load", "TypeError:", "ReferenceError:")):
        print(output)
        return 1
      print("La vista previa permanece abierta sin variables de captura.")
  print("Backend y todos los paneles comprobados.")
  return 0


if __name__ == "__main__":
  sys.exit(main())
