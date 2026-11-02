.pragma library

// A monitor owns its active workspace. Global keyboard focus is a separate state.
function entries(snapshot, monitorName, count) {
  const monitors = snapshot.monitors || [];
  const workspaces = (snapshot.workspaces || []).filter(w => !w.name.startsWith("special:"));
  const monitor = monitors.find(m => m.name === monitorName);
  const activeId = monitor ? monitor.activeId : null;
  const selected = [];
  for (let id = 1; id <= count; id++) {
    const existing = workspaces.find(w => w.id === id);
    if (!existing || !existing.monitor || existing.monitor === monitorName)
      selected.push(existing || { id: id, name: String(id), monitor: "", occupied: false });
  }
  for (const workspace of workspaces) {
    if ((workspace.monitor === monitorName || workspace.id === activeId) && !selected.some(w => w.id === workspace.id))
      selected.push(workspace);
  }
  if (activeId !== null && activeId !== undefined && !selected.some(w => w.id === activeId))
    selected.push({ id: activeId, name: String(activeId), monitor: monitorName, occupied: false });
  selected.sort((a, b) => a.id > 0 && b.id > 0 ? a.id - b.id : a.id > 0 ? -1 : b.id > 0 ? 1 : a.name.localeCompare(b.name));
  return selected.map(w => ({
    id: w.id,
    name: w.name,
    label: w.id > 0 ? String(w.id) : w.name,
    active: w.id === activeId,
    occupied: !!w.occupied,
    urgent: !!w.urgent
  }));
}

// Keep the first two spaces and the active one; gaps remain navigable.
function compact(workspaces) {
  if (workspaces.length <= 5)
    return workspaces;
  const active = workspaces.findIndex(workspace => workspace.active);
  const visible = [0, 1];
  if (active > 1)
    visible.push(active);
  const result = [];
  function gap(start, end) {
    if (start > end)
      return;
    if (start === end) {
      result.push(workspaces[start]);
      return;
    }
    const hidden = workspaces.slice(start, end + 1);
    const target = workspaces[end < active ? end : start];
    result.push({
      gap: true,
      label: "…",
      name: hidden.map(workspace => workspace.label).join(", "),
      target: target,
      hidden: hidden,
      active: false,
      occupied: hidden.some(workspace => workspace.occupied),
      urgent: hidden.some(workspace => workspace.urgent)
    });
  }
  let previous = -1;
  for (const index of visible) {
    gap(previous + 1, index - 1);
    result.push(workspaces[index]);
    previous = index;
  }
  gap(previous + 1, workspaces.length - 1);
  return result;
}

function display(workspaces, mode) {
  if (mode === "compact")
    return compact(workspaces);
  if (mode === "dots")
    return compact(workspaces).map(workspace => workspace.active || workspace.gap ? workspace : Object.assign({}, workspace, {label: "·"}));
  const active = workspaces.find(workspace => workspace.active);
  return active ? [active] : [{id: null, name: "Sin espacio activo", label: "—", active: false, unavailable: true}];
}

function adjacent(workspaces, direction) {
  if (!workspaces.length)
    return null;
  const active = workspaces.findIndex(workspace => workspace.active);
  if (active < 0)
    return workspaces[direction < 0 ? workspaces.length - 1 : 0];
  return workspaces[(active + (direction < 0 ? -1 : 1) + workspaces.length) % workspaces.length];
}

function luaQuote(value) {
  return '"' + value.replace(/[\\"\x00-\x1f]/g, character => {
    if (character === "\\" || character === '"')
      return "\\" + character;
    return "\\" + character.charCodeAt(0).toString().padStart(3, "0");
  }) + '"';
}

function focusCommands(workspace, monitor, usingLua) {
  const target = workspace.id > 0 ? String(workspace.id) : "name:" + workspace.name;
  const commands = [];
  if (monitor)
    commands.push(usingLua ? "hl.dsp.focus({ monitor = " + luaQuote(monitor) + " })" : "focusmonitor " + monitor);
  commands.push(usingLua ? "hl.dsp.focus({ workspace = " + (workspace.id > 0 ? target : luaQuote(target)) + " })" : "workspace " + target);
  return commands;
}
