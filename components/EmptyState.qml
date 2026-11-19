import QtQuick
import QtQuick.Layouts
import Quickshell
import "../core"
import "." as Controls

ColumnLayout {
  id: root
  property string icon: "grid"
  property bool error: false
  property string title: "Sin entradas"
  property string description: ""
  property bool copied: false
  onDescriptionChanged: copied = false
  onTitleChanged: copied = false
  spacing: 8
  Layout.fillWidth: true
  Controls.Icon {
    visible: root.error
    name: "error"
    color: Theme.text
    Layout.preferredWidth: 104
    Layout.preferredHeight: 104
    Layout.alignment: Qt.AlignHCenter
    Layout.topMargin: 12
  }
  Label {
    text: root.title
    horizontalAlignment: root.error ? Text.AlignHCenter : Text.AlignLeft
    font.pixelSize: Theme.fontPx(13)
    Layout.fillWidth: true
    Layout.topMargin: 8
  }
  Label {
    visible: text !== ""
    text: root.description
    horizontalAlignment: root.error ? Text.AlignHCenter : Text.AlignLeft
    color: Theme.muted
    wrapMode: Text.WordWrap
    Layout.fillWidth: true
    Layout.bottomMargin: 8
    font.pixelSize: Theme.fontPx(12)
  }
  Controls.ActionButton {
    visible: root.error
    text: root.copied ? "Copiado" : "Copiar error"
    Layout.alignment: Qt.AlignHCenter
    onClicked: {
      Quickshell.clipboardText = root.title + (root.description ? "\n" + root.description : "");
      root.copied = true;
    }
  }
}
