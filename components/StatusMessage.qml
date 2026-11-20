import QtQuick
import QtQuick.Layouts
import Quickshell
import "../core"
import "." as Controls

RowLayout {
  id: root
  property string text: ""
  property bool error: false
  property int fontSize: 11
  property bool copied: false
  onTextChanged: {
    copied = false;
    if (visible && text)
      Accessible.announce(text, root.error ? Accessible.Assertive : Accessible.Polite);
  }
  Accessible.role: root.error ? Accessible.AlertMessage : Accessible.StaticText
  Accessible.name: text
  onVisibleChanged: if (visible && text)
    Accessible.announce(text, root.error ? Accessible.Assertive : Accessible.Polite)
  function copyError() {
    Quickshell.clipboardText = text;
    copied = true;
    copiedTimer.restart();
  }
  Layout.fillWidth: true
  spacing: 10

  Controls.Icon {
    visible: root.error
    name: "error"
    color: Theme.text
    Layout.preferredWidth: 32
    Layout.preferredHeight: 32
    Layout.alignment: Qt.AlignTop
  }
  Controls.Label {
    objectName: "status-message-text"
    text: root.text
    color: root.error ? Theme.text : Theme.muted
    wrapMode: Text.WordWrap
    Layout.fillWidth: true
    font.pixelSize: Theme.fontPx(root.fontSize)
  }
  Controls.ActionButton {
    objectName: "copy-error"
    visible: root.error && root.text !== ""
    text: root.copied ? "Copiado" : "Copiar"
    hint: "Copiar mensaje de error"
    Layout.alignment: Qt.AlignTop
    onClicked: root.copyError()
  }
  Timer {
    id: copiedTimer
    interval: 2000
    onTriggered: root.copied = false
  }
}
