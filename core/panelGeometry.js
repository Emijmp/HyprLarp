// The desktop and the design preview use the same logical screen geometry.
function finite(value, fallback) {
  return typeof value === "number" && Number.isFinite(value) ? Math.max(0, value) : fallback;
}
function availableArea(width, height, options) {
  width = Math.max(1, finite(width, 1));
  height = Math.max(1, finite(height, 1));
  options = options || {};
  const position = options.position || "top";
  const sidebar = options.layoutMode === "sidebar";
  const gap = finite(options.gap, 0);
  const margins = options.margins || {};
  const left = Math.min(width - 1, position === "left" ? gap : sidebar ? 0 : 8);
  const right = Math.min(width - left - 1, position === "right" ? gap : sidebar ? 0 : Math.max(8, finite(margins.right, 8)));
  const top = Math.min(height - 1, sidebar ? 0 : position === "top" ? gap : 8);
  const bottom = Math.min(height - top - 1, sidebar ? 0 : position === "bottom" ? gap : 8);
  return {x: left, y: top, width: width - left - right, height: height - top - bottom};
}
function widthFor(area, layoutMode, preferredWidth, scale) {
  scale = Math.max(0.1, finite(scale, 1));
  const preferred = layoutMode === "sidebar" ? 420 * scale : layoutMode === "centered" ? 560 * scale : finite(preferredWidth, 360 * scale);
  return Math.max(1, Math.min(area.width, preferred));
}
function place(area, width, height, options) {
  options = options || {};
  width = Math.max(1, Math.min(area.width, finite(width, area.width)));
  height = options.layoutMode === "sidebar" ? area.height : Math.max(1, Math.min(area.height, finite(height, area.height)));
  const centered = options.layoutMode === "centered" || (options.panelName === "launcher" && options.layoutMode !== "sidebar");
  const x = centered ? area.x + (area.width - width) / 2 : options.position === "left" && options.layoutMode !== "sidebar" ? area.x : area.x + area.width - width;
  const y = centered ? area.y + (area.height - height) / 2 : options.position === "bottom" && options.layoutMode !== "sidebar" ? area.y + area.height - height : area.y;
  return {x: x, y: y, width: width, height: height};
}
