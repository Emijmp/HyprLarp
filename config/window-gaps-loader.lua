-- Read a small data file without adding it to Hyprland's Lua include watcher.
-- Only validated numeric values reach hl.config; this file never executes data.
return function(path)
  local file = io.open(path, "r")
  if not file then
    return false
  end
  local content = file:read(1025) or ""
  file:close()
  local function invalid()
    print("HyprLarp: separación de ventanas inválida; se conservan los valores del compositor")
    return false
  end
  if #content > 1024 then
    return invalid()
  end
  local limits = { enabled = 1, inner = 64, top = 128, right = 128, bottom = 128, left = 128 }
  local data, count = {}, 0
  for line in content:gmatch("[^\r\n]+") do
    if line:sub(1, 1) ~= "#" then
      local key, value = line:match("^([a-z]+)=(%d+)$")
      local number = value and tonumber(value)
      if not key or not limits[key] or data[key] ~= nil or not number or number > limits[key] then
        return invalid()
      end
      data[key], count = number, count + 1
    end
  end
  if count ~= 6 then
    return invalid()
  end
  if data.enabled == 1 then
    hl.config({
      general = {
        gaps_in = data.inner,
        gaps_out = { top = data.top, right = data.right, bottom = data.bottom, left = data.left },
      },
    })
  end
  return true
end
