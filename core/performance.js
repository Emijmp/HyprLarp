function numeric(value) {
  return typeof value === "number" && Number.isFinite(value);
}
function format(value, unit, digits) {
  return numeric(value) ? value.toFixed(digits === undefined ? 1 : digits) + (unit || "") : "N/D";
}
function duration(milliseconds) {
  return numeric(milliseconds) ? milliseconds >= 1000 ? format(milliseconds / 1000, " s", 2) : format(milliseconds, " ms", 0) : "N/D";
}
function reportLabel(report) {
  return report.label + " · " + new Date(report.createdAt).toLocaleString(Qt.locale("es"), "dd/MM HH:mm") + " · " + report.revision.slice(0, 8);
}
function compare(first, second) {
  if (!first || !second || first.id === second.id)
    return {compatible: false, reason: "Guarda y elige dos mediciones distintas."};
  if (first.context.fingerprint !== second.context.fingerprint)
    return {compatible: false, reason: "El modo, la configuración, las pantallas o el sistema son diferentes. Las cifras se muestran por separado."};
  const difference = (a, b) => numeric(a) && numeric(b) ? b - a : null;
  return {compatible: true,
    cpu: difference(first.summary.cpuPercent, second.summary.cpuPercent),
    rss: difference(first.summary.rssMiB, second.summary.rssMiB),
    pss: difference(first.summary.pssMiB, second.summary.pssMiB),
    startup: difference(first.startupMs, second.startupMs)};
}
function signed(value, unit, digits) {
  return numeric(value) ? (value > 0 ? "+" : "") + format(value, unit, digits) : "N/D";
}
