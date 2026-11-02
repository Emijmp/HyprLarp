"""Bounded local I/O and process work; no shell interpolation."""

import concurrent.futures
import json
import math
import os
from pathlib import Path
import selectors
import signal
import stat
import subprocess
import threading
import time
import sys

JSON_LIMIT = 2 * 1024 * 1024
_process_lock = threading.Lock()
_processes = set()
_closing = False


def stop_processes():
  global _closing
  with _process_lock:
    _closing = True
    for process in list(_processes):
      if process.poll() is None:
        try:
          os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
          pass


def read_regular(path, limit=JSON_LIMIT):
  fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC)
  try:
    metadata = os.fstat(fd)
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > limit:
      raise ValueError("El archivo debe ser regular y respetar el límite de tamaño")
    result = bytearray()
    while len(result) <= limit:
      chunk = os.read(fd, min(65536, limit + 1 - len(result)))
      if not chunk:
        return bytes(result)
      result.extend(chunk)
    raise ValueError("El archivo supera el límite de tamaño")
  finally:
    os.close(fd)


def parse_json(value):
  def invalid(value):
    raise ValueError("Número JSON no válido: " + value)
  if isinstance(value, bytes):
    value = value.decode("utf-8-sig")
  depth, quoted, escaped = 0, False, False
  for character in value:
    if quoted:
      if escaped:
        escaped = False
      elif character == "\\":
        escaped = True
      elif character == '"':
        quoted = False
    elif character == '"':
      quoted = True
    elif character in "[{":
      depth += 1
      if depth > 64:
        raise ValueError("El JSON contiene demasiados niveles anidados")
    elif character in "]}":
      depth -= 1
  try:
    result = json.loads(value, parse_constant=invalid)
  except RecursionError as error:
    raise ValueError("El JSON contiene demasiados niveles anidados") from error
  pending = [iter((result,))]
  while pending:
    try:
      item = next(pending[-1])
    except StopIteration:
      pending.pop()
      continue
    if isinstance(item, str):
      item.encode("utf-8")
    elif isinstance(item, int) and not -(1 << 63) <= item < (1 << 63):
      raise ValueError("El entero JSON está fuera del rango admitido")
    elif isinstance(item, float) and not math.isfinite(item):
      raise ValueError("El número JSON debe ser finito")
    elif isinstance(item, dict):
      for key in item:
        key.encode("utf-8")
      pending.append(iter(item.values()))
    elif isinstance(item, list):
      pending.append(iter(item))
  return result


def read_json(path, limit=JSON_LIMIT):
  return parse_json(read_regular(path, limit))


def idle_processes(expected, base=Path("/proc")):
  for process in base.iterdir():
    if not process.name.isdecimal():
      continue
    try:
      if process.stat().st_uid != os.getuid():
        continue
      args = (process / "cmdline").read_bytes().split(b"\0")
      if args and Path(os.fsdecode(args[0])).name == "hypridle" and b"-c" in args:
        index = args.index(b"-c")
        if index + 1 < len(args) and args[index + 1] == os.fsencode(expected):
          yield int(process.name), args
    except OSError:
      continue


def private_directory(path):
  path = Path(path)
  if path.is_symlink():
    raise ValueError("El directorio privado no puede ser un enlace simbólico")
  path.mkdir(parents=True, exist_ok=True, mode=0o700)
  if path.stat().st_uid != os.getuid():
    raise ValueError("El directorio privado pertenece a otro usuario")
  path.chmod(0o700)
  return path


class BoundedExecutor(concurrent.futures.ThreadPoolExecutor):
  def __init__(self, max_workers=3, pending=12):
    super().__init__(max_workers=max_workers, thread_name_prefix="hyprlarp")
    self.capacity = threading.BoundedSemaphore(max_workers + pending)

  def submit(self, fn, /, *args, **kwargs):
    if not self.capacity.acquire(blocking=False):
      raise RuntimeError("La cola de operaciones está llena; vuelve a intentarlo")
    try:
      future = super().submit(fn, *args, **kwargs)
    except BaseException:
      self.capacity.release()
      raise
    future.add_done_callback(lambda finished: self.capacity.release())
    return future


def bounded_process(argv, *, content=b"", timeout=8, limit=JSON_LIMIT, check=True):
  """Drain both pipes without buffering an unlimited decoder response."""
  wrapped = [sys.executable, str(Path(__file__).with_name("child.py")), str(os.getpid()), *argv]
  with _process_lock:
    if _closing:
      raise RuntimeError("El servicio se está cerrando")
    process = subprocess.Popen(wrapped, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
      env={**os.environ, "LC_ALL": "C"}, start_new_session=True)
    _processes.add(process)
  output, errors, offset = bytearray(), bytearray(), 0
  deadline = time.monotonic() + timeout
  try:
    with selectors.DefaultSelector() as selector:
      for stream, kind in ((process.stdout, "out"), (process.stderr, "err")):
        os.set_blocking(stream.fileno(), False)
        selector.register(stream, selectors.EVENT_READ, kind)
      if content:
        os.set_blocking(process.stdin.fileno(), False)
        selector.register(process.stdin, selectors.EVENT_WRITE, "in")
      else:
        process.stdin.close()
      while selector.get_map():
        remaining = deadline - time.monotonic()
        if remaining <= 0:
          raise RuntimeError(Path(argv[0]).name + " no respondió a tiempo")
        for key, events in selector.select(remaining):
          if key.data == "in":
            try:
              offset += os.write(key.fd, content[offset:offset + 16384])
            except BrokenPipeError:
              offset = len(content)
            if offset == len(content):
              selector.unregister(key.fileobj)
              key.fileobj.close()
            continue
          chunk = os.read(key.fd, 65536)
          if not chunk:
            selector.unregister(key.fileobj)
            continue
          buffer, maximum = (output, limit) if key.data == "out" else (errors, 65536)
          if len(buffer) + len(chunk) > maximum:
            raise ValueError("La salida de " + Path(argv[0]).name + " supera el límite permitido")
          buffer.extend(chunk)
      remaining = deadline - time.monotonic()
      if remaining <= 0:
        raise RuntimeError(Path(argv[0]).name + " no respondió a tiempo")
      process.wait(timeout=remaining)
    if check and process.returncode:
      message = (errors or output).decode("utf-8", errors="replace").strip()[:350]
      raise RuntimeError(message or Path(argv[0]).name + " terminó con error")
    return bytes(output)
  except BaseException as error:
    try:
      os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
      pass
    process.wait()
    if isinstance(error, subprocess.TimeoutExpired):
      raise RuntimeError(Path(argv[0]).name + " no respondió a tiempo") from None
    raise
  finally:
    with _process_lock:
      _processes.discard(process)
    for stream in (process.stdin, process.stdout, process.stderr):
      stream.close()
