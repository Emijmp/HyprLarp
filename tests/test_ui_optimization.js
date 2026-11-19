const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.join(__dirname, '..');

function load(relative) {
  let encodes = 0;
  const context = vm.createContext({encodeURIComponent: value => {
    encodes++;
    return encodeURIComponent(value);
  }});
  vm.runInContext(fs.readFileSync(path.join(root, relative), 'utf8').replace(/^\.pragma library\s*/, ''), context);
  return {context, encodes: () => encodes};
}

for (const relative of ['assets/branding.js', 'greeter/branding.js', 'components/icons.js']) {
  const {context, encodes} = load(relative);
  const branding = relative !== 'components/icons.js';
  const cache = branding ? 'artworkSourceCache' : 'iconSourceCache';
  const name = branding ? 'hyprlarp' : 'close';
  const first = context.source(name, '#ffffff', 1);
  assert.ok(first.startsWith('data:image/svg+xml;charset=utf-8,'));
  for (let index = 0; index < 1000; index++)
    assert.equal(context.source(name, '#ffffff', 1), first, 'reopened controls keep the same SVG');
  assert.equal(encodes(), 1, 'identical icons are escaped once across repeated controls');
  const tinted = decodeURIComponent(context.source(name, '#123456', .5).split(',', 2)[1]);
  assert.ok(tinted.includes('#123456') && tinted.includes(branding ? 'opacity="0.5"' : 'stroke-opacity="0.5"'));
  assert.ok(!tinted.includes('#ffffff'), 'changing tint updates the artwork');
  for (let index = 0; index < 500; index++)
    context.source(name, '#' + index.toString(16).padStart(6, '0'), index / 500);
  assert.equal(vm.runInContext('Object.keys(' + cache + ').length', context), 1, 'editing colors never accumulates old tints');
  if (branding) {
    assert.equal(context.source('unknown', '#ffffff', 1), '');
    assert.equal(vm.runInContext('Object.keys(' + cache + ').length', context), 1);
  } else {
    for (let index = 0; index < 500; index++)
      assert.equal(context.source('unknown-' + index, '#ffffff', 1), context.source('grid', '#ffffff', 1));
    assert.equal(vm.runInContext('Object.keys(' + cache + ').length', context), 2, 'unknown names share the fixed fallback slot');
  }
}

const {context: colors} = load('core/accessibility.js');
const calculate = colors.luminance;
let conversions = 0;
colors.luminance = value => { conversions++; return calculate(value); };
const background = ['#757575', '#757575', '#757575'];
assert.equal(colors.ensureContrast('#222222', background, 4.5), '#020202');
assert.ok(conversions < 50, 'contrast search converts fixed backgrounds once, rather than per candidate');
for (const color of ['#000000', '#ffffff', '#777777', '#d79921', '#123456']) {
  const expected = colors.contrast('#000000', color) >= colors.contrast('#ffffff', color) ? '#000000' : '#ffffff';
  assert.equal(colors.contrastText(color), expected, 'foreground contrast stays identical');
}
console.log('Bounded icon reuse and contrast search verified');
