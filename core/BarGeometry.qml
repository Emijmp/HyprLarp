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
  // A positive layer-shell exclusive zone needs one edge or three anchors.
  // Stretch along the bar using complementary margins to keep its chosen length.
  readonly property var windowAnchors: ({
      top: vertical || position === "top",
      bottom: vertical || position === "bottom",
      left: !vertical || position === "left",
      right: !vertical || position === "right"
    })
  readonly property bool reserveSpace: configuration.barReserveSpace !== false && configuration.barEnabled !== false
  readonly property int exclusiveZone: reserveSpace ? size + edgeMargin : 0
  function length(extent) {
    const available = Math.max(1, extent - (vertical ? margins.top + margins.bottom : margins.left + margins.right));
    return Math.round(available * (configuration.barLength ?? 100) / 100);
  }
  function offset(extent) {
    const start = vertical ? margins.top : margins.left;
    const end = vertical ? margins.bottom : margins.right;
    return start + Math.round(Math.max(0, extent - start - end - length(extent)) * alignment);
  }
  function windowMargins(width, height) {
    return {
      top: vertical ? offset(height) : margins.top,
      bottom: vertical ? Math.max(0, height - offset(height) - length(height)) : margins.bottom,
      left: vertical ? margins.left : offset(width),
      right: vertical ? margins.right : Math.max(0, width - offset(width) - length(width))
    };
  }
}
