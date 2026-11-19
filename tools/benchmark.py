#!/usr/bin/env python3
"""Measure an isolated preview or attach read-only to a running native shell."""

import argparse
from collections import Counter
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
TICKS = os.sysconf("SC_CLK_TCK")
PAGE = os.sysconf("SC_PAGE_SIZE")


def process_tree(root_pid):
  # Read only the measured tree, including children spawned by worker threads.
  # Scanning all of /proc every sample needlessly measures unrelated processes.
  entries = {}
  pending = [root_pid]
  while pending:
    pid = pending.pop()
    if pid in entries:
      continue
    entry = Path("/proc") / str(pid)
    try:
      tail = (entry / "stat").read_text().rsplit(")", 1)[1].split()
      entries[pid] = {"parent": int(tail[1]), "start": int(tail[19]),
        "ticks": sum(int(tail[index]) for index in (11, 12, 13, 14)),
        "rss": int(tail[21]) * PAGE, "threads": int(tail[17])}
      for task in (entry / "task").iterdir():
        try:
          pending.extend(int(child) for child in (task / "children").read_text().split())
        except (OSError, ValueError):
          continue
    except (OSError, ValueError, IndexError):
      continue
  return entries


def pss_bytes(processes):
  total = 0
  for pid in processes:
    try:
      lines = (Path("/proc") / str(pid) / "smaps_rollup").read_text().splitlines()
      total += next(int(line.split()[1]) * 1024 for line in lines if line.startswith("Pss:"))
    except (OSError, StopIteration, ValueError):
      return None
  return total


def gpu_engines(processes):
  # Linux DRM counters are per client. Duplicated file descriptors share counters.
  clients = {}
  for pid in processes:
    try:
      paths = list((Path("/proc") / str(pid) / "fdinfo").iterdir())
    except OSError:
      continue
    for path in paths:
      try:
        fields = dict(line.split(":", 1) for line in path.read_text().splitlines() if ":" in line)
        client = fields.get("drm-client-id")
        if client is None:
          continue
        device = fields.get("drm-pdev", fields.get("drm-driver", "")).strip()
        engines = {}
        for key, value in fields.items():
          words = value.split()
          if key.startswith("drm-engine-") and len(words) == 2 and words[1] == "ns":
            engines[key.removeprefix("drm-engine-")] = int(words[0])
        clients[(device, client.strip())] = engines
      except (OSError, ValueError):
        continue
  return {f"{device}:{client}:{engine}": value for (device, client), engines in clients.items() for engine, value in engines.items()}


def sample(pid, seconds, mode, panel="", profile=None, interval=1):
  before = process_tree(pid)
  if pid not in before:
    raise RuntimeError("El proceso ya no está disponible")
  before_gpu = gpu_engines(before)
  started = time.monotonic()
  peak_rss = sum(value["rss"] for value in before.values())
  while time.monotonic() - started < seconds:
    time.sleep(min(interval, max(0, seconds - (time.monotonic() - started))))
    current = process_tree(pid)
    if pid not in current or current[pid]["start"] != before[pid]["start"]:
      raise RuntimeError("El shell terminó durante la medición")
    peak_rss = max(peak_rss, sum(value["rss"] for value in current.values()))
  after = process_tree(pid)
  if pid not in after or after[pid]["start"] != before[pid]["start"]:
    raise RuntimeError("El proceso medido terminó o cambió de identidad")
  finished = time.monotonic()
  elapsed = finished - started
  cpu_ticks = sum(data["ticks"] for data in after.values()) - sum(data["ticks"] for data in before.values())
  pss = pss_bytes(after)
  after_gpu = gpu_engines(after)
  utilization = Counter()
  for key, value in after_gpu.items():
    if key in before_gpu:
      engine = key.rsplit(":", 1)[-1]
      utilization[engine] += max(0, value - before_gpu[key]) / 1e9 / elapsed * 100
  result = {"mode": mode, "panel": panel or "closed", "pid": pid,
    "seconds": round(elapsed, 2), "cpu_percent_one_core": round(max(0, cpu_ticks) / TICKS / elapsed * 100, 2),
    "rss_mib_end": round(sum(value["rss"] for value in after.values()) / 1024**2, 2),
    "rss_mib_peak_sampled": round(peak_rss / 1024**2, 2),
    "pss_mib_end": round(pss / 1024**2, 2) if pss is not None else None,
    "processes_end": len(after), "threads_end": sum(data["threads"] for data in after.values()),
    "sample_interval_seconds": interval, "cpu_tick_ms": round(1000 / TICKS, 3),
    "platform": platform.platform(),
    "gpu_engine_percent": {key: round(value, 2) for key, value in utilization.items()} or None,
    "gpu_note": "Contadores DRM por motor; suma de clientes, no ocupación global de la GPU" if utilization else "El controlador o los permisos no exponen contadores DRM por proceso"}
  if profile is not None:
    events = [json.loads(line) for line in profile.read_text().splitlines()] if profile.exists() else []
    commands = Counter(event["command"] for event in events if started <= event["time"] <= finished)
    result.update(external_commands=sum(commands.values()), commands_by_program=dict(commands))
  return result


