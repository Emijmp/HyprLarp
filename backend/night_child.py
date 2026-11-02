#!/usr/bin/env python3
"""Bind the managed filter's lifetime to the backend, then replace this helper."""

import ctypes
import os
import signal
import sys

if __name__ == "__main__":
  parent = int(sys.argv[1])
  libc = ctypes.CDLL(None, use_errno=True)
  libc.prctl.argtypes = [ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong]
  libc.prctl.restype = ctypes.c_int
  if libc.prctl(1, signal.SIGTERM, 0, 0, 0) != 0 or os.getppid() != parent:
    raise SystemExit(1)
  os.execvp("hyprsunset", ["hyprsunset", "--temperature", sys.argv[2]])
