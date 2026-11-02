"""Bounded persistent pins and on-demand thumbnails for cliphist."""

import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import threading
import time


class Clipboard:
  LIMIT = 16 * 1024 * 1024

  def __init__(self, service, api):
    self.s, self.api = service, api
    self.lock = threading.RLock()
    self.directory = service.store.directory / "clipboard"
    self.state = {"pins": {}, "seen": {}}
    try:
      if self.directory.exists():
        self.api.private_directory(self.directory)
      loaded = self.api.read_json(self.directory / "index.json")
      if isinstance(loaded, dict) and isinstance(loaded.get("pins"), dict) and isinstance(loaded.get("seen"), dict):
        self.state = loaded
    except (OSError, ValueError):
      pass
    self.state["pins"] = {key: value for key, value in self.state["pins"].items()
      if re.fullmatch(r"[a-f0-9]{64}", key) and isinstance(value, dict) and isinstance(value.get("text"), str)}
    self.state["pins"] = {key: {"text": value["text"][:512], "image": bool(value.get("image"))} for key, value in list(self.state["pins"].items())[:50]}
    self.state["seen"] = {key: value for key, value in self.state["seen"].items()
      if key.isdecimal() and isinstance(value, (int, float))}

  def save(self):
    self.api.private_directory(self.directory)
    self.api.atomic_json(self.directory / "index.json", self.state)

  @staticmethod
  def entry(raw):
    if not isinstance(raw, str) or len(raw) > 65536 or not re.match(r"^\d+\t", raw):
      raise ValueError("Entrada de portapapeles inválida")
    return raw.split("\t", 1)

  def pin_id(self, value):
    if not isinstance(value, str) or value not in self.state["pins"]:
      raise ValueError("La entrada fijada ya no existe")
    return value

  def decode(self, data):
    if data.get("pin"):
      self.api.private_directory(self.directory)
      ident = self.pin_id(data["pin"])
      content = self.api.read_regular(self.directory / (ident + ".data"), self.LIMIT)
    else:
      raw = data.get("raw", "")
      self.entry(raw)
      content = self.api.bounded_process(["cliphist", "decode"], content=raw.encode(), timeout=5, limit=self.LIMIT)
    if len(content) > self.LIMIT:
      raise ValueError("La entrada supera 16 MiB")
    return content

  def refresh(self, *, expire=False):
    with self.lock:
      lines = self.api.optional(["cliphist", "-preview-width", "256", "list"]).splitlines()[:5000] if self.s.store.settings["clipboardEnabled"] else []
      now = int(time.time())
      changed, entries, active = False, [], set()
      retention = self.s.store.settings["clipboardRetentionHours"] * 3600
      for raw in lines:
        try:
          ident, text = self.entry(raw)
        except ValueError:
          continue
        active.add(ident)
        if retention and ident not in self.state["seen"]:
          self.state["seen"][ident] = now
          changed = True
        if expire and retention and now - self.state["seen"].get(ident, now) >= retention and not self.s.preview:
          self.api.command(["cliphist", "delete"], input_text=raw)
          self.state["seen"].pop(ident, None)
          changed = True
          continue
        if len(entries) < 100:
          entries.append({"id": ident, "text": text, "raw": raw, "image": "[[ binary data" in text})
      old_seen = self.state["seen"]
      self.state["seen"] = {key: value for key, value in old_seen.items() if key in active} if retention else {}
      changed = changed or self.state["seen"] != old_seen
      pins = [{"id": "pin:" + ident, "pin": ident, **entry} for ident, entry in self.state["pins"].items()
        if (self.directory / (ident + ".data")).is_file()]
      if changed:
        self.save()
      self.s.emit_changed("clipboard", pins + entries)

  def handle(self, action, data):
    if action not in {"clipboard-pin", "clipboard-unpin", "clipboard-thumbnail", "clipboard-copy", "clipboard-delete", "clipboard-clear"}:
      return False
    if self.s.preview:
      raise RuntimeError("La vista previa no modifica el portapapeles")
    with self.lock:
      if action == "clipboard-pin":
        content = self.decode(data)
        ident = hashlib.sha256(content).hexdigest()
        if ident not in self.state["pins"] and len(self.state["pins"]) >= 50:
          raise ValueError("Puedes fijar hasta 50 entradas")
        _, text = self.entry(data.get("raw", ""))
        self.api.private_directory(self.directory)
        path = self.directory / (ident + ".data")
        self.api.atomic_bytes(path, content)
        self.state["pins"][ident] = {"text": text[:512], "image": "[[ binary data" in text}
        self.save()
      elif action == "clipboard-unpin" or (action == "clipboard-delete" and data.get("pin")):
        ident = self.pin_id(data.get("pin"))
        (self.directory / (ident + ".data")).unlink(missing_ok=True)
        self.state["pins"].pop(ident)
        self.save()
      elif action == "clipboard-copy":
        subprocess.run(["wl-copy"], input=self.decode(data), timeout=5, check=True)
        return True
      elif action == "clipboard-delete":
        raw = data.get("raw", "")
        self.entry(raw)
        self.api.command(["cliphist", "delete"], input_text=raw)
      elif action == "clipboard-clear":
        self.api.command(["cliphist", "wipe"])
      elif action == "clipboard-thumbnail":
        self.api.private_directory(self.directory)
        content = self.decode(data)
        ident = hashlib.sha256(content).hexdigest()
        cache = self.directory / "thumbnails"
        self.api.private_directory(cache)
        path = cache / (ident + ".png")
        if not path.exists():
          if not shutil.which("magick"):
            return True
          coder = "png" if content.startswith(b"\x89PNG\r\n\x1a\n") else "jpeg" if content.startswith(b"\xff\xd8\xff") else "gif" if content[:6] in {b"GIF87a", b"GIF89a"} else "webp" if content[:4] == b"RIFF" and content[8:12] == b"WEBP" else "bmp" if content.startswith(b"BM") else ""
          if not coder:
            return True
          argv = ["magick", "-limit", "thread", "1", "-limit", "memory", "256MiB", "-limit", "map", "256MiB", "-limit", "disk", "0",
            "-limit", "width", "16384", "-limit", "height", "16384", "-limit", "time", "5", coder + ":-[0]", "-thumbnail", "192x128>", "png:-"]
          thumbnail = self.api.bounded_process(argv, content=content, timeout=8, limit=1024 * 1024)
          self.api.atomic_bytes(path, thumbnail)
          for old in sorted(cache.glob("*.png"), key=lambda item: item.stat().st_mtime, reverse=True)[16:]:
            old.unlink(missing_ok=True)
        self.s.emit("clipboard-thumbnail", {"id": data.get("id"), "url": path.as_uri()})
        return True
      self.refresh()
      return True
