import QtQuick
import QtQuick.Controls
import "../core"

TextField {
  id: root
  implicitHeight: Theme.controlHeight(34)
  Accessible.name: placeholderText || objectName || "Campo de texto"
  Accessible.description: placeholderText || objectName || "Campo de texto"
  Accessible.passwordEdit: echoMode === TextInput.Password
  Accessible.onShowOnScreenAction: forceActiveFocus()
  leftPadding: 9
  rightPadding: 9
  font.family: Theme.font
  font.pixelSize: Theme.fontPx(12)
  color: Theme.text
  selectionColor: Theme.text
  selectedTextColor: Theme.surface
  placeholderTextColor: Theme.muted
  background: Rectangle {
    color: Theme.surface
    radius: Theme.radiusFor("field")
    border.width: 1
    border.color: root.activeFocus ? Theme.border : Theme.separator
    Rectangle {
      visible: Theme.decorated && root.activeFocus
      x: 3
      y: 3
      width: 4
      height: 1
      color: Theme.border
    }
  }
  FocusRing {
    control: root
  }
}
