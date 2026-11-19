import QtQuick
import QtQuick.Layouts
import "../core"
import "../components"

ColumnLayout {
  spacing: 12
  Component.onCompleted: Bridge.perform("displays-refresh")
  ProjectionOptions {}
  DisplayConfirmation {}
  ActionButton {
    text: "Configurar resolución y posición…"
    icon: "sliders"
    onClicked: ShellState.openSettings("Displays")
  }
  StatusMessage {
    visible: !!Bridge.displays.error
    text: Bridge.displays.error || ""
    error: true
  }
}
