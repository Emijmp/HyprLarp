"""Battery values from sysfs. Missing telemetry stays unknown."""

from pathlib import Path
import math


def battery_state(base=Path("/sys/class/power_supply")):
  batteries, external = [], []
  for device in sorted(base.glob("*")):
    def text(name, fallback=None):
      try:
        return (device / name).read_text().strip() or fallback
      except OSError:
        return fallback

    def number(name):
      try:
        result = float(text(name))
        return result if math.isfinite(result) else None
      except (TypeError, ValueError):
        return None

    kind = text("type")
    if kind in {"Mains", "USB", "USB_C", "USB_PD", "USB_DCP"}:
      if number("online") is not None:
        external.append(number("online") == 1)
      continue
    if kind != "Battery" or text("present") == "0":
      continue
    voltage = number("voltage_now")
    design_voltage = number("voltage_min_design") or voltage
    energy = {name: number("energy_" + name) for name in ("now", "full", "full_design")}
    charge = {name: number("charge_" + name) for name in ("now", "full", "full_design")}
    capacity_estimated = False
    for key in energy:
      if energy[key] is None and charge[key] is not None and design_voltage:
        energy[key] = charge[key] * (voltage if key == "now" and voltage else design_voltage) / 1_000_000
        capacity_estimated = True
    full, design, now = energy["full"], energy["full_design"], energy["now"]
    health = 100 * full / design if full is not None and design and design > 0 else None
    if health is None and charge["full"] is not None and charge["full_design"] and charge["full_design"] > 0:
      health = 100 * charge["full"] / charge["full_design"]
    percent = number("capacity")
    if percent is None and now is not None and full and full > 0:
      percent = 100 * now / full
    power = number("power_now")
    if power is None and number("current_now") is not None and voltage is not None:
      power = abs(number("current_now") * voltage) / 1_000_000
    watts = abs(power) / 1_000_000 if power is not None else None
    status = text("status", "Unknown")
    empty, remaining = number("time_to_empty_now"), number("time_to_full_now")
    estimated = False
    if status == "Discharging" and not empty and now is not None and watts:
      empty, estimated = now / 1_000_000 / watts * 3600, True
    if status == "Charging" and not remaining and full is not None and now is not None and watts:
      remaining, estimated = max(0, full - now) / 1_000_000 / watts * 3600, True
    cycles = number("cycle_count")
    temp = number("temp")
    batteries.append({"name": device.name, "status": status,
      "percent": round(max(0, min(100, percent))) if percent is not None else None,
      "health": round(health, 1) if health is not None else None,
      "degradation": round(max(0, 100 - health), 1) if health is not None else None,
      "watts": round(watts, 2) if watts is not None else None,
      "energyNow": round(now / 1_000_000, 2) if now is not None else None,
      "energyFull": round(full / 1_000_000, 2) if full is not None else None,
      "energyDesign": round(design / 1_000_000, 2) if design is not None else None,
      "capacityEstimated": capacity_estimated,
      "voltage": round(voltage / 1_000_000, 2) if voltage is not None else None,
      "cycles": int(cycles) if cycles is not None and cycles >= 0 else None,
      "temperature": round(temp / 10, 1) if temp is not None else None,
      "manufacturer": text("manufacturer", ""), "model": text("model_name", ""),
      "technology": text("technology", ""), "serial": text("serial_number", ""),
      "timeToEmpty": int(empty) if empty and empty > 0 else None,
      "timeToFull": int(remaining) if remaining and remaining > 0 else None,
      "timeEstimated": estimated,
      "chargeStart": number("charge_control_start_threshold"),
      "chargeEnd": number("charge_control_end_threshold")})
  known = [battery for battery in batteries if battery["percent"] is not None]
  weighted = known and all(battery["energyFull"] and battery["energyFull"] > 0 for battery in known)
  percent = (sum(b["percent"] * b["energyFull"] for b in known) / sum(b["energyFull"] for b in known)
    if weighted else sum(b["percent"] for b in known) / len(known) if known else None)
  return {"available": bool(batteries), "batteries": batteries,
    "percent": round(percent) if percent is not None else None,
    "charging": any(b["status"] in {"Charging", "Full"} for b in batteries),
    "externalPower": any(external) if external else None}
