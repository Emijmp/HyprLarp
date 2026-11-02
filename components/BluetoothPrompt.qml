import QtQuick
import QtQuick.Layouts
import "../core"

ColumnLayout {
  id: root
  property var request: Bridge.bluetoothPrompt
  readonly property bool needsInput: request !== null && ["pin", "passkey"].includes(request.kind)
  signal revealRequested(var item)
  visible: request !== null
  spacing: 8
  function reply(accepted) {
    if (!request || Bridge.preview || Bridge.isBusy("bluetooth-respond"))
      return;
    Bridge.perform("bluetooth-respond", {
      token: request.token,
      accepted: accepted,
      value: entry.text
    });
    entry.text = "";
  }
  onRequestChanged: if (request)
    Qt.callLater(() => {
      entry.text = "";
      if (root.needsInput)
        entry.forceActiveFocus();
      root.revealRequested(root);
    })
  SectionTitle {
    text: root.request ? root.request.name : ""
  }
  Label {
    text: !root.request ? "" : root.request.kind === "display" ? "Introduce este código en el dispositivo y pulsa Enter allí." : root.request.kind === "confirm" ? "Confirma que este código coincide con el del dispositivo." : root.needsInput ? "Introduce el código de vinculación del dispositivo." : "Permitir la vinculación con este dispositivo."
    font.pixelSize: 11
    Layout.fillWidth: true
    wrapMode: Text.WordWrap
  }
  Label {
    visible: !!root.request && !!root.request.code
    text: root.request ? root.request.code : ""
    font.family: Theme.mono
    font.pixelSize: 22
    Layout.fillWidth: true
  }
  Field {
    id: entry
    visible: root.needsInput
    Layout.fillWidth: true
    placeholderText: root.request && root.request.kind === "pin" ? "PIN" : "Código de hasta 6 dígitos"
    maximumLength: root.request && root.request.kind === "pin" ? 16 : 6
    validator: RegularExpressionValidator {
      regularExpression: root.request && root.request.kind === "passkey" ? /[0-9]{0,6}/ : /[A-Za-z0-9]{0,16}/
    }
    onAccepted: if (text.length > 0)
      root.reply(true)
  }
  RowLayout {
    ActionButton {
      text: "Cancelar"
      onClicked: Bridge.perform("bluetooth-cancel")
    }
    ActionButton {
      visible: !!root.request && root.request.kind !== "display"
      text: root.needsInput ? "Enviar código" : "Confirmar"
      enabled: !Bridge.preview && !Bridge.isBusy("bluetooth-respond") && (!root.needsInput || entry.text.length > 0)
      accent: true
      onClicked: root.reply(true)
    }
  }
  Rule {}
}
