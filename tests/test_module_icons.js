const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");
const root = path.join(__dirname, "..");
const context = vm.createContext({});
vm.runInContext(fs.readFileSync(path.join(root, "components/icons.js"), "utf8").replace(/^\.pragma library\s*/, "") + "\nglobalThis.availableIcons = paths;", context);
vm.runInContext(fs.readFileSync(path.join(root, "assets/branding.js"), "utf8").replace(/^\.pragma library\s*/, ""), context);
const modules = JSON.parse(fs.readFileSync(path.join(root, "config/modules.json"), "utf8"));
for (const entry of modules) {
  assert.ok(context.availableIcons[entry.icon] || context.supports(entry.icon), entry.id + " has its own valid icon");
}
