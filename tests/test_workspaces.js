const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");
const model = {};
vm.createContext(model);
vm.runInContext(fs.readFileSync(path.join(__dirname, "../core/workspaces.js"), "utf8").replace(/^\.pragma library\s*/, ""), model);
const snapshot = {
  monitors: [{ name: "eDP-1", activeId: 2 }, { name: "DP-1", activeId: 9 }],
  workspaces: [
    { id: 2, name: "2", monitor: "eDP-1", occupied: true },
    { id: 9, name: "9", monitor: "DP-1", occupied: true },
    { id: -1000, name: "dev", monitor: "DP-1", occupied: true, urgent: true },
    { id: -99, name: "special:scratch", monitor: "DP-1", occupied: true }
  ]
};
const left = model.entries(snapshot, "eDP-1", 5);
const right = model.entries(snapshot, "DP-1", 5);
assert.equal(left.find(w => w.active).id, 2);
assert.equal(right.find(w => w.active).id, 9);
assert.equal(right.some(w => w.id === 2), false);
assert.equal(left.some(w => w.id === 9), false);
assert.equal(right.some(w => w.name.startsWith("special:")), false);
assert.equal(right.find(w => w.name === "dev").urgent, true);
assert.equal(model.entries({ monitors: [], workspaces: [] }, "eDP-1", 5).some(w => w.active), false);
snapshot.monitors[0].activeId = 12;
assert.equal(model.entries(snapshot, "eDP-1", 5).find(w => w.active).id, 12);
snapshot.monitors[1].activeId = -1000;
assert.equal(model.entries(snapshot, "DP-1", 5).find(w => w.active).label, "dev");
snapshot.workspaces[0].monitor = "DP-1";
assert.equal(model.entries(snapshot, "eDP-1", 5).some(w => w.id === 2), false);
assert.equal(model.entries(snapshot, "DP-1", 5).some(w => w.id === 2), true);
const commands = Array.from(model.focusCommands({ id: -1000, name: 'dev"\\\n' }, "DP-1", true));
assert.equal(commands[0], 'hl.dsp.focus({ monitor = "DP-1" })');
assert.equal(commands[1], 'hl.dsp.focus({ workspace = "name:dev\\"\\\\\\010" })');
assert.equal(model.focusCommands({ id: 9, name: "9" }, "", true)[0], "hl.dsp.focus({ workspace = 9 })");
assert.equal(model.focusCommands({ id: -1000, name: "dev" }, "", false)[0], "workspace name:dev");
console.log("Workspace checks passed: per-monitor focus, occupancy, named/dynamic spaces and dispatch quoting.");

const ten = Array.from({length: 10}, (_, index) => ({id: index + 1, name: String(index + 1), label: String(index + 1), active: false, occupied: true}));
for (let active = 1; active <= 10; active++) {
  const all = ten.map(entry => ({...entry, active: entry.id === active}));
  const compact = Array.from(model.compact(all));
  assert.ok(compact.length <= 5, "At most five cells with workspace " + active);
  assert.equal(compact.filter(entry => entry.active).length, 1);
  assert.equal(compact.find(entry => entry.active).id, active);
  assert.deepEqual(compact.filter(entry => !entry.gap).slice(0, 2).map(entry => entry.id), [1, 2]);
  const expanded = compact.flatMap(entry => entry.gap ? Array.from(entry.hidden) : [entry]);
  assert.deepEqual(expanded.map(entry => entry.id), ten.map(entry => entry.id));
  for (const gap of compact.filter(entry => entry.gap)) {
    assert.ok(gap.hidden.some(entry => entry.id === gap.target.id));
    const activeIndex = active - 1;
    const nearest = Array.from(gap.hidden).sort((a, b) => Math.abs(a.id - active) - Math.abs(b.id - active))[0];
    assert.equal(gap.target.id, nearest.id);
  }
  assert.equal(model.adjacent(all, 1).id, active === 10 ? 1 : active + 1);
  assert.equal(model.adjacent(all, -1).id, active === 1 ? 10 : active - 1);
}
assert.equal(model.compact(ten.slice(0, 5)).length, 5);
assert.equal(model.compact(ten).some(entry => entry.active), false);
assert.equal(model.adjacent([], 1), null);
const focusSix = ten.map(entry => ({...entry, active: entry.id === 6, urgent: entry.id === 4}));
assert.deepEqual(Array.from(model.compact(focusSix)).map(entry => entry.label), ["1", "2", "…", "6", "…"]);
assert.ok(model.compact(focusSix).some(entry => entry.gap && entry.urgent));
const named = ten.concat([{id: -1000, name: "dev", label: "dev", active: true, occupied: true}]);
assert.equal(model.compact(named).find(entry => entry.active).name, "dev");
console.log("Compact workspace checks passed: five cells, gaps, urgency, names and complete wheel navigation.");

for (let active = 1; active <= 10; active++) {
  const all = ten.map(entry => ({...entry, active: entry.id === active}));
  const current = Array.from(model.display(all, "current"));
  assert.equal(current.length, 1);
  assert.equal(current[0].id, active);
  const dots = Array.from(model.display(all, "dots"));
  assert.equal(dots.filter(entry => /^\d+$/.test(entry.label)).length, 1);
  assert.equal(dots.find(entry => entry.active).label, String(active));
}
assert.equal(model.display([], "current")[0].unavailable, true);
assert.equal(model.display([], "current")[0].active, false);
