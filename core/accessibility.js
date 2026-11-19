function linearChannel(hex, offset) {
  const value = parseInt(hex.slice(offset, offset + 2), 16) / 255;
  return value <= .04045 ? value / 12.92 : Math.pow((value + .055) / 1.055, 2.4);
}
function luminance(hex) {
  return linearChannel(hex, 1) * .2126 + linearChannel(hex, 3) * .7152 + linearChannel(hex, 5) * .0722;
}
function contrast(a, b) {
  const first = luminance(a), second = luminance(b);
  return (Math.max(first, second) + .05) / (Math.min(first, second) + .05);
}
function contrastText(background) {
  const value = luminance(background) + .05;
  return value / .05 >= 1.05 / value ? "#000000" : "#ffffff";
}
function ensureContrast(color, backgrounds, ratio) {
  color = /^#[0-9a-f]{6}$/i.test(String(color)) ? String(color).toLowerCase() : "#ffffff";
  const surfaces = (backgrounds || []).filter(value => /^#[0-9a-f]{6}$/i.test(String(value)));
  if (!surfaces.length)
    return color;
  ratio = ratio || 4.5;
  // Every candidate is compared with the same surfaces. Convert those only
  // once, rather than repeating their gamma conversion throughout the search.
  const surfaceLuminances = surfaces.map(surface => luminance(String(surface)));
  const score = candidate => {
    const value = luminance(candidate);
    let minimum = Infinity;
    for (const surface of surfaceLuminances)
      minimum = Math.min(minimum, (Math.max(value, surface) + .05) / (Math.min(value, surface) + .05));
    return minimum;
  };
  const initialScore = score(color);
  if (initialScore >= ratio)
    return color;
  const channels = [1, 3, 5].map(index => parseInt(color.slice(index, index + 2), 16));
  const mix = (end, amount) => "#" + channels.map(value => Math.round(value + (end - value) * amount).toString(16).padStart(2, "0")).join("");
  let best = color;
  let bestScore = initialScore;
  let closest = Infinity;
  for (const end of [0, 255]) {
    const edge = mix(end, 1);
    const edgeScore = score(edge);
    if (closest === Infinity && edgeScore > bestScore) {
      best = edge;
      bestScore = edgeScore;
    }
    if (edgeScore < ratio)
      continue;
    let low = 0, high = 1;
    for (let step = 0; step < 20; step++) {
      const middle = (low + high) / 2;
      if (score(mix(end, middle)) >= ratio)
        high = middle;
      else
        low = middle;
    }
    const candidate = mix(end, high);
    const distance = channels.reduce((sum, value, index) => sum + Math.pow(value - parseInt(candidate.slice(1 + index * 2, 3 + index * 2), 16), 2), 0);
    if (distance < closest) {
      best = candidate;
      closest = distance;
    }
  }
  if (closest !== Infinity)
    return best;
  // Unusual custom surfaces may require a middle gray or be incompatible.
  // Choose the largest minimum contrast without claiming every palette works.
  for (let value = 0; value < 256; value++) {
    const candidate = "#" + value.toString(16).padStart(2, "0").repeat(3);
    const next = score(candidate);
    if (next > bestScore) {
      best = candidate;
      bestScore = next;
    }
  }
  return best;
}
function palette(base, enabled) {
  if (!enabled)
    return base;
  const light = luminance(base.background) > .5;
  return Object.assign({}, base, {
    background: light ? "#ffffff" : "#000000", surface: light ? "#ffffff" : "#000000",
    raised: light ? "#f2f2f2" : "#101010", moduleSurface: light ? "#ffffff" : "#000000",
    text: light ? "#000000" : "#ffffff", muted: light ? "#333333" : "#dedede",
    accent: light ? "#000000" : "#ffffff", border: light ? "#000000" : "#ffffff",
    separator: light ? "#555555" : "#bfbfbf", danger: light ? "#000000" : "#ffffff"
  });
}
