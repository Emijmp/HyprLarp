"""Validated window spacing, persisted as data and applied without polling."""

import copy
import threading

KEYS = {"windowGapsEnabled", "windowGapsIn", "windowGapsOut"}
HEADER = "# HyprLarp window gaps; generated from settings\n"


def values(settings):
  return {key: copy.deepcopy(settings[key]) for key in KEYS}


def render(settings):
  return HEADER + "enabled=" + str(int(settings["windowGapsEnabled"])) + "\ninner=" + str(settings["windowGapsIn"]) + "\n" \
    + "".join(edge + "=" + str(settings["windowGapsOut"][edge]) + "\n" for edge in ("top", "right", "bottom", "left"))


def expression(settings):
  outer = settings["windowGapsOut"]
  return "hl.config({ general = { gaps_in = " + str(settings["windowGapsIn"]) + ", gaps_out = { " \
    + ", ".join(edge + " = " + str(outer[edge]) for edge in ("top", "right", "bottom", "left")) + " } } })"


class WindowGaps:
  def __init__(self, service, api):
    self.s, self.api = service, api
    self.path = service.store.directory / "window-gaps.conf"
    self.lock = threading.Lock()
    self.was_enabled = False

  def sync(self, native=True):
    with self.lock:
      with self.s.store.lock:
        settings = values(self.s.store.settings)
      enabled = settings["windowGapsEnabled"]
      try:
        try:
          previous = self.api.read_regular(self.path, 1024)
        except FileNotFoundError:
          previous = b""
        self.was_enabled = self.was_enabled or b"\nenabled=1\n" in previous
        content = render(settings).encode("utf-8")
        if content != previous:
          self.api.atomic_bytes(self.path, content)
        applied = False
        if native and not self.s.preview:
          if enabled:
            self.was_enabled = True
            self.api.command(["hyprctl", "eval", expression(settings)], timeout=3)
            applied = True
          elif self.was_enabled:
            self.api.command(["hyprctl", "reload"], timeout=3)
            self.was_enabled = False
            applied = True
        self.s.emit("window-gaps", {"enabled": enabled, "applied": applied, "error": "", "values": settings})
        return True
      except (OSError, ValueError, RuntimeError) as error:
        self.s.emit("window-gaps", {"enabled": enabled, "applied": False, "error": str(error)[:350], "values": settings})
        return False
