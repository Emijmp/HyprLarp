"""One warning per severity and discharge cycle, retained across shell restarts."""

import math

try:
  from .persistence import atomic_json
  from .safety import read_json
except ImportError:
  from persistence import atomic_json
  from safety import read_json


class BatteryAlerts:
  def __init__(self, directory):
    self.path = directory / 'battery-alerts.json'
    try:
      saved = read_json(self.path, limit=4096)
      self.notified = set(saved.get('notified', [])) & {'low', 'critical'}
    except (OSError, ValueError, TypeError, AttributeError):
      self.notified = set()

  def update(self, battery, settings):
    if not settings.get('batteryAlertsEnabled', True) or not battery.get('available'):
      return None
    percent = battery.get('percent')
    if isinstance(percent, bool) or not isinstance(percent, (int, float)) or not math.isfinite(percent) or not 0 <= percent <= 100:
      return None
    levels = settings.get('batteryAlertLevels', {'low': 20, 'critical': 10})
    previous = self.notified.copy()
    alert = None
    if battery.get('externalPower') is True or battery.get('charging') or percent >= min(100, levels['low'] + 5):
      self.notified.clear()
    elif any(item.get('status') == 'Discharging' for item in battery.get('batteries', [])):
      severity = 'critical' if percent <= levels['critical'] else 'low' if percent <= levels['low'] else None
      if severity and severity not in self.notified:
        self.notified.add(severity)
        if severity == 'critical':
          self.notified.add('low')
        alert = {'level': severity, 'percent': round(percent)}
    if previous != self.notified:
      try:
        atomic_json(self.path, {'notified': sorted(self.notified)})
      except OSError:
        # The in-memory guard still prevents repeated warnings if storage is full.
        pass
    return alert
