const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
function load(file) {
  const context = vm.createContext({Date});
  vm.runInContext(fs.readFileSync(path.join(__dirname, '..', file), 'utf8'), context);
  return context;
}
const dates = load('core/datetime.js');
assert.equal(dates.timePattern({clockFormat: '12h', clockSeconds: true}), 'hh:mm:ss AP');
assert.equal(dates.timePattern({clockFormat: '24h', clockSeconds: false}), 'hh:mm');
assert.equal(dates.isoWeek(new Date(2021, 0, 1)), 53);
assert.equal(dates.isoWeek(new Date(2021, 0, 4)), 1);
assert.equal(dates.isoWeek(new Date(2024, 11, 30)), 1);
for (const start of ['monday', 'sunday']) {
  for (const weeks of [false, true]) {
    const grid = dates.monthGrid(2024, 1, start, weeks);
    assert.equal(grid.filter(cell => cell.kind === 'day' && cell.valid).length, 29);
    assert.equal(grid.filter(cell => cell.kind === 'week').length, weeks ? 6 : 0);
    assert.equal(grid.length, (weeks ? 8 : 7) * 7);
    assert.equal(grid[weeks ? 1 : 0].label, start === 'sunday' ? 'D' : 'L');
    assert.equal(grid.filter(cell => cell.kind === 'day').findIndex(cell => cell.number === 1), start === 'sunday' ? 4 : 3);
  }
}
const search = load('core/configuration.js');
assert.equal(search.search('  ').length, 0);
assert.equal(search.search('zzzznoresult').length, 0);
for (const [query, page, anchor] of [
  ['SEGUNDOS', 'General', 'setting-clockSeconds'], ['batería crítica', 'General', 'setting-batteryAlerts'],
  ['lunes', 'General', 'setting-calendar'], ['opacidad paneles', 'Appearance', undefined],
  ['monitores', 'Displays', 'Pantallas conectadas'], ['atajos', 'Shortcuts', undefined]
]) {
  const result = search.search(query).find(entry => entry[0] === page);
  assert.ok(result, query);
  if (anchor) assert.equal(result[3], anchor);
}
console.log('Calendar, clock and settings search passed');
