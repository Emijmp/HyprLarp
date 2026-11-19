// Temporary panel edits follow confirmed settings, including Undo and Reset.
var keys = ["panelLayout", "panelStyle", "panelOpacity", "panelBlur"];
function snapshot(settings) {
  return {
    panelLayout: settings.panelLayout || "floating",
    panelStyle: settings.panelStyle || "standard",
    panelOpacity: settings.panelOpacity ?? 1,
    panelBlur: !!settings.panelBlur
  };
}
function equal(first, second) {
  return keys.every(key => first[key] === second[key]);
}
function create(settings) {
  const saved = snapshot(settings);
  return {saved: saved, values: Object.assign({}, saved), submitted: null, error: ""};
}
function sync(draft, settings) {
  const saved = snapshot(settings);
  if (draft.submitted && equal(saved, draft.submitted))
    return create(saved);
  // Unrelated changes retain the user's draft. Authoritative panel changes
  // (Undo, Reset, import or another window) replace that draft explicitly.
  return equal(saved, draft.saved) ? draft : create(saved);
}
function edit(draft, key, value) {
  if (!keys.includes(key) || draft.submitted)
    return draft;
  const values = Object.assign({}, draft.values);
  values[key] = value;
  return {saved: draft.saved, values: values, submitted: null, error: ""};
}
function submit(draft) {
  const values = Object.assign({}, draft.values);
  if (values.panelStyle === "glass")
    values.panelOpacity = Math.min(values.panelOpacity, .86);
  return {saved: draft.saved, values: values, submitted: Object.assign({}, values), error: ""};
}
function fail(draft, reason) {
  return {saved: draft.saved, values: draft.values, submitted: null, error: reason};
}
function settle(draft, settings) {
  if (!draft.submitted)
    return sync(draft, settings);
  return equal(snapshot(settings), draft.submitted) ? create(settings) : fail(draft, "No se guardó el diseño del panel. Puedes reintentarlo o descartar la vista previa.");
}
function pending(draft) {
  return !equal(draft.values, draft.saved);
}
