const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const geometry = vm.createContext({});
vm.runInContext(fs.readFileSync(path.join(__dirname, '../core/panelGeometry.js'), 'utf8'), geometry);
for (const [screenWidth, screenHeight] of [[320, 240], [800, 480], [1920, 1080], [16, 10]]) {
  for (const layoutMode of ['floating', 'centered', 'sidebar']) {
    for (const position of ['left', 'right', 'top', 'bottom']) {
      for (const scale of [1, 1.25, 2]) {
        const gap = 52 * scale;
        const area = geometry.availableArea(screenWidth, screenHeight, {layoutMode, position, gap, margins: {right: 8}});
        const width = geometry.widthFor(area, layoutMode, 520 * scale, scale);
        for (const panelName of ['performance', 'launcher']) {
          const placed = geometry.place(area, width, 2000, {layoutMode, panelName, position});
          assert.ok(placed.x >= 0 && placed.y >= 0);
          assert.ok(placed.width > 0 && placed.height > 0);
          assert.ok(placed.x + placed.width <= screenWidth + 1e-6);
          assert.ok(placed.y + placed.height <= screenHeight + 1e-6);
          assert.ok(placed.x >= area.x && placed.y >= area.y);
          assert.ok(placed.x + placed.width <= area.x + area.width + 1e-6);
          assert.ok(placed.y + placed.height <= area.y + area.height + 1e-6);
          if (position === 'left' && screenWidth > gap)
            assert.ok(placed.x >= gap);
          if (position === 'right' && screenWidth > gap)
            assert.ok(placed.x + placed.width <= screenWidth - gap + 1e-6);
        }
      }
    }
  }
}
const area = geometry.availableArea(1280, 720, {layoutMode: 'centered', position: 'top', gap: 50});
const centered = geometry.place(area, 560, 400, {layoutMode: 'centered', position: 'top'});
assert.equal(centered.x + centered.width / 2, area.x + area.width / 2);
assert.equal(centered.y + centered.height / 2, area.y + area.height / 2);
console.log('Panel positions stay within each screen and respect vertical bars at every scale');
