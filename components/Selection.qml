import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../core"

ComboBox {
  id: root
  property var choices: []
  property var labels: []
  property string value: ""
  signal edited(string value)
  model: choices
  currentIndex: Math.max(0, choices.indexOf(value))
  implicitHeight: Theme.controlHeight(34)
  Accessible.name: objectName || "Seleccionar opción"
  implicitWidth: 250
  font.family: Theme.font
  font.pixelSize: Theme.fontPx(12)
  onActivated: index => edited(choices[index])
  contentItem: Label {
    leftPadding: 9
    rightPadding: 24
    text: root.labels[root.currentIndex] || root.choices[root.currentIndex] || ""
    color: root.enabled ? Theme.text : Theme.muted
    font.family: root.font.family
    font.pixelSize: root.font.pixelSize
    textFormat: Text.PlainText
    elide: Text.ElideRight
    verticalAlignment: Text.AlignVCenter
  }
  indicator: Label {
    x: root.width - width - 9
    y: (root.height - height) / 2
    text: "▾"
    color: Theme.muted
  }
  background: Rectangle {
    color: Theme.surface
    border.width: 1
    border.color: root.activeFocus ? Theme.border : Theme.separator
    radius: Theme.radiusFor("field")
  }
  delegate: ItemDelegate {
    required property int index
    required property string modelData
    width: root.width
    height: Theme.controlHeight(34)
    highlighted: root.highlightedIndex === index
    contentItem: Label {
      text: root.labels[index] || modelData
      color: Theme.text
      font.family: root.font.family
      font.pixelSize: root.font.pixelSize
      textFormat: Text.PlainText
      elide: Text.ElideRight
      verticalAlignment: Text.AlignVCenter
    }
    background: Rectangle {
      color: parent.highlighted ? Theme.raised : Theme.surface
    }
  }
  popup: Popup {
    y: root.height + 3
    width: root.width
    padding: 1
    implicitHeight: Math.min(280, contentItem.implicitHeight + 2)
    contentItem: ListView {
      clip: true
      implicitHeight: contentHeight
      model: root.popup.visible ? root.delegateModel : null
      currentIndex: root.highlightedIndex
      ScrollIndicator.vertical: ScrollIndicator {}
    }
    background: Rectangle {
      color: Theme.surface
      border.color: Theme.border
      border.width: 1
    }
  }
  FocusRing {
    control: root
  }
}
