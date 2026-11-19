import QtQuick
import QtQuick.Layouts
import "../core"

ColumnLayout {
  id: root
  property string title: ""
  property bool settingsControl: true
  property real value: 0
  property real from: 0
  property real to: 100
  property real step: 1
  property string suffix: " px"
  property string displayValue: String(Math.round(value)) + suffix
  readonly property real inputScale: to === 1 && step < 1 ? 100 : 1
  signal edited(real value)
  spacing: 5
  Layout.fillWidth: true
  opacity: enabled ? 1 : 0.4
  RowLayout {
    Label {
      text: root.title
      Layout.fillWidth: true
      wrapMode: Text.WordWrap
      font.pixelSize: Theme.fontPx(12)
    }
    Field {
      id: number
      Layout.preferredWidth: Theme.px(64)
      implicitHeight: Theme.controlHeight(26)
      Accessible.name: root.title + " · valor numérico"
      horizontalAlignment: TextInput.AlignRight
      font.family: Theme.mono
      font.pixelSize: Theme.fontPx(11)
      text: String(Math.round(root.value * root.inputScale * 100) / 100)
      validator: DoubleValidator {
        bottom: root.from * root.inputScale
        top: root.to * root.inputScale
        decimals: 2
        locale: "C"
      }
      onEditingFinished: {
        const parsed = Number(text) / root.inputScale;
        if (acceptableInput && Number.isFinite(parsed))
          root.edited(Math.max(root.from, Math.min(root.to, Math.round(parsed / root.step) * root.step)));
        text = Qt.binding(() => String(Math.round(root.value * root.inputScale * 100) / 100));
      }
    }
    Label {
      text: root.displayValue
      font.family: Theme.mono
      font.pixelSize: Theme.fontPx(10)
      color: Theme.muted
    }
  }
  LevelSlider {
    Accessible.name: root.title
    Accessible.description: root.displayValue
    settingsControl: root.settingsControl
    Layout.fillWidth: true
    from: root.from
    to: root.to
    stepSize: root.step
    value: root.value
    onMoved: root.edited(value)
  }
}
