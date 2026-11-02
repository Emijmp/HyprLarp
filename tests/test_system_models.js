const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");
function moduleContext(name) {
  const context = vm.createContext({});
  vm.runInContext(fs.readFileSync(path.join(__dirname, "../core/" + name), "utf8"), context);
  return context;
}
const night = moduleContext("nightSchedule.js");
const scheduled = {nightLightSchedule: true, nightLightStart: "20:00", nightLightEnd: "07:00"};
for (const [hour, minute, expected] of [[19,59,false],[20,0,true],[23,59,true],[0,0,true],[6,59,true],[7,0,false],[12,0,false]])
  assert.equal(night.active(scheduled, new Date(2026, 10, 1, hour, minute)), expected);
assert.equal(night.active({...scheduled,nightLightEnd:"20:00"}, new Date()), true);
assert.equal(night.active({nightLightEnabled:true,nightLightSchedule:false}, new Date()), true);
const osd = moduleContext("osdState.js");
let state = osd.update(null, {id:1,value:0.5,muted:false,available:true}, 0);
assert.equal(state.changed, false);
state = osd.update(state.sample, {id:1,value:0.6,muted:false,available:true}, 100);
assert.equal(state.changed, false);
state = osd.update(state.sample, {id:1,value:0.7,muted:false,available:true}, 1000);
assert.equal(state.changed, true);
assert.equal(osd.update(state.sample, {id:1,value:0.7,muted:true,available:true}, 1100).changed, true);
assert.equal(osd.update(state.sample, {id:2,value:0.2,muted:false,available:true}, 1100).changed, false);
assert.equal(osd.update(state.sample, {id:1,value:0,muted:false,available:false}, 1100).changed, false);
