const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");
const context = vm.createContext({});
vm.runInContext(fs.readFileSync(path.join(__dirname, "../core/displays.js"), "utf8"), context);
const outputs = [
  {name: "eDP-1", enabled: true, mode: "1920x1080@60", modes: ["1920x1080@60", "1920x1080@40"], scale: 1.25, transform: 0, x: 0, y: 0, mirror: "", internal: true},
  {name: "HDMI-A-1", enabled: true, mode: "1920x1080@60", modes: ["1920x1080@60"], scale: 1, transform: 0, x: 1536, y: 0, mirror: "", internal: false}
];
assert.equal(context.size(outputs[0], outputs[0]).width, 1536);
assert.equal(context.size({...outputs[0], transform: 1}, outputs[0]).width, 864);
assert.equal(context.projection(outputs), "extend");
assert.equal(context.projection([outputs[0], {...outputs[1], mirror: "eDP-1"}]), "duplicate");
assert.equal(context.projection([outputs[0], {...outputs[1], enabled: false}]), "internal-only");
assert.equal(context.projection([{...outputs[0], enabled: false}, outputs[1]]), "external-only");
assert.ok(context.scales(outputs[0], outputs[0]).includes("1.25"));
assert.ok(!context.scales(outputs[0], outputs[0]).includes("1.75"));
const moved = context.move(outputs, "HDMI-A-1", 1550, 10, outputs);
assert.equal(moved[1].x, 1536);
assert.equal(moved[1].y, 0);
assert.equal(outputs[1].x, 1536);
