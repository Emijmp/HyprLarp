"""Managed hyprsunset instance, applied only on changes or schedule boundaries."""

import datetime as dt
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import threading


def scheduled_active(settings, now=None):
  if not settings.get("nightLightSchedule"):
    return settings.get("nightLightEnabled", False)
  now = now or dt.datetime.now()
  minute = now.hour * 60 + now.minute
  def minutes(value):
    hour, minute = map(int, value.split(":"))
    return hour * 60 + minute
  start, end = minutes(settings["nightLightStart"]), minutes(settings["nightLightEnd"])
  return start <= minute < end if start < end else minute >= start or minute < end if start > end else True


class NightLight:
  def __init__(self, service, api):
    self.s, self.api = service, api
    self.process = None
    self.lock = threading.RLock()
    self.applied = None
    self.last_request = None
    self.closing = False

  def ipc(self, request):
    runtime = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"))
    signature = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE", "")
    path = runtime / "hypr" / signature / ".hyprsunset.sock"
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
      client.settimeout(0.4)
      client.connect(str(path))
      client.sendall(request.encode())
      return client.recv(2048).decode(errors="replace").strip()

  def emit(self, error=""):
    alive = self.process is not None and self.process.poll() is None
    self.s.emit_changed("night-light", {"available": bool(shutil.which("hyprsunset")),
      "active": alive, "temperature": self.applied if alive else None, "error": error,
      "preview": self.s.preview})

  def sync(self, force=False):
    with self.lock:
      if self.s.stopping.is_set():
        return
      desired = scheduled_active(self.s.store.settings)
      temperature = self.s.store.settings["nightLightTemperature"]
      request = (desired, temperature)
      if self.s.preview or self.s.settings_only:
        self.emit()
        return
      if request == self.last_request and not force:
        return
      self.last_request = request
      try:
        if not desired:
          self.close()
        elif self.process and self.process.poll() is None:
          if self.ipc("temperature " + str(temperature)) != "ok":
            raise RuntimeError("Hyprsunset no aceptó la temperatura")
          self.applied = temperature
        else:
          if not shutil.which("hyprsunset"):
            raise RuntimeError("Instala hyprsunset para activar el modo nocturno")
          try:
            self.ipc("temperature")
          except OSError:
            pass
          else:
            raise RuntimeError("Hay otra instancia de hyprsunset activa. Ciérrala para gestionarlo desde HyprLarp.")
          configuration = self.s.store.directory / "nightlight-config" / "hypr"
          configuration.mkdir(parents=True, exist_ok=True)
          (configuration / "hyprsunset.conf").write_text("")
          environment = {**os.environ, "XDG_CONFIG_HOME": str(configuration.parent)}
          with (self.s.store.directory / "nightlight.log").open("w") as log:
            self.process = subprocess.Popen([sys.executable, str(Path(__file__).with_name("night_child.py")), str(os.getpid()), str(temperature)],
              env=environment, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
          for _ in range(15):
            if self.process.poll() is not None:
              raise RuntimeError("Hyprsunset no pudo aplicar el filtro. Revisa nightlight.log.")
            try:
              if self.ipc("temperature"):
                self.applied = temperature
                break
            except OSError:
              self.s.stopping.wait(0.1)
          else:
            self.close()
            raise RuntimeError("El filtro no respondió a tiempo")
        if desired and self.process:
          process = self.process
          if getattr(self, "watched", None) is not process:
            self.watched = process
            threading.Thread(target=self.watch, args=(process,), daemon=True).start()
        self.emit()
      except (OSError, RuntimeError) as error:
        self.emit(str(error))

  def watch(self, process):
    process.wait()
    with self.lock:
      if self.process is process and not self.closing:
        self.applied = None
        self.last_request = None
        self.emit("El filtro se detuvo. Puedes reintentarlo desde Modo nocturno.")

  def close(self):
    with self.lock:
      self.closing = True
      if self.process and self.process.poll() is None:
        self.process.terminate()
        try:
          self.process.wait(timeout=2)
        except subprocess.TimeoutExpired:
          self.process.kill()
          self.process.wait(timeout=2)
      self.process = None
      self.applied = None
      self.closing = False
