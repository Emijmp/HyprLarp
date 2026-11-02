import QtQuick

QtObject {
  property var configuration: Bridge.settings
  readonly property string position: configuration.barPosition || "top"
  readonly property bool vertical: position === "left" || position === "right"
  readonly property int size: configuration.barSize ?? 34
  readonly property var margins: configuration.barMargins || ({
      top: 8,
      right: 8,
      bottom: 8,
      left: 8
    })
  readonly property int paddingX: configuration.barPaddingX ?? 8
  readonly property int paddingY: configuration.barPaddingY ?? 3
  readonly property int spacing: configuration.barSpacing ?? 10
  readonly property int border: configuration.barBorderWidth ?? 1
  readonly property int iconSize: configuration.barIconSize ?? 14
  readonly property int fontSize: configuration.barFontSize ?? 12
  readonly property real alignment: configuration.barAlignment === "end" ? 1 : configuration.barAlignment === "center" ? 0.5 : 0
  readonly property int edgeMargin: margins[position]
  function length(extent) {
    const available = Math.max(1, extent - (vertical ? margins.top + margins.bottom : margins.left + margins.right));
    return Math.round(available * (configuration.barLength ?? 100) / 100);
  }
  function offset(extent) {
    const start = vertical ? margins.top : margins.left;
    const end = vertical ? margins.bottom : margins.right;
    return start + Math.round(Math.max(0, extent - start - end - length(extent)) * alignment);
  }
}
