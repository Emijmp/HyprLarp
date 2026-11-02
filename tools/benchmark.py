#!/usr/bin/env python3
"""Measure an isolated preview or attach read-only to a running native shell."""

import argparse
from collections import Counter
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
TICKS = os.sysconf("SC_CLK_TCK")
PAGE = os.sysconf("SC_PAGE_SIZE")


def process_tree(root_pid):
  entries = {}
  for entry in Path("/proc").iterdir():
    if not entry.name.isdigit():
      continue
    try:
      tail = (entry / "stat").read_text().rsplit(")", 1)[1].split()
      entries[int(entry.name)] = {"parent": int(tail[1]),
        "ticks": sum(int(tail[index]) for index in (11, 12, 13, 14)),
        "rss": int(tail[21]) * PAGE}
    except (OSError, ValueError, IndexError):
      continue
  selected = {root_pid}
  while True:
    children = {pid for pid, data in entries.items() if data["parent"] in selected}
    if not children - selected:
      break
    selected.update(children)
  return {pid: entries[pid] for pid in selected if pid in entries}


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


def sample(pid, seconds, mode, panel="", profile=None):
  before = process_tree(pid)
  if pid not in before:
    raise RuntimeError("El proceso ya no está disponible")
  before_gpu = gpu_engines(before)
  started = time.monotonic()
  peak_rss = sum(value["rss"] for value in before.values())
  while time.monotonic() - started < seconds:
    time.sleep(min(0.5, max(0, seconds - (time.monotonic() - started))))
    current = process_tree(pid)
    if pid not in current:
      raise RuntimeError("El shell terminó durante la medición")
    peak_rss = max(peak_rss, sum(value["rss"] for value in current.values()))
  after = process_tree(pid)
  finished = time.monotonic()
  elapsed = finished - started
  cpu_ticks = sum(data["ticks"] - before.get(child, {}).get("ticks", 0) for child, data in after.items())
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
    "gpu_engine_percent": {key: round(value, 2) for key, value in utilization.items()} or None,
    "gpu_note": "Contadores DRM por motor; suma de clientes, no ocupación global de la GPU" if utilization else "El controlador o los permisos no exponen contadores DRM por proceso"}
  if profile is not None:
    events = [json.loads(line) for line in profile.read_text().splitlines()] if profile.exists() else []
    commands = Counter(event["command"] for event in events if started <= event["time"] <= finished)
    result.update(external_commands=sum(commands.values()), commands_by_program=dict(commands))
  return result


def measure(seconds, panel):
  with tempfile.TemporaryDirectory(prefix="hyprlarp-bench-") as directory:
    temporary = Path(directory)
    profile = temporary / "commands.jsonl"
    environment = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "QT_QUICK_BACKEND": "software",
      "XDG_RUNTIME_DIR": directory, "HYPRLARP_STATE_DIR": str(temporary / "settings"),
      "HYPRLARP_START_PANEL": panel, "HYPRLARP_COMMAND_PROFILE": str(profile)}
    for name in ("WAYLAND_DISPLAY", "HYPRLARP_CAPTURE", "HYPRLARP_SMOKE_TEST", "HYPRLARP_SETTINGS_CAPTURE"):
      environment.pop(name, None)
    with (temporary / "quickshell.log").open("w+") as log:
      process = subprocess.Popen([str(ROOT / "bin/hyprlarp"), "preview"], env=environment, stdout=log, stderr=subprocess.STDOUT)
      try:
        time.sleep(3)
        if process.poll() is not None:
          log.seek(0)
          raise RuntimeError(log.read())
        return sample(process.pid, seconds, "Qt offscreen / software; preview read-only", panel, profile)
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
  parser.add_argument("--output", type=Path)
  arguments = parser.parse_args()
  if not 1 <= arguments.seconds <= 3600:
    parser.error("La muestra debe durar entre 1 y 3600 segundos")
  result = sample(arguments.pid, arguments.seconds, "Native session; read-only attachment", arguments.panel) if arguments.pid else measure(arguments.seconds, arguments.panel)
  rendered = json.dumps(result, indent=2) + "\n"
  print(rendered)
  if arguments.output:
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(rendered)


if __name__ == "__main__":
  main()
