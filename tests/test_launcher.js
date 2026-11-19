const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const context = vm.createContext({});
for (const file of ["fuzzy.js", "launcher.js"])
  vm.runInContext(fs.readFileSync(path.join(__dirname, "../core", file), "utf8"), context);
for (const name of ["Firefox Web Browser", "Visual Studio Code", "Calculadora", "Configuración"])
  for (const query of ["", "firefx", "vis stud", "calc", "conf", "zzzz"])
    assert.equal(context.score(query, name.toLowerCase(), name.toLowerCase()), context.scoreWords(query ? query.split(/\s+/) : [], name.toLowerCase(), name.toLowerCase(), name.toLowerCase().split(/[^a-z0-9]+/).filter(Boolean)));
assert.ok(context.matches("configuracion", "Configuración del escritorio"));
assert.ok(!context.matches("wifi", "Bluetooth"));
function exactDistance(a, b) {
  let row = Array.from({length: b.length + 1}, (_, index) => index);
  for (let i = 1; i <= a.length; i++) {
    const next = [i];
    for (let j = 1; j <= b.length; j++)
      next[j] = Math.min(next[j - 1] + 1, row[j] + 1, row[j - 1] + (a[i - 1] !== b[j - 1]));
    row = next;
  }
  return row[b.length];
}
for (const a of ["", "a", "ab", "abcd", "firefox", "firefx"])
  for (const b of ["", "b", "ab", "acbd", "firfox", "firefox"])
    for (const limit of [0, 1, 2]) {
      const expected = exactDistance(a, b), result = context.distance(a, b, limit);
      assert.ok(expected > limit ? result > limit : result === expected, `${a}/${b}/${limit}`);
    }
const definitions = JSON.parse(fs.readFileSync(path.join(__dirname, "../config/modules.json"), "utf8"));
assert.ok(context.actions(definitions, "> configuración").length > 0);
assert.ok(!context.actions(definitions, "").some(entry => entry.id === "launcher"));
assert.equal(context.actions(definitions, "> barra")[0].id, "navigation");
assert.ok(context.actions(definitions, "> bandeja").some(entry => entry.target === "navigation"));
