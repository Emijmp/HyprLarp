"""Bounded, cancellable file search and an arithmetic parser; no resident indexer."""

from __future__ import annotations

import ast
from collections import deque
from heapq import nsmallest
import math
import operator
import os
from pathlib import Path
import threading
import time
import unicodedata

MAX_ENTRIES = 5000
MAX_RESULTS = 40
IGNORE = {"node_modules", "__pycache__", "target", "vendor", "venv", "pkg"}
OPERATORS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
  ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod, ast.Pow: operator.pow}
FUNCTIONS = {"sqrt": math.sqrt, "abs": abs, "round": round, "sin": math.sin, "cos": math.cos, "tan": math.tan,
  "log": math.log, "log10": math.log10}


def calculate(expression):
  if not isinstance(expression, str) or not 1 <= len(expression) <= 256:
    raise ValueError("Expresión demasiado larga")
  try:
    tree = ast.parse(expression.strip(), mode="eval")
    if len(list(ast.walk(tree))) > 64:
      raise ValueError("Expresión demasiado compleja")
    def visit(node):
      if isinstance(node, ast.Expression):
        value = visit(node.body)
      elif isinstance(node, ast.Constant) and type(node.value) in {int, float}:
        value = node.value
      elif isinstance(node, ast.Name) and node.id in {"pi", "e"}:
        value = {"pi": math.pi, "e": math.e}[node.id]
      elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = visit(node.operand) * (-1 if isinstance(node.op, ast.USub) else 1)
      elif isinstance(node, ast.BinOp) and type(node.op) in OPERATORS:
        left, right = visit(node.left), visit(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > 12:
          raise ValueError("El exponente máximo es 12")
        value = OPERATORS[type(node.op)](left, right)
      elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FUNCTIONS and not node.keywords and 1 <= len(node.args) <= 2:
        value = FUNCTIONS[node.func.id](*(visit(argument) for argument in node.args))
      else:
        raise ValueError("Usa números, operaciones y funciones matemáticas")
      if type(value) not in {int, float} or not math.isfinite(value) or abs(value) > 1e15:
        raise ValueError("Resultado fuera del intervalo permitido")
      return value
    result = visit(tree)
    return str(result) if isinstance(result, int) else format(result, ".12g")
  except (SyntaxError, TypeError, ArithmeticError, RecursionError) as error:
    raise ValueError("Expresión matemática inválida") from error


def normalize(value):
  return "".join(character for character in unicodedata.normalize("NFD", value.casefold()) if not unicodedata.combining(character))


class LauncherSearch:
  def __init__(self, service, api, home=None):
    self.s, self.api = service, api
    self.home = Path(home or Path.home())
    self.lock = threading.RLock()
    self.token = ""
    self.query = ""
    self.index = None
    self.index_at = 0
    self.truncated = False

  def cancel(self):
    with self.lock:
      self.token = ""
      self.index = None
      self.index_at = 0

  def current(self, token):
    with self.lock:
      return self.token == token and not self.s.stopping.is_set()

  def build_index(self, token):
    queue = deque([(self.home, 0)])
    entries, visited, truncated = [], 0, False
    while queue and visited < MAX_ENTRIES and self.current(token):
      directory, depth = queue.popleft()
      try:
        with os.scandir(directory) as children:
          for child in children:
            visited += 1
            if visited > MAX_ENTRIES:
              truncated = True
              break
            if not self.current(token):
              return None
            if child.name.startswith(".") or child.name in IGNORE or child.is_symlink():
              continue
            folder = child.is_dir(follow_symlinks=False)
            if folder or child.is_file(follow_symlinks=False):
              entries.append((normalize(child.name), child.name, child.path, folder))
            if folder and depth < 3:
              queue.append((Path(child.path), depth + 1))
      except OSError:
        continue
    if queue:
      truncated = True
    with self.lock:
      if not self.current(token):
        return None
      self.index, self.index_at, self.truncated = entries, time.monotonic(), truncated
    return entries

  def files(self, query, token):
    if query.startswith(("/", "~/")):
      path = Path(query).expanduser()
      folder, prefix = (path, "") if query.endswith("/") else (path.parent, normalize(path.name))
      matches = []
      truncated = False
      try:
        with os.scandir(folder) as entries:
          for index, entry in enumerate(entries):
            if not self.current(token):
              return [], False
            if index >= MAX_ENTRIES:
              truncated = True
              break
            if not entry.name.startswith(".") and normalize(entry.name).startswith(prefix):
              matches.append((normalize(entry.name), entry.name, entry.path, entry.is_dir()))
              if len(matches) > MAX_RESULTS:
                truncated = True
                break
      except OSError:
        pass
      return self.results(matches), truncated
    words = normalize(query).split()[:8]
    if not words:
      return [], False
    with self.lock:
      index = self.index if time.monotonic() - self.index_at < 30 else None
    if index is None:
      index = self.build_index(token)
    if index is None:
      return [], False
    # Only forty results can reach the view. Keep one extra to report truncation
    # instead of allocating and sorting every matching entry on each keystroke.
    matches = nsmallest(MAX_RESULTS + 1,
      (entry for entry in index if all(word in entry[0] for word in words)),
      key=lambda item: (not item[0].startswith(words[0]), not item[3], item[0]))
    return self.results(matches), self.truncated or len(matches) > MAX_RESULTS

  @staticmethod
  def results(entries):
    return [{"kind": "file", "id": path, "path": path, "name": name,
      "genericName": str(Path(path).parent), "directory": folder, "icon": ""}
      for normalized, name, path, folder in entries[:MAX_RESULTS]]

  def refresh(self):
    with self.lock:
      query, token = self.query, self.token
    if not token:
      return
    results, truncated, error = [], False, ""
    if query.startswith("="):
      try:
        value = calculate(query[1:])
        results = [{"kind": "calculation", "id": query, "name": value, "value": value,
          "genericName": query[1:].strip() + " · Enter para copiar", "icon": ""}]
      except ValueError as failure:
        error = str(failure)
    else:
      results, truncated = self.files(query.removeprefix("?").strip(), token)
    if self.current(token):
      self.s.emit("launcher-results", {"token": token, "results": results, "truncated": truncated, "error": error})

  def handle(self, action, data):
    if action == "launcher-query":
      query, token = data.get("query", ""), data.get("token", "")
      if not isinstance(query, str) or len(query) > 4096 or "\0" in query or not isinstance(token, str) or len(token) > 128:
        raise ValueError("Búsqueda inválida")
      if not token:
        self.cancel()
        return True
      with self.lock:
        self.query, self.token = query, token
      self.s.queue_refresh("launcher-search", self.refresh, latest=True)
      return True
    if action == "launcher-open":
      path = data.get("path")
      if not isinstance(path, str) or not path or len(path) > 4096 or "\0" in path or not Path(path).is_absolute() or not Path(path).exists():
        raise ValueError("El archivo ya no está disponible")
      if not self.api.shutil.which("xdg-open"):
        raise RuntimeError("Instala xdg-utils para abrir archivos")
      self.api.subprocess.Popen(["xdg-open", path], stdout=self.api.subprocess.DEVNULL,
        stderr=self.api.subprocess.DEVNULL, start_new_session=True)
      return True
    return False
