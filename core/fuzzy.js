// Small bounded matcher shared with the launcher tests. No per-query metadata parsing.
function normalize(value) {
  return String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
}
function distance(a, b, limit) {
  if (Math.abs(a.length - b.length) > limit) return limit + 1;
  let previous = Array.from({length: b.length + 1}, (_, i) => i);
  for (let i = 1; i <= a.length; i++) {
    const next = [i];
    let smallest = i;
    for (let j = 1; j <= b.length; j++) {
      next[j] = Math.min(next[j - 1] + 1, previous[j] + 1, previous[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
      smallest = Math.min(smallest, next[j]);
    }
    if (smallest > limit) return limit + 1;
    previous = next;
  }
  return previous[b.length];
}
function score(query, name, keywords) {
  if (!query) return 0;
  let total = 0;
  const words = query.split(/\s+/).slice(0, 8);
  for (const word of words) {
    if (name.startsWith(word)) { total += 100; continue; }
    if (name.includes(word)) { total += 75; continue; }
    if (keywords.includes(word)) { total += 50; continue; }
    let best = -1;
    for (const token of name.split(/[^a-z0-9]+/).filter(Boolean)) {
      const limit = word.length >= 6 ? 2 : word.length >= 4 ? 1 : 0;
      if (limit && distance(word, token, limit) <= limit) best = Math.max(best, 35);
      let cursor = 0;
      for (const letter of token) if (letter === word[cursor]) cursor++;
      if (cursor === word.length && word.length >= 2) best = Math.max(best, 20 - (token.length - word.length));
    }
    if (best < 0) return -1;
    total += best;
  }
  return total;
}
