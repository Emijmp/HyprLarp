import QtQuick
import QtQuick.Layouts
import "../core"

ColumnLayout {
  id: root
  required property var node
  property bool device: false
  property bool input: false
  readonly property bool available: Audio.usable(node)
  RowLayout {
    Label {
      text: root.node.description || root.node.name
      font.pixelSize: Theme.fontPx(12)
      elide: Text.ElideRight
      Layout.fillWidth: true
    }
    ActionButton {
      visible: root.device
      text: (root.input ? Audio.source : Audio.node) === root.node ? "Actual" : "Usar"
      enabled: root.available
      onClicked: Audio.select(root.node, root.input)
    }
    ActionButton {
      icon: root.available && root.node.audio.muted ? "muted" : root.input ? "microphone" : "volume"
      hint: "Alternar silencio"
      enabled: root.available
      onClicked: Audio.setNodeMuted(root.node, !root.node.audio.muted)
    }
  }
  SettingSlider {
    settingsControl: false
    title: "Volumen"
    to: 1
    step: 0.01
    value: root.available ? root.node.audio.volume : 0
    enabled: root.available
    displayValue: Math.round(value * 100) + "%"
    onEdited: value => Audio.setNodeVolume(root.node, value)
  }
  Rule {}
}