def measure(seconds, panel, *, native=False, root=ROOT, interval=1):
  with tempfile.TemporaryDirectory(prefix="hyprlarp-bench-") as directory:
    temporary = Path(directory)
    profile = temporary / "commands.jsonl"
    environment = {**os.environ,
      "XDG_RUNTIME_DIR": directory, "HYPRLARP_STATE_DIR": str(temporary / "settings"),
      "HYPRLARP_START_PANEL": "", "HYPRLARP_COMMAND_PROFILE": str(profile), "HYPRLARP_BENCHMARK": "1"}
    if native:
      if not os.environ.get("WAYLAND_DISPLAY") or not os.environ.get("XDG_RUNTIME_DIR"):
        raise RuntimeError("--native necesita una sesión Wayland abierta")
      environment["XDG_RUNTIME_DIR"] = os.environ["XDG_RUNTIME_DIR"]
      environment["QT_QPA_PLATFORM"] = "wayland"
      environment.pop("QT_QUICK_BACKEND", None)
    else:
      environment.update(QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software")
      environment.pop("WAYLAND_DISPLAY", None)
    for name in ("HYPRLARP_CAPTURE", "HYPRLARP_SMOKE_TEST", "HYPRLARP_SETTINGS_CAPTURE", "HYPRLARP_SETTINGS_ONLY"):
      environment.pop(name, None)
    with (temporary / "quickshell.log").open("w+") as log:
      started_ms = time.time() * 1000
      process = subprocess.Popen([str(root / "bin/hyprlarp"), "preview"], env=environment, stdout=log, stderr=subprocess.STDOUT)
      try:
        time.sleep(3)
        if process.poll() is not None:
          log.seek(0)
          raise RuntimeError(log.read())
        if panel:
          binary = os.environ.get("HYPRLARP_QUICKSHELL", "quickshell")
          opened = subprocess.run([binary, "--path", str(root / "preview.qml"), "ipc", "call", "shell", "toggle", panel],
            env=environment, capture_output=True, text=True, timeout=5)
          if opened.returncode:
            raise RuntimeError(opened.stderr.strip() or "No se pudo abrir el panel de prueba")
          time.sleep(0.25)
        result = sample(process.pid, seconds, "Wayland / native renderer; preview read-only" if native else "Qt offscreen / software; preview read-only", panel, profile, interval)
        log.flush()
        log.seek(0)
        content = log.read()
        ready = re.search(r"BENCHMARK_READY (\d+)", content)
        loaded = re.search(r"BENCHMARK_PANEL [a-z-]+ (\d+) (\d+)", content)
        result["backend_ready_ms"] = round(int(ready[1]) - started_ms, 1) if ready else None
        result["panel_load_ms"] = int(loaded[2]) - int(loaded[1]) if loaded else None
        result["timing_note"] = "Inicialización del backend y carga de componentes; no es tiempo hasta el primer fotograma"
        if "Failed to load" in content or "TypeError:" in content or "ReferenceError:" in content:
          raise RuntimeError(content[-4000:])
        return result
      finally:
        process.terminate()
        try:
          process.wait(timeout=5)
        except subprocess.TimeoutExpired:
          process.kill()
          process.wait()


def main():
  parser = argparse.ArgumentParser()
  parser.add_argument("--seconds", type=float, default=12)
  parser.add_argument("--panel", default="", choices=["", "control", "resources", "launcher", "audio"])
  parser.add_argument("--pid", type=int, help="Medir una instancia nativa ya abierta, sin modificarla")
  parser.add_argument("--native", action="store_true", help="Abrir una vista previa aislada con Wayland y renderizador nativo")
  parser.add_argument("--root", type=Path, default=ROOT, help="Checkout que se quiere medir")
  parser.add_argument("--interval", type=float, default=1, help="Intervalo de muestreo, de 0.2 a 10 segundos")
  parser.add_argument("--compare", type=Path, help="Añadir diferencias respecto de un informe anterior del mismo modo")
  parser.add_argument("--output", type=Path)
  arguments = parser.parse_args()
  if not 1 <= arguments.seconds <= 3600:
    parser.error("La muestra debe durar entre 1 y 3600 segundos")
  if not 0.2 <= arguments.interval <= 10:
    parser.error("El intervalo debe estar entre 0.2 y 10 segundos")
  if arguments.pid and arguments.native:
    parser.error("--pid y --native son modos diferentes")
  previous = None
  if arguments.compare:
    try:
      previous = json.loads(arguments.compare.read_text())
      if not isinstance(previous, dict):
        raise ValueError("el informe no es un objeto JSON")
    except (OSError, ValueError) as error:
      parser.error("No se pudo leer el informe de referencia: " + str(error))
  result = sample(arguments.pid, arguments.seconds, "Native session; read-only attachment", arguments.panel, interval=arguments.interval) if arguments.pid else measure(arguments.seconds, arguments.panel, native=arguments.native, root=arguments.root.resolve(), interval=arguments.interval)
  if previous is not None:
    if previous.get("mode") != result["mode"] or previous.get("panel") != result["panel"]:
      parser.error("La comparación requiere el mismo modo y panel")
    result["change_from_previous"] = {key: round(result[key] - previous[key], 3)
      for key in ("cpu_percent_one_core", "rss_mib_end", "pss_mib_end", "backend_ready_ms", "panel_load_ms")
      if isinstance(result.get(key), (int, float)) and isinstance(previous.get(key), (int, float))}
  rendered = json.dumps(result, indent=2) + "\n"
  print(rendered)
  if arguments.output:
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(rendered)


if __name__ == "__main__":
  main()
