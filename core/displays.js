var planKeys = ["name", "enabled", "mode", "scale", "transform", "x", "y", "mirror"];

function plan(outputs) {
  return outputs.map(output => {
    const result = {};
    for (const key of planKeys)
      result[key] = output[key];
    return result;
  });
}

function modeParts(mode) {
  const match = String(mode).match(/^(\d+)x(\d+)@([\d.]+)/);
  return match ? {width: Number(match[1]), height: Number(match[2]), refresh: Number(match[3])} : {width: 1920, height: 1080, refresh: 60};
}

function size(output, info) {
  const mode = output.mode === "preferred" ? ((info && info.modes || [])[0] || "1920x1080@60") : output.mode;
  const dimensions = modeParts(mode);
  const rotated = [1, 3, 5, 7].includes(Number(output.transform));
  return {width: (rotated ? dimensions.height : dimensions.width) / output.scale,
    height: (rotated ? dimensions.width : dimensions.height) / output.scale};
}

function resolution(mode) {
  return mode === "preferred" ? "preferred" : String(mode).split("@")[0];
}

function resolutions(info) {
  return ["preferred"].concat(Array.from(new Set((info.modes || []).map(resolution))));
}

function rates(output, info) {
  return output.mode === "preferred" ? ["auto"] : (info.modes || []).filter(mode => resolution(mode) === resolution(output.mode)).map(mode => mode.split("@")[1]);
}

function scales(output, info) {
  const dimensions = modeParts(output.mode === "preferred" ? (info.modes || [])[0] : output.mode);
  return Array.from(new Set([.5, .75, 1, 1.25, 1.5, 1.75, 2, 2.5, 3, 4, output.scale]))
    .filter(scale => [dimensions.width / scale, dimensions.height / scale].every(value => Math.abs(value - Math.round(value)) < .02))
    .sort((a, b) => a - b).map(String);
}

function projection(outputs) {
  const enabled = outputs.filter(output => output.enabled);
  if (enabled.length === 1)
    return enabled[0].internal ? "internal-only" : "external-only";
  if (enabled.some(output => output.mirror))
    return "duplicate";
  return enabled.length > 1 ? "extend" : "internal-only";
}

function move(outputs, name, x, y, information) {
  const next = plan(outputs);
  const current = next.find(output => output.name === name);
  if (!current)
    return next;
  const own = size(current, information.find(output => output.name === name));
  const xs = [0], ys = [0];
  for (const other of next.filter(output => output.name !== name && output.enabled && !output.mirror)) {
    const dimensions = size(other, information.find(output => output.name === other.name));
    xs.push(other.x, other.x + dimensions.width, other.x - own.width, other.x + dimensions.width - own.width);
    ys.push(other.y, other.y + dimensions.height, other.y - own.height, other.y + dimensions.height - own.height);
  }
  const snap = (value, candidates) => candidates.reduce((best, candidate) => Math.abs(value - candidate) < Math.abs(value - best) ? candidate : best, value + 48);
  const sx = snap(x, xs), sy = snap(y, ys);
  current.x = Math.round(Math.abs(sx - x) < 48 ? sx : x);
  current.y = Math.round(Math.abs(sy - y) < 48 ? sy : y);
  return next;
}
