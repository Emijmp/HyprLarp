pragma Singleton
import QtQuick
import Quickshell

Singleton {
  readonly property var enabledModules: Array.from(new Set((Bridge.preview ? [""] : Quickshell.screens.map(screen => screen.name)).reduce((all, name) => {
    const bar = forName(name);
    return bar.barEnabled === false ? all : all.concat(bar.barModules || []);
  }, []))).filter(name => !(Bridge.settings.disabledModules || []).includes(name))
  function forName(name) {
    return Object.assign({}, Bridge.settings, name ? (Bridge.settings.monitorBars || {})[name] || {} : {});
  }
  function forScreen(screen) {
    return forName(screen ? screen.name : "");
  }
  function modules(configuration, zone) {
    const zones = configuration.barZones || {
      start: configuration.barModules || [],
      center: [],
      end: []
    };
    return (zones[zone] || []).filter(name => !(Bridge.settings.disabledModules || []).includes(name));
  }
  readonly property string position: Bridge.settings.barPosition || "top"
  readonly property bool vertical: position === "left" || position === "right"
  readonly property int size: Bridge.settings.barSize ?? 34
  readonly property var margins: Bridge.settings.barMargins || ({
      top: 8,
      right: 8,
      bottom: 8,
      left: 8
    })
  readonly property int paddingX: Bridge.settings.barPaddingX ?? 8
  readonly property int paddingY: Bridge.settings.barPaddingY ?? 3
  readonly property int spacing: Bridge.settings.barSpacing ?? 10
  readonly property int border: Bridge.settings.barBorderWidth ?? 1
  readonly property int iconSize: Bridge.settings.barIconSize ?? 14
  readonly property int fontSize: Bridge.settings.barFontSize ?? 12
  readonly property real alignment: Bridge.settings.barAlignment === "end" ? 1 : Bridge.settings.barAlignment === "center" ? 0.5 : 0
  readonly property int edgeMargin: margins[position]
  function length(extent) {
    const available = Math.max(1, extent - (vertical ? margins.top + margins.bottom : margins.left + margins.right));
    return Math.round(available * (Bridge.settings.barLength ?? 100) / 100);
  }
  function offset(extent) {
    const start = vertical ? margins.top : margins.left;
    const end = vertical ? margins.bottom : margins.right;
    return start + Math.round(Math.max(0, extent - start - end - length(extent)) * alignment);
  }
}
