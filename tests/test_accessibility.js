const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const context = vm.createContext({});
vm.runInContext(fs.readFileSync(path.join(__dirname, '../core/accessibility.js'), 'utf8'), context);
const palettes = JSON.parse(fs.readFileSync(path.join(__dirname, '../config/palettes.json'), 'utf8'));
const correctedDark = context.ensureContrast('#222222', ['#757575'], 4.5);
assert.equal(correctedDark, '#020202', 'a farther white endpoint must not replace the closest valid dark variant');
assert.ok(context.contrast(correctedDark, '#757575') >= 4.5);
for (const base of [...Object.values(palettes), {...palettes.amoled, background: '#ffffff'}]) {
  const result = context.palette(base, true);
  for (const background of ['background', 'surface', 'raised']) {
    for (const foreground of ['text', 'muted', 'accent'])
      assert.ok(context.contrast(result[background], result[foreground]) >= 7, `${background} / ${foreground}`);
  }
  assert.equal(context.palette(base, false), base);
}
for (const base of Object.values(palettes)) {
  const surfaces = [base.surface, base.raised, base.moduleSurface];
  for (const extracted of ['#000000', '#ffffff', '#101010', '#aaaaaa', '#e7e7e7', '#cc1166', '#123456']) {
    const safe = context.ensureContrast(extracted, surfaces, 4.5);
    assert.match(safe, /^#[0-9a-f]{6}$/);
    for (const surface of surfaces)
      assert.ok(context.contrast(safe, surface) >= 4.5, `${base.name}: ${extracted} -> ${safe} on ${surface}`);
    assert.ok(context.contrast(context.contrastText(safe), safe) >= 4.5);
    assert.equal(context.ensureContrast(safe, surfaces, 4.5), safe, 'correction stays stable');
  }
}
vm.runInContext(fs.readFileSync(path.join(__dirname, '../core/focus.js'), 'utf8'), context);
const root = {visible:true, enabled:true, children:[]};
const hidden = {visible:false, enabled:true, activeFocusOnTab:true, width:30, height:30, parent:root};
const disabled = {...hidden, visible:true, enabled:false};
const button = {...hidden, visible:true, enabled:true};
root.children = [hidden, disabled, button];
assert.equal(context.first(root), button);
assert.equal(context.contains(root, button), true);
assert.equal(context.contains(button, root), false);
console.log('High contrast and focus navigation verified');
