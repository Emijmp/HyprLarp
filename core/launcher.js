// Pure result filtering; the window model itself is maintained by Wayland events.
function matches(text, name) {
  const clean = value => String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  return clean(text).trim().split(/\s+/).every(word => clean(name).includes(word));
}
function actions(definitions, query) {
  const text = query.replace(/^>\s*/, "");
  const navigation = {id: "navigation", kind: "panel", target: "navigation", title: "Barra y bandeja", description: "Acceso por teclado a módulos, espacios de trabajo e iconos de la bandeja."};
  return [navigation].concat(definitions).filter(entry => ["panel", "settings", "command", "session", "toggle"].includes(entry.kind) && entry.id !== "launcher" && matches(text, entry.title + " " + entry.description))
    .map(entry => ({kind: "action", id: entry.id, name: entry.title, genericName: "Acción del escritorio · " + entry.description,
      icon: "", target: entry.target, actionKind: entry.kind, definition: entry}));
}
