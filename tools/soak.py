#!/usr/bin/env python3
"""Exercise an immutable preview copy for hours without touching the desktop."""

import argparse
from collections import deque
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import signal
import statistics
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.performance import ProcessSampler, package_revision, process_stat
from backend.persistence import atomic_json
from backend.version import VERSION
from tools.deployment import copy_sources, no_symlinks

ERRORS = ("ReferenceError:", "TypeError:", "Binding loop", "Failed to load", "Unable to assign",
  "Traceback (most recent call last)", "First-run regression:")


def summarize(samples, warmup, limit):
  settled = [item for item in samples if item["elapsed"] >= warmup]
  if not settled:
    return {"memory_checked": False, "growth_mib": None, "stable": False}
  window = min(5, max(1, len(settled) // 3))
  first = statistics.median(item["rssMiB"] for item in settled[:window])
  last = statistics.median(item["rssMiB"] for item in settled[-window:])
  return {"memory_checked": len(settled) >= 3, "growth_mib": round(last - first, 2),
    "baseline_rss_mib": first, "final_window_rss_mib": last,
    "peak_rss_mib": max(item["rssMiB"] for item in settled), "stable": last - first <= limit}


def run(output, *, duration=7200, interval=15, warmup=120, max_growth=64, cycle_ms=2000, restart_every=1800):
  output = Path(output).absolute()
  no_symlinks(output)
  if output.exists() and any(output.iterdir()):
    raise ValueError("El directorio de salida debe estar vacío")
  output.mkdir(parents=True, exist_ok=True, mode=0o700)
  output.chmod(0o700)
  app = output / "app"
  app.mkdir()
  copy_sources(app)
  (app / "soak.qml").write_text('//@ pragma UseQApplication\n//@ pragma Env QT_QUICK_CONTROLS_STYLE=Basic\nimport Quickshell\nimport "tools" as Tools\nShellRoot { Tools.Soak {} }\n')
  binary = shutil.which("quickshell") or shutil.which("qs")
  if not binary:
    raise RuntimeError("La prueba prolongada requiere Quickshell")
  started = time.monotonic()
  report = {"type": "hyprlarp-soak", "version": 1, "release": VERSION, "revision": package_revision(app),
    "started": datetime.now(timezone.utc).isoformat(), "requested_seconds": duration,
    "mode": "isolated Qt offscreen/software", "status": "running", "samples": 0,
    "panels_visited": 0, "rounds": 0, "backend_restarts": 0, "errors": [],
    "physical_suspend_tested": False, "physical_hotplug_tested": False, "pam_tested": False}
  samples = deque(maxlen=20000)
  process = None
  interrupted = False
  old_handlers = {}
  def stop(signum, frame):
    nonlocal interrupted
    interrupted = True
  for number in (signal.SIGTERM, signal.SIGINT):
    old_handlers[number] = signal.signal(number, stop)
  try:
    with tempfile.TemporaryDirectory(prefix="hyprlarp-soak-runtime-") as runtime:
      home = output / "home"
      home.mkdir(mode=0o700)
      environment = {key: os.environ[key] for key in ("PATH", "LANG", "LC_ALL", "XDG_DATA_DIRS") if key in os.environ}
      environment.update({"QT_QPA_PLATFORM": "offscreen", "QT_QUICK_BACKEND": "software",
        "XDG_RUNTIME_DIR": runtime, "HYPRLARP_STATE_DIR": str(output / "state"),
        "HYPRLARP_PREVIEW": "1", "HYPRLARP_SOAK_CYCLE_MS": str(cycle_ms),
        "HOME": str(home), "XDG_CONFIG_HOME": str(home / ".config"),
        "XDG_DATA_HOME": str(home / ".local/share"), "XDG_CACHE_HOME": str(home / ".cache")})
      for name in ("WAYLAND_DISPLAY", "DISPLAY", "HYPRLARP_SETTINGS_ONLY", "HYPRLARP_WELCOME_ONLY",
        "HYPRLARP_SMOKE_TEST", "HYPRLARP_CAPTURE", "HYPRLARP_SETTINGS_CAPTURE"):
        environment.pop(name, None)
      with (output / "quickshell.log").open("w") as log, (output / "samples.jsonl").open("w") as trace:
        process = subprocess.Popen([binary, "--path", str(app / "soak.qml"), "--no-color"],
          env=environment, stdout=log, stderr=subprocess.STDOUT)
        sampler, backend, failures, next_restart = None, None, 0, restart_every
        while time.monotonic() - started < duration and not interrupted:
          if process.poll() is not None:
            raise RuntimeError("La interfaz terminó durante la prueba")
          result = subprocess.run([binary, "--path", str(app / "soak.qml"), "ipc", "call", "soak", "health"],
            env=environment, text=True, capture_output=True, timeout=5)
          try:
            health = json.loads(result.stdout.strip().rsplit("\n", 1)[-1])
            if result.returncode or not health.get("connected") or not health.get("ready"):
              raise ValueError("La interfaz todavía no está lista")
          except (ValueError, IndexError):
            failures += 1
            if failures > 3:
              raise RuntimeError("El backend no recuperó su conexión")
            time.sleep(min(1, interval))
            continue
          failures = 0
          if health.get("blocked"):
            raise RuntimeError("Componentes bloqueados: " + ", ".join(health["blocked"]))
          if backend != health["backendPid"]:
            backend = health["backendPid"]
            sampler = ProcessSampler(app, pids={"interface": process.pid, "backend": backend})
          sample = sampler.sample()
          sample["elapsed"] = round(time.monotonic() - started, 2)
          sample["scene"] = health.get("scene", "")
          samples.append(sample)
          trace.write(json.dumps(sample) + "\n")
          trace.flush()
          report.update(samples=len(samples), elapsed_seconds=sample["elapsed"],
            panels_visited=health.get("step", 0), rounds=health.get("rounds", 0),
            memory=summarize(samples, min(warmup, duration / 4), max_growth))
          atomic_json(output / "result.json", report)
          if (output / "quickshell.log").stat().st_size > 16 * 1024 * 1024:
            raise RuntimeError("El registro superó el presupuesto de 16 MiB")
          content = (output / "quickshell.log").read_text(errors="replace")
          errors = [line for line in content.splitlines() if any(marker in line for marker in ERRORS)]
          if errors:
            report["errors"] = errors[-20:]
            raise RuntimeError("La prueba detectó errores de interfaz")
          if restart_every and sample["elapsed"] >= next_restart:
            # The sampled identity and parent must still match immediately
            # before signalling; use pidfd so PID reuse cannot target an app.
            target = sampler.targets["backend"]
            descriptor = os.pidfd_open(backend)
            try:
              current = process_stat(backend)
              if current["start"] != target["start"] or current["parent"] != process.pid:
                raise RuntimeError("Cambió la identidad del backend")
              signal.pidfd_send_signal(descriptor, signal.SIGTERM)
            finally:
              os.close(descriptor)
            report["backend_restarts"] += 1
            next_restart += restart_every
          remaining = duration - (time.monotonic() - started)
          if remaining > 0:
            time.sleep(min(interval, remaining))
        if interrupted:
          report["status"] = "interrupted"
        elif not report.get("memory", {}).get("stable"):
          raise RuntimeError("El crecimiento de memoria superó el límite de la prueba")
        else:
          report["status"] = "passed"
  except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
    report["status"] = "failed"
    report["errors"].append(str(error))
  finally:
    if process is not None and process.poll() is None:
      process.terminate()
      try:
        process.wait(timeout=5)
      except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=3)
    report["elapsed_seconds"] = round(time.monotonic() - started, 2)
    report["finished"] = datetime.now(timezone.utc).isoformat()
    atomic_json(output / "result.json", report)
    for number, handler in old_handlers.items():
      signal.signal(number, handler)
  return report


def main():
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("--output", type=Path, required=True)
  parser.add_argument("--duration", type=float, default=7200)
  parser.add_argument("--interval", type=float, default=15)
  parser.add_argument("--warmup", type=float, default=120)
  parser.add_argument("--max-growth-mib", type=float, default=64)
  parser.add_argument("--cycle-ms", type=int, default=2000)
  parser.add_argument("--restart-every", type=float, default=1800)
  args = parser.parse_args()
  if not (1 <= args.duration <= 86400 and .2 <= args.interval <= 60 and 100 <= args.cycle_ms <= 60000
    and 0 <= args.warmup <= args.duration and 1 <= args.max_growth_mib <= 1024 and 0 <= args.restart_every <= 86400):
    parser.error("Duración, intervalos o presupuesto fuera de rango")
  try:
    result = run(args.output, duration=args.duration, interval=args.interval, warmup=args.warmup,
      max_growth=args.max_growth_mib, cycle_ms=args.cycle_ms, restart_every=args.restart_every)
  except (OSError, ValueError, RuntimeError) as error:
    parser.exit(1, str(error) + "\n")
  print(json.dumps(result, ensure_ascii=False, indent=2))
  return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
  raise SystemExit(main())
