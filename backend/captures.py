"""Capture drafts and bounded geometric annotations, only on explicit actions."""

import datetime as dt
import html
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import threading
import uuid


def window_geometry(window):
  if not isinstance(window, dict) or not isinstance(window.get("at"), list) or not isinstance(window.get("size"), list):
    raise ValueError("No hay una ventana activa disponible")
  x, y = window["at"]
  width, height = window["size"]
  if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in (x, y, width, height)) or width < 1 or height < 1:
    raise ValueError("Geometría de ventana inválida")
  return f"{int(x)},{int(y)} {int(width)}x{int(height)}"


def annotations_svg(operations, width, height):
  if not isinstance(operations, list) or len(operations) > 100:
    raise ValueError("El editor admite hasta 100 anotaciones")
  elements = []
  for item in operations:
    if not isinstance(item, dict) or item.get("kind") not in {"arrow", "text", "redact"}:
      raise ValueError("Anotación desconocida")
    values = [item.get(key) for key in ("x", "y", "x2", "y2")]
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in values):
      raise ValueError("Coordenadas inválidas")
    x, y = max(0, min(width, values[0])), max(0, min(height, values[1]))
    x2, y2 = max(0, min(width, values[2])), max(0, min(height, values[3]))
    if item["kind"] == "redact":
      elements.append(f'<rect x="{min(x,x2)}" y="{min(y,y2)}" width="{abs(x2-x)}" height="{abs(y2-y)}" fill="#000000"/>')
    elif item["kind"] == "arrow":
      angle = math.atan2(y2 - y, x2 - x)
      size = max(10, min(width, height) / 35)
      ax, ay = x2 - size * math.cos(angle - 0.45), y2 - size * math.sin(angle - 0.45)
      bx, by = x2 - size * math.cos(angle + 0.45), y2 - size * math.sin(angle + 0.45)
      elements.append(f'<path d="M{x} {y}L{x2} {y2}M{ax} {ay}L{x2} {y2}L{bx} {by}" fill="none" stroke="#000000" stroke-width="7"/>')
      elements.append(f'<path d="M{x} {y}L{x2} {y2}M{ax} {ay}L{x2} {y2}L{bx} {by}" fill="none" stroke="#ffffff" stroke-width="3"/>')
    else:
      text = item.get("text")
      if not isinstance(text, str) or not text.strip() or len(text) > 200:
        raise ValueError("El texto debe tener entre 1 y 200 caracteres")
      font = max(16, min(width, height) / 28)
      elements.append(f'<text x="{x}" y="{y}" font-family="DejaVu Sans" font-size="{font}" fill="#ffffff" stroke="#000000" stroke-width="1" paint-order="stroke">{html.escape(text)}</text>')
  return f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">' + "".join(elements) + "</svg>"


class Captures:
  def __init__(self, service, api):
    self.s, self.api = service, api
    self.lock = threading.RLock()
    self.drafts = {}
    self.directory = service.store.directory / "capture-drafts"
    # Drafts from an interrupted shell are never published as finished captures.
    if self.directory.exists() and not self.directory.is_symlink():
      for path in self.directory.glob("*"):
        if re.fullmatch(r"[a-f0-9]{32}\.(png|svg)", path.name) and path.is_file():
          path.unlink(missing_ok=True)

  def destination(self):
    pictures = Path(self.api.optional(["xdg-user-dir", "PICTURES"], str(Path.home() / "Pictures"))) / "Screenshots"
    pictures.mkdir(parents=True, exist_ok=True)
    path = pictures / f"HyprLarp-{dt.datetime.now():%Y%m%d-%H%M%S-%f}.png"
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(descriptor)
    return path

  def copy(self, path):
    with path.open("rb") as handle:
      subprocess.run(["wl-copy", "--type", "image/png"], stdin=handle, check=True, timeout=5)
    self.s.emit("message", "Captura guardada y copiada: " + path.name)

  def capture(self, data):
    mode = data.get("mode", "region")
    if mode not in {"region", "screen", "window"}:
      raise ValueError("Tipo de captura desconocido")
    annotate = data.get("annotate", False) is True
    if annotate and not shutil.which("magick"):
      raise RuntimeError("Instala ImageMagick para editar capturas")
    argv = ["grim"]
    if mode == "region":
      geometry = self.api.command(["slurp"], timeout=120)
      if not geometry:
        return
      argv += ["-g", geometry]
    elif mode == "window":
      argv += ["-g", window_geometry(json.loads(self.api.command(["hyprctl", "-j", "activewindow"])))]
    if annotate:
      self.api.private_directory(self.directory)
      token = uuid.uuid4().hex
      path = self.directory / (token + ".png")
    else:
      path = self.destination()
    self.api.command(argv + [str(path)])
    if annotate:
      path.chmod(0o600)
      dimensions = self.api.command(["magick", "identify", "-format", "%w %h", str(path)]).split()
      width, height = map(int, dimensions)
      with self.lock:
        self.drafts[token] = {"path": path, "width": width, "height": height}
      self.s.emit("capture-edit", {"token": token, "url": path.as_uri(), "width": width, "height": height})
    else:
      self.copy(path)

  def handle(self, action, data):
    if action not in {"capture-save", "capture-discard"}:
      return False
    if self.s.preview:
      raise RuntimeError("La vista previa no guarda capturas")
    token = data.get("token")
    with self.lock:
      if not isinstance(token, str) or token not in self.drafts:
        raise ValueError("El borrador de captura ya no está disponible")
      draft = self.drafts[token]
      if action == "capture-save":
        width, height = draft["width"], draft["height"]
        svg = annotations_svg(data.get("operations", []), width, height)
        overlay = self.directory / (token + ".svg")
        overlay.write_text(svg)
        argv = ["magick", str(draft["path"]), str(overlay), "-compose", "over", "-composite"]
        crop = data.get("crop")
        if crop is not None:
          if not isinstance(crop, dict) or set(crop) != {"x", "y", "width", "height"}:
            raise ValueError("Recorte inválido")
          if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in crop.values()):
            raise ValueError("Recorte inválido")
          x, y = max(0, int(crop["x"])), max(0, int(crop["y"]))
          w, h = min(int(crop["width"]), width - x), min(int(crop["height"]), height - y)
          if w < 1 or h < 1:
            raise ValueError("El recorte está fuera de la imagen")
          argv += ["-crop", f"{w}x{h}+{x}+{y}", "+repage"]
        destination = self.destination()
        self.api.command(argv + [str(destination)], timeout=15)
        self.copy(destination)
      draft["path"].unlink(missing_ok=True)
      (self.directory / (token + ".svg")).unlink(missing_ok=True)
      del self.drafts[token]
    return True
