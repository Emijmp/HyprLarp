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
      loaded = json.loads((self.directory / "index.json").read_text())
      if isinstance(loaded, dict) and isinstance(loaded.get("pins"), dict) and isinstance(loaded.get("seen"), dict):
        self.state = loaded
    except (OSError, ValueError):
      pass
    self.state["pins"] = {key: value for key, value in self.state["pins"].items()
      if re.fullmatch(r"[a-f0-9]{64}", key) and isinstance(value, dict) and isinstance(value.get("text"), str)}
    self.state["seen"] = {key: value for key, value in self.state["seen"].items()
      if key.isdecimal() and isinstance(value, (int, float))}

  def save(self):
    self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
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
      ident = self.pin_id(data["pin"])
      content = (self.directory / (ident + ".data")).read_bytes()
    else:
      raw = data.get("raw", "")
      self.entry(raw)
      result = subprocess.run(["cliphist", "decode"], input=raw.encode(), capture_output=True, timeout=5, check=True)
      content = result.stdout
    if len(content) > self.LIMIT:
      raise ValueError("La entrada supera 16 MiB")
    return content

  def refresh(self, *, expire=False):
    with self.lock:
      lines = self.api.optional(["cliphist", "list"]).splitlines()[:5000] if self.s.store.settings["clipboardEnabled"] else []
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
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        path = self.directory / (ident + ".data")
        path.write_bytes(content)
        path.chmod(0o600)
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
        content = self.decode(data)
        ident = hashlib.sha256(content).hexdigest()
        cache = self.directory / "thumbnails"
        cache.mkdir(parents=True, exist_ok=True, mode=0o700)
        path = cache / (ident + ".png")
        if not path.exists():
          if not shutil.which("magick"):
            return True
          subprocess.run(["magick", "-", "-thumbnail", "192x128>", "png:" + str(path)],
            input=content, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True, timeout=8)
          path.chmod(0o600)
          for old in sorted(cache.glob("*.png"), key=lambda item: item.stat().st_mtime, reverse=True)[16:]:
            old.unlink(missing_ok=True)
        self.s.emit("clipboard-thumbnail", {"id": data.get("id"), "url": path.as_uri()})
        return True
      self.refresh()
      return True
