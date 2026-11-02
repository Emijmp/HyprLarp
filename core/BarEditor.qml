pragma Singleton
import QtQuick
import Quickshell

Singleton {
  id: root
  property string target: ""
  readonly property var settings: BarLayout.forName(target)
  readonly property var targets: [""].concat(Array.from(new Set(Quickshell.screens.map(screen => screen.name).concat(Object.keys(Bridge.settings.monitorBars || {})).filter(Boolean))))
  readonly property var targetLabels: targets.map(name => name || "Todos · valores base")
  function minimum(settings) {
    const vertical = ["left", "right"].includes(settings.barPosition);
    return 2 * ((settings[vertical ? "barPaddingX" : "barPaddingY"] ?? 0) + (settings.barBorderWidth ?? 0) + (settings[vertical ? "modulePaddingX" : "modulePaddingY"] ?? 0) + (settings.moduleBorderWidth ?? 0)) + Math.max(settings.barIconSize ?? 14, (settings.barFontSize ?? 12) + 4);
  }
  function set(key, value) {
    configure({
      [key]: value
    });
  }
  function configure(values) {
    const patch = Object.assign({}, values);
    const next = Object.assign({}, settings, patch);
    if (patch.barZones)
      patch.barModules = [].concat(patch.barZones.start, patch.barZones.center, patch.barZones.end);
    const required = minimum(next);
    if (required > 128) {
      Bridge.toast("Reduce el padding para mantener el grosor dentro de 128 px", true);
      return;
    }
    if (next.barSize < required)
      patch.barSize = required;
    if (target) {
      const bars = Object.assign({}, Bridge.settings.monitorBars || {});
      bars[target] = Object.assign({}, bars[target] || {}, patch);
      Bridge.configure("monitorBars", bars);
    } else {
      const bars = Object.assign({}, Bridge.settings.monitorBars || {});
      let changed = false;
      for (const name of Object.keys(bars)) {
        const effective = Object.assign({}, Bridge.settings, patch, bars[name]);
        if (minimum(effective) > 128) {
          Bridge.toast("El padding de " + name + " supera el grosor máximo", true);
          return;
        }
        if (effective.barSize < minimum(effective)) {
          bars[name] = Object.assign({}, bars[name], {
            barSize: minimum(effective)
          });
          changed = true;
        }
      }
      if (changed)
        patch.monitorBars = bars;
      Bridge.configureMany(patch);
    }
  }
  function inherit() {
    if (!target)
      return;
    const bars = Object.assign({}, Bridge.settings.monitorBars || {});
    delete bars[target];
    Bridge.configure("monitorBars", bars);
  }
}
