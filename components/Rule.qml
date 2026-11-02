import QtQuick
import QtQuick.Layouts
import "../core"

Rectangle {
  visible: Theme.detail("separators")
  implicitHeight: visible ? 1 : 0
  Layout.fillWidth: true
  color: Theme.separator
}
