-- Loaded before the user's binds. Keeps their handlers and native bind handles.
-- No commands, IPC calls, timers or filesystem writes run in a bind callback.
if rawget(_G, "HyprLarpBinds") then
  return HyprLarpBinds
end

local manager = {
  nativeBind = hl.bind,
  nativeExec = hl.dsp.exec_cmd,
  records = {},
  owned = {},
  disabled = {},
  commands = setmetatable({}, { __mode = "k" }),
  conflicts = {},
  legacy = {},
  migrate = false,
  overflow = false,
  stopped = false,
  runtimePath = "",
}
_G.HyprLarpBinds = manager

local function copy(value)
  local result = {}
  for key, item in pairs(value or {}) do
    result[key] = item
  end
  return result
end

local function canonical(chord)
  chord = chord:match("^%s*(.-)%s*$")
  local modifiers, key = chord:match("^(.-),%s*(.+)$")
  if not modifiers then
    key = chord:match("([^+%s]+)%s*$") or chord
    modifiers = chord:sub(1, #chord - #key)
  end
  local names, seen = {}, {}
  for token in modifiers:upper():gmatch("[%w_]+") do
    local name = token == "MOD4" and "SUPER" or token == "MOD1" and "ALT" or token
    if not seen[name] then
      names[#names + 1], seen[name] = name, true
    end
  end
  table.sort(names)
  return table.concat(names, " ") .. "," .. key:upper()
end

local function nativeKeys(chord)
  local modifiers, key = chord:match("^(.-),%s*(.+)$")
  if not modifiers then
    return chord
  end
  modifiers = modifiers:gsub("%+", " "):match("^%s*(.-)%s*$")
  return modifiers ~= "" and (modifiers:gsub("%s+", " + ") .. " + " .. key) or key
end

local function alive(record)
  return record.handle:is_enabled() == true
end

local function restore()
  for _, item in ipairs(manager.owned) do
    item:remove()
  end
  for _, item in ipairs(manager.disabled) do
    item:set_enabled(true)
  end
  manager.owned, manager.disabled, manager.conflicts = {}, {}, {}
end

local function disable(record)
  if alive(record) then
    record.handle:set_enabled(false)
    manager.disabled[#manager.disabled + 1] = record.handle
  end
end

local function legacyTail(command)
  return command and command:match("^%s*noctalia%s+msg%s+([%w_%- ]-)%s*$")
end

local function translated(command)
  local tail = manager.migrate and legacyTail(command)
  if tail == "window-switcher" then
    return hl.dsp.window.cycle_next()
  end
  return manager.nativeExec(tail and manager.legacy[tail] or command)
end

manager.execWrapper = function(command, ...)
  -- Preserve exec options and all unrelated commands verbatim.
  local handler
  if select("#", ...) == 0 and manager.migrate and legacyTail(command) then
    handler = translated(command)
  else
    handler = manager.nativeExec(command, ...)
  end
  manager.commands[handler] = command
  return handler
end
hl.dsp.exec_cmd = manager.execWrapper

manager.bindWrapper = function(keys, handler, options)
  local handle = manager.nativeBind(keys, handler, options)
  if manager.stopped then
    return handle
  end
  if #manager.records >= 4096 then
    manager.overflow = true
    return handle
  end
  local submap = handle.submap or ""
  local key = canonical(keys)
  manager.records[#manager.records + 1] = {
    handle = handle, handler = handler, options = copy(options), keys = keys,
    key = key, submap = submap, source = submap .. "|" .. key,
    command = manager.commands[handler] or "",
  }
  return handle
end
hl.bind = manager.bindWrapper

function manager.begin(runtimePath)
  restore()
  manager.records, manager.legacy = {}, {}
  manager.migrate, manager.overflow, manager.stopped = false, false, false
  manager.runtimePath = runtimePath or ""
end

function manager.stop()
  restore()
  manager.migrate, manager.stopped = false, true
  if hl.bind == manager.bindWrapper then
    hl.bind = manager.nativeBind
  end
  if hl.dsp.exec_cmd == manager.execWrapper then
    hl.dsp.exec_cmd = manager.nativeExec
  end
  _G.HyprLarpBinds = nil
end

local function register(chord, handler, options, submap)
  local function create()
    local handle = manager.nativeBind(nativeKeys(chord), handler, options)
    manager.owned[#manager.owned + 1] = handle
  end
  if submap and submap ~= "" then
    hl.define_submap(submap, create)
  else
    create()
  end
end

local function collision(key, submap, source)
  for _, record in ipairs(manager.records) do
    if record.key == key and record.submap == submap and record.source ~= source and alive(record) then
      return record
    end
  end
end

function manager.apply(definitions, legacy, migrate, shellLegacy)
  restore()
  manager.legacy, manager.migrate = legacy, migrate
  if manager.overflow then
    manager.migrate = false
    manager.conflicts = { { chord = "", command = "Más de 4096 binds: se conservan todos los originales" } }
    return
  end
  local customized = {}
  for _, entry in ipairs(definitions) do
    if entry.source ~= "" then
      customized[entry.source] = true
    end
  end
  -- Migrate only recognized Noctalia actions; other native handlers keep priority.
  if migrate then
    for _, record in ipairs(manager.records) do
      local tail = legacyTail(record.command)
      if not customized[record.source] and alive(record) and tail and (legacy[tail] or tail == "window-switcher") then
        disable(record)
        if not shellLegacy[tail] then
          register(record.keys, translated(record.command), record.options, record.submap)
        end
      end
    end
  end
  for _, entry in ipairs(definitions) do
    local sources = {}
    for _, record in ipairs(manager.records) do
      if entry.source ~= "" and record.source == entry.source then
        sources[#sources + 1] = record
      end
    end
    local submap = sources[1] and sources[1].submap or ""
    local occupied = collision(canonical(entry.chord), submap, entry.source)
    if entry.source ~= "" and #sources == 0 then
      manager.conflicts[#manager.conflicts + 1] = { id = entry.id, chord = entry.chord, command = "El bind original ya no existe; actualiza la lista" }
    elseif entry.enabled and occupied and not entry.replace then
      manager.conflicts[#manager.conflicts + 1] = { id = entry.id, chord = entry.chord, command = occupied.command ~= "" and occupied.command or "Acción de Hyprland en tu archivo" }
    else
      for _, record in ipairs(sources) do
        disable(record)
      end
      if entry.enabled then
        if entry.replace then
          for _, record in ipairs(manager.records) do
            if record.key == canonical(entry.chord) and record.submap == submap then
              disable(record)
            end
          end
        end
        if entry.type == "inherit" then
          for _, record in ipairs(sources) do
            local options = copy(record.options)
            options.description = "HyprLarp/" .. entry.id .. ": " .. entry.name
            register(entry.chord, manager.migrate and legacyTail(record.command) and translated(record.command) or record.handler, options, submap)
          end
        else
          register(entry.chord, manager.nativeExec(entry.command), {
            description = "HyprLarp/" .. entry.id .. ": " .. entry.name,
            locked = entry.locked, repeating = entry["repeat"], release = entry.release,
          }, submap)
        end
      end
    end
  end
end

local function quote(value)
  return '"' .. tostring(value):gsub('[%z\1-\31\\"]', function(character)
    if character == '"' or character == "\\" then
      return "\\" .. character
    end
    return string.format("\\u%04x", character:byte())
  end) .. '"'
end

function manager.snapshot()
  local entries, seen = {}, {}
  for _, record in ipairs(manager.records) do
    if not seen[record.source] and #entries < 1024 then
      seen[record.source] = true
      local key = record.handle.key
      local mods = {}
      for _, item in ipairs({ { "SUPER", 64 }, { "CTRL", 4 }, { "ALT", 8 }, { "SHIFT", 1 }, { "MOD2", 16 }, { "MOD3", 32 }, { "MOD5", 128 } }) do
        if record.handle.modmask & item[2] ~= 0 then
          mods[#mods + 1] = item[1]
        end
      end
      if key == "" then
        key = record.handle.keycode > 0 and ("code:" .. record.handle.keycode) or record.keys:match("([^+%s]+)%s*$")
      end
      entries[#entries + 1] = "{" .. '"source":' .. quote(record.source) .. ',"chord":' .. quote(table.concat(mods, " ") .. ", " .. key)
        .. ',"command":' .. quote(record.command:sub(1, 4096)) .. ',"submap":' .. quote(record.submap)
        .. ',"enabled":' .. tostring(alive(record)) .. "}"
    end
  end
  local conflicts = {}
  for _, item in ipairs(manager.conflicts) do
    conflicts[#conflicts + 1] = '{"chord":' .. quote(item.chord) .. ',"command":' .. quote(item.command) .. "}"
  end
  return '{"available":true,"bindings":[' .. table.concat(entries, ",") .. '],"conflicts":[' .. table.concat(conflicts, ",") .. "]}"
end

return manager
