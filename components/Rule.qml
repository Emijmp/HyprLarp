import QtQuick
import QtQuick.Layouts
import "../core"

Rectangle {
  visible: Theme.detail("separators")
  implicitHeight: 1
  Layout.fillWidth: true
  color: Theme.separator
}
