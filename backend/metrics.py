"""Demand-driven resource reads and scheduling, without UI or action routing."""

from __future__ import annotations

from pathlib import Path
import shutil
import time
from typing import Any

def brightness_state(base: Path = Path("/sys/class/backlight")) -> dict:
  for device in sorted(base.glob("*")):
    try:
      maximum = int((device / "max_brightness").read_text())
      source = device / "actual_brightness"
      current = int((source if source.exists() else device / "brightness").read_text())
      if maximum > 0:
        return {"brightness": round(100 * current / maximum), "brightnessAvailable": True}
    except (OSError, ValueError):
      continue
  return {"brightness": 0, "brightnessAvailable": False}


def poll_intervals(settings: dict, panel: str, settings_only: bool = False, native_services: bool = False, outputs: list[str] | None = None) -> dict[str, float]:
  """Demand-driven reads with an adjustable rate and no closed-panel polling."""
  if settings_only:
    return {'performance': 2} if panel == 'performance' else {}
  names = [""] if outputs is None else outputs
  modules = set()
  for name in names:
    bar = {**settings, **settings.get("monitorBars", {}).get(name, {})}
    if bar.get("barEnabled", True):
      modules.update(bar["barModules"])
  modules -= set(settings["disabledModules"])
  plan = {}
  if panel == 'performance':
    plan['performance'] = 2
  if "resources" in modules or panel in {"resources", "control"}:
    plan["metrics"] = 2
  if panel in {"control", "brightness"} or "brightness" in modules:
    plan["brightness"] = 2
  if panel == "battery":
    plan["battery"] = 2
  elif panel == "control" or "battery" in modules or settings.get("batteryAlertsEnabled", False):
    plan["battery"] = 30
  if not native_services and ("wifi" in modules or panel in {"wifi", "control"}):
    plan["network"] = 60
  if panel == "clipboard" and settings["clipboardEnabled"]:
    plan["clipboard"] = 2
  if not native_services and panel == "bluetooth":
    plan["bluetooth"] = 6
  if settings.get("clipboardEnabled") and settings.get("clipboardRetentionHours", 0):
    plan["clipboard-expiry"] = 60
  # Keep cleanup and the explicit performance panel predictable. The profile
  # only adjusts recurring hardware/system reads while their UI is relevant.
  factor = {"efficient": 2.5, "balanced": 1.0, "responsive": 0.75}.get(settings.get("performanceMode", "balanced"), 1.0)
  for name in plan:
    if name not in {"performance", "clipboard-expiry"}:
      plan[name] = max(0.5, plan[name] * factor)
  return plan


class Metrics:
  def __init__(self):
    self.previous_cpu: tuple[int, int] | None = None
    self.previous_network: tuple[float, int, int] | None = None
    self.disk_sample = {}
    self.disk_at = 0
    self.thermal_path = None
    self.thermal_at = 0

  def read(self, detailed=True) -> dict:
    data: dict[str, Any] = {"cpu": None, "memory": 0, "memoryUsed": 0, "memoryTotal": 0,
                "disk": 0, "temperature": None, "upload": 0, "download": 0}
    try:
      with Path("/proc/stat").open() as cpu:
        times = [int(x) for x in cpu.readline().split()[1:9]]
      total, idle = sum(times), times[3] + times[4]
      if self.previous_cpu:
        delta = total - self.previous_cpu[0]
        data["cpu"] = round(100 * (1 - (idle - self.previous_cpu[1]) / max(1, delta)), 1)
      self.previous_cpu = (total, idle)
      memory = {line.split(":")[0]: int(line.split()[1]) for line in Path("/proc/meminfo").read_text().splitlines()}
      data["memoryTotal"] = round(memory["MemTotal"] / 1024**2, 1)
      data["memoryUsed"] = round((memory["MemTotal"] - memory["MemAvailable"]) / 1024**2, 1)
      data["memory"] = round(100 * (1 - memory["MemAvailable"] / memory["MemTotal"]), 1)
      if not detailed:
        return {key: data[key] for key in ("cpu", "memory", "memoryUsed", "memoryTotal")}
      now = time.monotonic()
      if not self.disk_sample or now - self.disk_at >= 10:
        disk = shutil.disk_usage(Path.home())
        self.disk_sample = {"disk": round(100 * disk.used / disk.total, 1), "diskFree": round(disk.free / 1024**3, 1)}
        self.disk_at = now
      data.update(self.disk_sample)
      data["uptime"] = int(float(Path("/proc/uptime").read_text().split()[0]))
      received, sent = 0, 0
      for line in Path("/proc/net/dev").read_text().splitlines()[2:]:
        interface, values = line.split(":", 1)
        if interface.strip() == "lo":
          continue
        values = values.split()
        received += int(values[0])
        sent += int(values[8])
      now = time.monotonic()
      if self.previous_network:
        elapsed = max(0.01, now - self.previous_network[0])
        data["download"] = max(0, round((received - self.previous_network[1]) / elapsed / 1024))
        data["upload"] = max(0, round((sent - self.previous_network[2]) / elapsed / 1024))
      self.previous_network = (now, received, sent)
      if now - self.thermal_at >= 60 or self.thermal_at == 0:
        self.thermal_at = now
        self.thermal_path = next((zone / "temp" for zone in sorted(Path("/sys/class/thermal").glob("thermal_zone*"))
          if (zone / "type").read_text().strip() in {"x86_pkg_temp", "cpu-thermal", "k10temp", "acpitz"}), None)
      if self.thermal_path:
        data["temperature"] = round(int(self.thermal_path.read_text()) / 1000)
    except (OSError, ValueError, KeyError, IndexError):
      pass
    return data
