pragma Singleton
import QtQuick
import Quickshell

Singleton {
  readonly property var fallback: ({
      name: "AMOLED Black",
      background: "#000000",
      surface: "#000000",
      raised: "#101010",
      border: "#ffffff",
      separator: "#292929",
      text: "#ffffff",
      muted: "#a0a0a0",
      accent: "#ffffff",
      danger: "#ffffff"
    })
  readonly property var palettes: Object.assign({}, Object.keys(Bridge.palettes).length ? Bridge.palettes : {
    amoled: fallback
  }, {
    custom: Bridge.settings.customPalette || Object.assign({}, fallback, {
      name: "Mi tema"
    })
  })
  readonly property var palette: palettes[Bridge.settings.theme || "amoled"] || fallback
  readonly property color background: palette.background
  readonly property color surface: palette.surface
  readonly property color raised: palette.raised
  readonly property color moduleSurface: palette.moduleSurface || palette.raised
  readonly property color border: palette.border
  readonly property color separator: palette.separator
  readonly property color text: palette.text
  readonly property color muted: palette.muted
  readonly property color green: text
  readonly property color accent: Bridge.settings.theme === "custom" ? palette.accent : Bridge.settings.accent || palette.accent
  readonly property color danger: palette.danger
  readonly property string font: Bridge.settings.font || "Inter"
  readonly property string mono: "JetBrains Mono"
  readonly property int radius: Math.min(8, Bridge.settings.radius || 0)
  readonly property bool decorated: (Bridge.settings.decoration || "subtle") === "subtle"
  readonly property int duration: Bridge.settings.animations ? 80 : 0
  function radiusFor(kind) {
    const overrides = Bridge.settings.cornerRadii || {};
    return Math.max(0, Math.min(8, overrides[kind] ?? radius));
  }
  function setRadius(kind, value) {
    const next = Object.assign({}, Bridge.settings.cornerRadii || {});
    if (value === null)
      delete next[kind];
    else
      next[kind] = value;
    Bridge.configure("cornerRadii", next);
  }
  function alpha(color, amount) {
    return Qt.rgba(color.r, color.g, color.b, amount);
  }
  function opacityFor(module, configuration) {
    const cfg = configuration || Bridge.settings;
    const overrides = cfg.moduleOpacities || {};
    return overrides[module] === undefined ? (cfg.moduleOpacity ?? 1) : overrides[module];
  }
  function apply(name) {
    if (palettes[name])
      Bridge.configureMany({
        theme: name,
        accent: palettes[name].accent
      });
  }
  function customize() {
    const copy = Object.assign({}, palette, {
      name: "Mi " + palette.name,
      accent: String(accent)
    });
    Bridge.configureMany({
      theme: "custom",
      customPalette: copy,
      accent: copy.accent
    });
  }
  function setCustom(key, value) {
    const next = Object.assign({}, palettes.custom, {
      [key]: value
    });
    const updates = {
      customPalette: next
    };
    if (key === "accent")
      updates.accent = value;
    Bridge.configureMany(updates);
  }
}
