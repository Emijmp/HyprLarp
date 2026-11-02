"""Passive libudev listener. No polling or resident helper process."""

import ctypes
import os
import select
import threading


class UdevEvents:
  def __init__(self, subsystem, callback):
    self.subsystem = subsystem.encode()
    self.callback = callback
    self.thread = None
    self.stop_write = None
    self.started = False

  def start(self):
    if self.started:
      return
    self.started = True
    read, self.stop_write = os.pipe()
    self.thread = threading.Thread(target=self.run, args=(read,), daemon=True)
    self.thread.start()

  def stop(self):
    self.started = False
    if self.stop_write is not None:
      try:
        os.write(self.stop_write, b"x")
        os.close(self.stop_write)
      except OSError:
        pass
      self.stop_write = None
    if self.thread:
      self.thread.join(timeout=1)
      self.thread = None

  def run(self, stop_read):
    library, context, monitor = None, None, None
    try:
      library = ctypes.CDLL("libudev.so.1")
      signatures = {
        "udev_new": ([], ctypes.c_void_p), "udev_unref": ([ctypes.c_void_p], ctypes.c_void_p),
        "udev_monitor_new_from_netlink": ([ctypes.c_void_p, ctypes.c_char_p], ctypes.c_void_p),
        "udev_monitor_unref": ([ctypes.c_void_p], ctypes.c_void_p),
        "udev_monitor_filter_add_match_subsystem_devtype": ([ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p], ctypes.c_int),
        "udev_monitor_enable_receiving": ([ctypes.c_void_p], ctypes.c_int),
        "udev_monitor_get_fd": ([ctypes.c_void_p], ctypes.c_int),
        "udev_monitor_receive_device": ([ctypes.c_void_p], ctypes.c_void_p),
        "udev_device_unref": ([ctypes.c_void_p], ctypes.c_void_p)}
      for name, (arguments, result) in signatures.items():
        getattr(library, name).argtypes = arguments
        getattr(library, name).restype = result
      context = library.udev_new()
      if not context:
        return
      monitor = library.udev_monitor_new_from_netlink(context, b"udev")
      if not monitor or library.udev_monitor_filter_add_match_subsystem_devtype(monitor, self.subsystem, None) < 0 or library.udev_monitor_enable_receiving(monitor) < 0:
        return
      fd = library.udev_monitor_get_fd(monitor)
      if fd < 0:
        return
      self.callback()
      while True:
        ready, _, _ = select.select([fd, stop_read], [], [])
        if stop_read in ready:
          return
        device = library.udev_monitor_receive_device(monitor)
        if device:
          library.udev_device_unref(device)
          self.callback()
    except (OSError, ValueError):
      pass
    finally:
      if library and monitor:
        library.udev_monitor_unref(monitor)
      if library and context:
        library.udev_unref(context)
      os.close(stop_read)
