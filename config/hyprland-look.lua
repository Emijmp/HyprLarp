-- Optional compositor styling for Hyprland 0.57+.
hl.config({
  general = {
    gaps_in = 4,
    gaps_out = 8,
    border_size = 1,
    col = {
      active_border = "rgb(ffffff)",
      inactive_border = "rgb(ffffff)",
    },
  },
  decoration = {
    rounding = 0,
    shadow = { enabled = false },
  },
})

-- Apply optional spacing after the base style so it also survives reloads.
if rawget(_G, "HyprLarpApplyWindowGaps") then
  HyprLarpApplyWindowGaps()
end
