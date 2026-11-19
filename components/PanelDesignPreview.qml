import QtQuick
import QtQuick.Layouts
import "../core"
import "../core/panelGeometry.js" as Geometry
import "../core/paths.js" as Paths

ColumnLayout {
  id: root
  objectName: "panel-design-preview"
  property string layoutMode: "floating"
  property string surfaceStyle: "standard"
  property real previewOpacity: 1
  property bool blur: false
  readonly property real logicalWidth: ShellState.activeScreen?.width || 1280
  readonly property real logicalHeight: ShellState.activeScreen?.height || 720
  readonly property var options: ({
      layoutMode: layoutMode,
      panelName: "control",
      position: barLayout.position,
      gap: barLayout.configuration.barEnabled !== false ? barLayout.size + barLayout.edgeMargin + 8 : 8,
      margins: barLayout.margins
    })
  readonly property var area: Geometry.availableArea(logicalWidth, logicalHeight, options)
  readonly property real panelWidth: Geometry.widthFor(area, layoutMode, Theme.px(360), Theme.textScale)
  readonly property var surfaceGeometry: Geometry.place(area, panelWidth, panelBody.implicitHeight + 28, options)
  readonly property bool effectiveBlur: blur && surfaceStyle === "glass" && Theme.effectsEnabled
  spacing: 8
  implicitWidth: 420
  Accessible.role: Accessible.Pane
  Accessible.name: "Vista previa del diseño del panel"
  Accessible.description: "Muestra proporcional de la pantalla. " + detail.text
  BarGeometry {
    id: barLayout
    configuration: BarLayout.forScreen(ShellState.activeScreen)
  }
  Rectangle {
    id: screenFrame
    Layout.fillWidth: true
    implicitHeight: width * root.logicalHeight / root.logicalWidth
    color: Theme.background
    radius: 8
    clip: true
    Item {
      id: scene
      width: root.logicalWidth
      height: root.logicalHeight
      scale: screenFrame.width / root.logicalWidth
      transformOrigin: Item.TopLeft
      Image {
        objectName: "preview-wallpaper"
        anchors.fill: parent
        source: Bridge.settings.wallpaperProvider !== "external" && Bridge.settings.wallpaper ? Paths.fileUrl(Bridge.settings.wallpaper) : ""
        sourceSize.width: 960
        sourceSize.height: 540
        fillMode: Image.PreserveAspectCrop
        asynchronous: true
        visible: status === Image.Ready
      }
      Rectangle {
        anchors.fill: parent
        color: Theme.background
        opacity: 0.3
      }
      Rectangle {
        readonly property var placement: barLayout.windowMargins(scene.width, scene.height)
        x: placement.left
        y: placement.top
        width: barLayout.vertical ? barLayout.size : barLayout.length(scene.width)
        height: barLayout.vertical ? barLayout.length(scene.height) : barLayout.size
        visible: barLayout.configuration.barEnabled !== false
        radius: Theme.radiusFor("bar")
        color: Theme.alpha(Theme.surface, barLayout.configuration.barOpacity ?? 1)
        border.width: barLayout.configuration.barBorderWidth ?? 1
        border.color: Theme.border
        Label {
          anchors.centerIn: parent
          text: barLayout.vertical ? "●\n01\n02\n03" : "HyprLarp    01  02  03                         12:45    Red    Audio"
          color: Theme.text
          font.pixelSize: barLayout.fontSize
          width: parent.width - 8
          horizontalAlignment: Text.AlignHCenter
        }
      }
      Rectangle {
        id: previewPanel
        objectName: "preview-panel-surface"
        readonly property real panelOpacity: Theme.highContrast ? 1 : root.surfaceStyle === "glass" ? Math.min(root.previewOpacity, .86) : root.previewOpacity
        x: root.surfaceGeometry.x
        y: root.surfaceGeometry.y
        width: root.surfaceGeometry.width
        height: root.surfaceGeometry.height
        radius: root.layoutMode === "sidebar" || root.surfaceStyle === "flat" ? 0 : Theme.radiusFor("panel")
        color: Qt.rgba(Theme.surface.r, Theme.surface.g, Theme.surface.b, panelOpacity)
        border.width: root.surfaceStyle === "flat" ? 0 : 1
        border.color: Theme.border
        clip: true
        ColumnLayout {
          id: panelBody
          anchors.top: parent.top
          anchors.left: parent.left
          anchors.right: parent.right
          anchors.margins: 14
          spacing: 12
          Label {
            text: "Centro de control"
            color: Theme.text
            font.pixelSize: Theme.fontPx(13)
            font.weight: Font.DemiBold
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
          }
          Rectangle {
            Layout.fillWidth: true
            height: 1
            color: Theme.separator
          }
          Label {
            text: "Volumen"
            color: Theme.muted
            font.pixelSize: Theme.fontPx(12)
            Layout.fillWidth: true
          }
          Rectangle {
            Layout.fillWidth: true
            height: Theme.controlHeight(26)
            color: Theme.raised
            radius: Theme.radiusFor("field")
            Rectangle {
              width: parent.width * .65
              height: 4
              anchors.verticalCenter: parent.verticalCenter
              color: Theme.accent
            }
          }
          Label {
            text: "Texto y controles con la escala actual"
            color: Theme.muted
            font.pixelSize: Theme.fontPx(11)
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
          }
          Rectangle {
            Layout.fillWidth: true
            implicitHeight: Math.max(Theme.controlHeight(30), actionLabel.implicitHeight + 12)
            radius: Theme.radiusFor("button")
            color: Theme.accent
            Label {
              id: actionLabel
              anchors.centerIn: parent
              width: parent.width - 16
              text: "Aplicar"
              color: Theme.onAccent
              horizontalAlignment: Text.AlignHCenter
              font.pixelSize: Theme.fontPx(12)
            }
          }
        }
      }
    }
  }
  Label {
    id: detail
    Layout.fillWidth: true
    wrapMode: Text.WordWrap
    text: (root.layoutMode === "sidebar" ? "Lateral" : root.layoutMode === "centered" ? "Centrado" : "Flotante") + " · " + ({
        standard: "Estándar",
        glass: "Vidrio",
        flat: "Plano"
      })[root.surfaceStyle] + " · " + Math.round(root.previewOpacity * 100) + "%" + (root.effectiveBlur ? " · desenfoque en el escritorio" : "")
    color: Theme.muted
    font.pixelSize: Theme.fontPx(11)
  }
}
