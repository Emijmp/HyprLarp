import QtQuick
import QtQuick.Controls

ComboBox {
  id: root

  property var look: ({})

  implicitHeight: Math.max(42 * (root.look.textScale || 1), root.look.largeTargets ? 44 : 0)
  font.family: look.font || "Inter"
  font.pixelSize: Math.round(13 * (root.look.textScale || 1))
  textRole: "name"
  leftPadding: 12
  rightPadding: 32

  background: Rectangle {
    color: root.look.raised || "#101010"
    radius: Math.min(8, root.look.radius || 0)
    border.width: root.activeFocus ? 2 : 1
    border.color: root.activeFocus ? (root.look.accent || "#ffffff") : (root.look.border || "#ffffff")
    opacity: root.enabled ? 1 : 0.45
  }

  contentItem: Text {
    text: root.displayText
    textFormat: Text.PlainText
    font: root.font
    color: root.look.text || "#ffffff"
    verticalAlignment: Text.AlignVCenter
    elide: Text.ElideRight
  }

  indicator: Text {
    x: root.width - width - 12
    anchors.verticalCenter: parent.verticalCenter
    text: "⌄"
    font.pixelSize: Math.round(17 * (root.look.textScale || 1))
    color: root.look.muted || "#a0a0a0"
  }

  delegate: ItemDelegate {
    required property int index
    required property var modelData

    width: root.width - 2
    implicitHeight: Math.max(42 * (root.look.textScale || 1), root.look.largeTargets ? 44 : 0)
    highlighted: root.highlightedIndex === index

    contentItem: Text {
      text: modelData.name
      textFormat: Text.PlainText
      font: root.font
      color: parent.highlighted ? (root.look.onAccent || "#000000") : (root.look.text || "#ffffff")
      verticalAlignment: Text.AlignVCenter
      elide: Text.ElideRight
    }

    background: Rectangle {
      color: parent.highlighted ? (root.look.accent || "#ffffff") : (root.look.surface || "#000000")
    }
  }

  popup: Popup {
    y: root.height + 5
    width: root.width
    padding: 1
    implicitHeight: Math.min(240, contentItem.implicitHeight + 2)

    background: Rectangle {
      color: root.look.surface || "#000000"
      border.color: root.look.border || "#ffffff"
      border.width: 1
      radius: Math.min(8, root.look.radius || 0)
    }

    contentItem: ListView {
      clip: true
      implicitHeight: contentHeight
      model: root.popup.visible ? root.delegateModel : null
      currentIndex: root.highlightedIndex

      ScrollIndicator.vertical: ScrollIndicator {}
    }
  }
}
