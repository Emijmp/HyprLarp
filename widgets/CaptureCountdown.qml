import QtQuick
import QtQuick.Layouts
import "../core"
import "../components"

Rectangle {
  visible: ShellState.captureRemaining > 0
  color: Theme.surface
  border.width: 1
  border.color: Theme.border
  implicitWidth: contents.implicitWidth + 24
  implicitHeight: contents.implicitHeight + 20
  RowLayout {
    id: contents
    anchors.centerIn: parent
    Label {
      text: "Captura en " + ShellState.captureRemaining + " s"
      font.family: Theme.mono
    }
    ActionButton {
      text: "Cancelar"
      onClicked: ShellState.cancelCapture()
    }
  }
}
