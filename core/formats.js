function number(value, unit, decimals) {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return "No disponible";
  return Number(value).toLocaleString(Qt.locale(), "f", decimals === undefined ? 1 : decimals) + (unit ? " " + unit : "");
}
function bytes(value) {
  if (value === null || value === undefined) return "No disponible";
  const units = ["B", "KiB", "MiB", "GiB", "TiB"];
  let index = 0;
  while (value >= 1024 && index < units.length - 1) { value /= 1024; index++; }
  return Number(value).toLocaleString(Qt.locale(), "f", index === 0 ? 0 : 1) + " " + units[index];
}
function duration(seconds) {
  if (!seconds || seconds < 0) return "No disponible";
  const minutes = Math.max(1, Math.round(seconds / 60));
  return (minutes >= 60 ? Math.floor(minutes / 60) + " h " : "") + (minutes % 60) + " min";
}
