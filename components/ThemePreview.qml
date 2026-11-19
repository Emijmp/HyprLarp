import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../core"
import "../core/accessibility.js" as Accessibility

Rectangle {
  id: root
  objectName: "theme-preview-card"
  required property string themeId
  required property var palette
  property bool selected: false
  readonly property var displayPalette: Accessibility.palette(palette, Theme.highContrast)
  readonly property string displayAccent: Accessibility.ensureContrast(displayPalette.accent, [displayPalette.surface, displayPalette.raised, displayPalette.moduleSurface || displayPalette.raised], 4.5)
  signal applyRequested(string themeId)
  implicitWidth: 260
  implicitHeight: body.implicitHeight + 20
  radius: Theme.radiusFor("panel")
  color: displayPalette.background
  border.width: selected ? 2 : 1
  border.color: root.selected ? root.displayAccent : root.displayPalette.border
  ColumnLayout {
    id: body
    anchors.top: parent.top
    anchors.left: parent.left
    anchors.right: parent.right
    anchors.margins: 10
    spacing: 8
    Rectangle {
      Layout.fillWidth: true
      height: Theme.px(22)
      radius: 4
      color: root.displayPalette.surface
      border.width: 1
      border.color: root.displayPalette.border
      RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 7
        anchors.rightMargin: 7
        spacing: 5
        Repeater {
          model: 3
          Rectangle {
            required property int index
            width: Theme.px(7)
            height: Theme.px(7)
            radius: width / 2
            color: [root.displayAccent, root.displayPalette.muted, root.displayPalette.danger][index]
          }
        }
        Item {
          Layout.fillWidth: true
        }
        Rectangle {
          width: 38
          height: 4
          radius: 2
          color: root.displayPalette.text
          opacity: 0.7
        }
      }
    }
    Rectangle {
      Layout.fillWidth: true
      implicitHeight: panelContent.implicitHeight + 16
      radius: 5
      color: root.displayPalette.raised
      ColumnLayout {
        id: panelContent
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.margins: 8
        spacing: 5
        Label {
          text: root.displayPalette.name
          color: root.displayPalette.text
          font.pixelSize: Theme.fontPx(12)
          font.weight: Font.DemiBold
          Layout.fillWidth: true
          wrapMode: Text.WordWrap
        }
        Label {
          text: "Texto · estado · panel"
          color: root.displayPalette.muted
          font.pixelSize: Theme.fontPx(10)
          Layout.fillWidth: true
          wrapMode: Text.WordWrap
        }
        Rectangle {
          width: 68
          height: 5
          radius: 2
          color: root.displayAccent
        }
      }
    }
    RowLayout {
      Layout.fillWidth: true
      Label {
        text: root.selected ? "Activo" : root.themeId
        color: root.displayPalette.muted
        font.pixelSize: Theme.fontPx(10)
        Layout.fillWidth: true
        wrapMode: Text.WordWrap
      }
      Button {
        id: applyButton
        text: "Aplicar"
        Accessible.name: "Aplicar tema " + root.displayPalette.name
        onClicked: root.applyRequested(root.themeId)
        contentItem: Text {
          text: applyButton.text
          color: Accessibility.contrastText(root.displayAccent)
          horizontalAlignment: Text.AlignHCenter
          verticalAlignment: Text.AlignVCenter
          font.family: Theme.font
          font.pixelSize: Theme.fontPx(10)
        }
        background: Rectangle {
          implicitWidth: applyButton.contentItem.implicitWidth + 20
          implicitHeight: Theme.controlHeight(28)
          radius: Theme.radiusFor("button")
          color: root.displayAccent
          border.width: applyButton.activeFocus ? 2 : 0
          border.color: root.displayPalette.text
        }
      }
    }
  }
}
