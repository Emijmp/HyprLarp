pragma Singleton
import QtQuick
import Quickshell
import "accessibility.js" as Accessibility

Singleton {
  id: root
  readonly property var fallback: ({
      name: "AMOLED Black",
      background: "#000000",
      surface: "#000000",
      raised: "#101010",
      moduleSurface: "#141414",
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
  readonly property bool highContrast: !!Bridge.settings.accessibilityHighContrast
  readonly property real textScale: Bridge.settings.accessibilityTextScale || 1
  readonly property bool largeTargets: !!Bridge.settings.accessibilityLargeTargets
  // Reuse the shell clock so sleep/resume and wall-clock changes update the
  // theme without a second timer. Tests may still override this property.
  property int localMinute: Clock.date.getHours() * 60 + Clock.date.getMinutes()
  readonly property string scheduledTheme: {
    if (!Bridge.settings.themeScheduleEnabled)
      return Bridge.settings.theme || "amoled";
    const [dayHour, dayMinute] = String(Bridge.settings.themeDayStart || "07:00").split(":").map(Number);
    const [nightHour, nightMinute] = String(Bridge.settings.themeNightStart || "19:00").split(":").map(Number);
    const minute = localMinute;
    const day = dayHour * 60 + dayMinute;
    const night = nightHour * 60 + nightMinute;
    const isDay = day <= night ? minute >= day && minute < night : minute >= day || minute < night;
    return isDay ? Bridge.settings.themeDay || "paper" : Bridge.settings.themeNight || "amoled";
  }
  readonly property var basePalette: palettes[scheduledTheme] || fallback
  readonly property var palette: Accessibility.palette(basePalette, highContrast)
  readonly property color background: palette.background
  readonly property color surface: palette.surface
  readonly property color raised: palette.raised
  readonly property color moduleSurface: palette.moduleSurface || palette.raised
  readonly property color border: palette.border
  readonly property color separator: palette.separator
  readonly property color text: palette.text
  readonly property color muted: palette.muted
  readonly property color green: text
  readonly property color accent: safeAccent(highContrast || scheduledTheme === "custom" || (Bridge.settings.themeScheduleEnabled && scheduledTheme !== Bridge.settings.theme) ? palette.accent : Bridge.settings.accent || palette.accent)
  readonly property color onAccent: Accessibility.contrastText(String(accent))
  readonly property color danger: palette.danger
  readonly property string font: Bridge.settings.font || "Inter"
  readonly property string mono: "JetBrains Mono"
  readonly property int radius: Math.min(8, Bridge.settings.radius || 0)
  readonly property bool decorated: (Bridge.settings.decoration || "subtle") === "subtle"
  readonly property int duration: Bridge.settings.animations && !Bridge.settings.accessibilityReducedMotion && Bridge.settings.performanceMode !== "efficient" ? 80 : 0
  readonly property bool effectsEnabled: Bridge.settings.performanceMode !== "efficient" && !highContrast
  readonly property bool blurEnabled: !!Bridge.settings.panelBlur && Bridge.settings.panelStyle === "glass" && effectsEnabled
  function px(size) {
    return Math.round(size * textScale);
  }
  function fontPx(size) {
    return px(Math.max(size, Number(Bridge.settings.accessibilityMinimumFontSize || 12)));
  }
  function safeAccent(color) {
    return Accessibility.ensureContrast(String(color), [palette.surface, palette.raised, palette.moduleSurface || palette.raised], highContrast ? 7 : 4.5);
  }
  function controlHeight(size) {
    return Math.max(px(size), largeTargets ? 44 : size);
  }
  function detail(name) {
    return decorated && (Bridge.settings.decorationOptions || {})[name] !== false;
  }
  function setDetail(name, enabled) {
    Bridge.configure("decorationOptions", Object.assign({}, Bridge.settings.decorationOptions || {}, {
      [name]: enabled
    }));
  }
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
    return Qt.rgba(color.r, color.g, color.b, highContrast ? 1 : amount);
  }
  function opacityFor(module, configuration) {
    const cfg = configuration || Bridge.settings;
    if (highContrast)
      return 1;
    const overrides = cfg.moduleOpacities || {};
    return overrides[module] === undefined ? (cfg.moduleOpacity ?? 1) : overrides[module];
  }
  function apply(name) {
    if (palettes[name])
      Bridge.configureMany({
        theme: name,
        accent: palettes[name].accent,
        themeScheduleEnabled: false
      });
  }
  function customize() {
    const copy = Object.assign({}, basePalette, {
      name: "Mi " + basePalette.name,
      accent: String(accent)
    });
    Bridge.configureMany({
      theme: "custom",
      customPalette: copy,
      accent: copy.accent,
      themeScheduleEnabled: false
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
