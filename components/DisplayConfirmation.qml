import QtQuick
import QtQuick.Layouts
import "../core"
import "." as Controls

Rectangle {
  id: root
  readonly property var pending: Bridge.displays.pending
  property double now: Date.now()
  onPendingChanged: now = Date.now()
  readonly property int remaining: pending ? Math.max(0, Math.ceil(pending.deadline - now / 1000)) : 0
  visible: !!pending
  Layout.fillWidth: true
  implicitHeight: content.implicitHeight + 24
  color: Theme.surface
  border.width: 1
  border.color: Theme.accent
  radius: Theme.radiusFor("panel")
  Timer {
    interval: 250
    running: !!root.pending
    repeat: true
    onTriggered: root.now = Date.now()
  }
  ColumnLayout {
    id: content
    anchors.fill: parent
    anchors.margins: 12
    spacing: 6
    Controls.Label {
      text: "¿Se ve bien la imagen? · " + root.remaining + " s"
      font.pixelSize: Theme.fontPx(13)
      Layout.fillWidth: true
    }
    Controls.Label {
      text: "Sin confirmar se recuperará la configuración anterior."
      font.pixelSize: Theme.fontPx(11)
      color: Theme.muted
      wrapMode: Text.WordWrap
      Layout.fillWidth: true
    }
    RowLayout {
      Controls.ActionButton {
        text: "Conservar cambios"
        accent: true
        enabled: !!root.pending && !Bridge.isBusy("displays-confirm")
        onClicked: Bridge.perform("displays-confirm", {
          token: root.pending.token
        })
      }
      Controls.ActionButton {
        text: "Recuperar ahora"
        enabled: !!root.pending && !Bridge.isBusy("displays-revert")
        onClicked: Bridge.perform("displays-revert", {
          token: root.pending.token
        })
      }
    }
  }
}
