function timePattern(settings) {
  return "hh:mm" + (settings.clockSeconds ? ":ss" : "") + (settings.clockFormat === "12h" ? " AP" : "");
}

function monthGrid(year, month, firstDay, weekNumbers) {
  const start = firstDay === "sunday" ? 0 : 1;
  const offset = (new Date(year, month, 1).getDay() - start + 7) % 7;
  const count = new Date(year, month + 1, 0).getDate();
  const headings = ["D", "L", "M", "X", "J", "V", "S"];
  const cells = [];
  if (weekNumbers)
    cells.push({kind: "heading", label: "Sem."});
  for (let day = 0; day < 7; day++)
    cells.push({kind: "heading", label: headings[(start + day) % 7]});
  for (let row = 0; row < 6; row++) {
    // ISO weeks start on Monday. A Sunday-first row is labelled for its Monday.
    if (weekNumbers)
      cells.push({kind: "week", label: String(isoWeek(new Date(year, month, 1 - offset + row * 7 + (start === 0 ? 1 : 0))))});
    for (let column = 0; column < 7; column++) {
      const number = row * 7 + column - offset + 1;
      cells.push({kind: "day", number: number, valid: number > 0 && number <= count});
    }
  }
  return cells;
}

function isoWeek(date) {
  const value = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
  value.setUTCDate(value.getUTCDate() + 4 - (value.getUTCDay() || 7));
  const yearStart = new Date(Date.UTC(value.getUTCFullYear(), 0, 1));
  return Math.ceil(((value - yearStart) / 86400000 + 1) / 7);
}
