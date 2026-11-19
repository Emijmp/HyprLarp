"""Private atomic file replacement shared by settings and optional features."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
from typing import Any

def atomic_bytes(destination: Path, value: bytes) -> None:
  destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
  fd, temp = tempfile.mkstemp(prefix=".hyprlarp-", dir=destination.parent)
  try:
    with os.fdopen(fd, "wb") as handle:
      handle.write(value)
    os.replace(temp, destination)
  finally:
    if os.path.exists(temp):
      os.unlink(temp)


def atomic_text(destination: Path, value: str) -> None:
  atomic_bytes(destination, value.encode("utf-8"))


def atomic_json(destination: Path, value: Any) -> None:
  atomic_text(destination, json.dumps(value, ensure_ascii=False, indent=2) + "\n")
