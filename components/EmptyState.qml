import QtQuick
import QtQuick.Layouts
import "../core"

ColumnLayout {
  property string icon: "grid"
  property string title: "Sin entradas"
  property string description: ""
  spacing: 8
  Layout.fillWidth: true
  Label {
    text: parent.title
    font.pixelSize: 13
    Layout.fillWidth: true
    Layout.topMargin: 8
  }
  Label {
    visible: text !== ""
    text: parent.description
    color: Theme.muted
    wrapMode: Text.WordWrap
    Layout.fillWidth: true
    Layout.bottomMargin: 8
    font.pixelSize: 12
  }
}
