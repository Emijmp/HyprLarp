#!/usr/bin/env python3
"""Bound clipboard input in anonymous memory, then replace this process with cliphist."""

import os
import select
import sys
import time

try:
  from .child import bind_parent
except ImportError:
  from child import bind_parent

LIMIT = 16 * 1024 * 1024


def bounded_input(source, limit=LIMIT, timeout=8):
  descriptor = os.memfd_create("hyprlarp-clipboard", os.MFD_CLOEXEC)
  total, oversized = 0, False
  deadline = time.monotonic() + timeout
  try:
    while True:
      remaining = deadline - time.monotonic()
      if remaining <= 0 or not select.select([source], [], [], remaining)[0]:
        os.close(descriptor)
        return None
      chunk = os.read(source, 65536)
      if not chunk:
        break
      total += len(chunk)
      if total > limit:
        oversized = True
      if not oversized:
        offset = 0
        while offset < len(chunk):
          offset += os.write(descriptor, chunk[offset:])
    if oversized:
      os.close(descriptor)
      return None
    os.lseek(descriptor, 0, os.SEEK_SET)
    return descriptor
  except BaseException:
    os.close(descriptor)
    raise


if __name__ == "__main__":
  bind_parent(os.getppid())
  descriptor = bounded_input(sys.stdin.fileno())
  if descriptor is None:
    raise SystemExit(0)
  os.dup2(descriptor, sys.stdin.fileno())
  os.close(descriptor)
  os.execvp("cliphist", ["cliphist", "store"])
