"""Bounded circuit breakers for components; settings are never modified."""

import threading
import time

try:
  from .persistence import atomic_json
  from .safety import read_json
  from .diagnostics import redact
except ImportError:
  from persistence import atomic_json
  from safety import read_json
  from diagnostics import redact


class FaultRegistry:
  def __init__(self, directory, allowed, *, clock=time.time):
    self.path = directory / 'module-faults.json'
    self.allowed = set(allowed)
    self.clock = clock
    self.lock = threading.RLock()
    self.entries = {}
    try:
      saved = read_json(self.path, limit=128 * 1024)
      if isinstance(saved, dict):
        for name, item in saved.items():
          if name in self.allowed and isinstance(item, dict) and isinstance(item.get('blocked'), bool):
            events = item.get('events', [])
            if isinstance(events, list) and all(isinstance(stamp, (int, float)) and not isinstance(stamp, bool) and 0 <= stamp <= self.clock() for stamp in events):
              self.entries[name] = {'id': name, 'blocked': item['blocked'], 'events': events[-3:], 'message': redact(str(item.get('message', '')))[:600]}
    except (OSError, ValueError):
      pass

  def snapshot(self):
    with self.lock:
      return [dict(item, events=list(item['events'])) for _, item in sorted(self.entries.items())]

  def blocked(self, name):
    with self.lock:
      return self.entries.get(name, {}).get('blocked', False)

  def save(self):
    try:
      atomic_json(self.path, self.entries)
    except OSError:
      pass

  def report(self, name, message):
    if not isinstance(name, str) or name not in self.allowed or not isinstance(message, str) or len(message) > 4096:
      raise ValueError('Componente o mensaje de fallo inválido')
    with self.lock:
      now = self.clock()
      old = self.entries.get(name, {})
      events = [stamp for stamp in old.get('events', []) if now - 300 <= stamp <= now]
      events = (events + [now])[-3:]
      self.entries[name] = {'id': name, 'events': events,
        'blocked': old.get('blocked', False) or len(events) >= 3, 'message': redact(message)[:600]}
      self.save()

  def reset(self, name):
    if not isinstance(name, str) or name not in self.allowed:
      raise ValueError('Componente desconocido')
    with self.lock:
      self.entries.pop(name, None)
      self.save()
