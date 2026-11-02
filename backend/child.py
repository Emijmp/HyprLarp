#!/usr/bin/env python3
"""A fresh child sets its parent-death signal before exec; safe with worker threads."""

import ctypes
import os
import signal
import sys


def bind_parent(parent):
  libc = ctypes.CDLL(None, use_errno=True)
  libc.prctl.argtypes = [ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong]
  libc.prctl.restype = ctypes.c_int
  if parent <= 1 or libc.prctl(1, signal.SIGTERM, 0, 0, 0) != 0 or os.getppid() != parent:
    raise SystemExit(1)


def execute(parent, argv):
  bind_parent(parent)
  os.execvp(argv[0], argv)


if __name__ == "__main__":
  if len(sys.argv) < 3:
    raise SystemExit(2)
  execute(int(sys.argv[1]), sys.argv[2:])
