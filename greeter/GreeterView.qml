import QtQuick
import QtQuick.Controls
import QtQuick.Window
import QtQuick.Layouts
import Quickshell
import "." as GreeterControls

Item {
  id: root

  required property var controller
  property bool interactive: true
  readonly property var look: controller.model.appearance || ({})
  readonly property real uiScale: Math.max(1, Math.min(2, look.textScale || 1))
  readonly property color surface: look.surface || "#000000"
  readonly property color foreground: look.text || "#ffffff"
  readonly property color muted: look.muted || "#a0a0a0"
  readonly property color accent: look.accent || "#ffffff"
  readonly property string family: look.font || "Inter"
  readonly property bool centered: look.layout === "centered"
  readonly property int padding: Math.round((width < 900 ? 24 : 36) * uiScale)
  property bool showPassword: false
  readonly property string keyboardStatusText: "TECLADO · " + (controller.keyboard?.layout || "Predeterminado") + (controller.keyboard?.capsLock === true ? "  ·  Bloq Mayús activado" : "")

  function submit() {
    if (!interactive)
      return;
    const response = password.text;
    controller.submit(response);
    password.text = "";
  }
  function reveal(item) {
    if (!root.interactive || !item)
      return;
    let inside = false;
    for (let parent = item; parent; parent = parent.parent)
      if (parent === railScroll) {
        inside = true;
        break;
      }
    if (!inside)
      return;
    const y = item.mapToItem(railScroll.contentItem, 0, 0).y;
    if (y < railScroll.contentY || y + item.height > railScroll.contentY + railScroll.height)
      railScroll.contentY = Math.max(0, Math.min(y - 8, railScroll.contentHeight - railScroll.height));
  }

  Keys.enabled: interactive
  Keys.onEscapePressed: controller.cancel()
  Connections {
    target: root.Window.window
    function onActiveFocusItemChanged() {
      if (!root.interactive || !root.Window.window)
        return;
      Qt.callLater(() => root.reveal(root.Window.window.activeFocusItem));
    }
  }
  Component.onCompleted: {
    if (interactive)
      password.forceActiveFocus();
  }

  SystemClock {
    id: clock

    precision: SystemClock.Minutes
  }

  Rectangle {
    anchors.fill: parent
    color: root.look.background || "#000000"
  }

  Image {
    anchors.fill: parent
    anchors.leftMargin: root.centered ? 0 : rail.width
    source: root.look.wallpaper || ""
    cache: false
    asynchronous: true
    fillMode: root.look.fill === "fit" ? Image.PreserveAspectFit : root.look.fill === "stretch" ? Image.Stretch : root.look.fill === "center" ? Image.Pad : root.look.fill === "repeat" ? Image.Tile : Image.PreserveAspectCrop
  }

  Rectangle {
    anchors.fill: parent
    visible: root.centered
    color: root.look.background || "#000000"
    opacity: 0.2
  }

  Rectangle {
    id: rail

    x: root.centered ? (root.width - width) / 2 : 0
    y: root.centered ? (root.height - height) / 2 : 0
    width: root.centered ? Math.min(448 * root.uiScale, Math.max(0, root.width - 2 * root.padding)) : Math.min((root.width < 800 ? Math.min(350, root.width * .53) : Math.min(440, root.width * .34)) * root.uiScale, root.width < 800 ? root.width : root.width * .75)
    height: root.centered ? Math.max(0, Math.min(root.height - 2 * root.padding, brand.implicitHeight + form.implicitHeight + footer.implicitHeight + 2 * root.padding + 48)) : root.height
    color: root.surface
    radius: root.centered ? (root.look.radius || 0) : 0
    border.width: root.centered ? 1 : 0
    border.color: root.look.border || "#ffffff"

    Rectangle {
      visible: !root.centered
      anchors.right: parent.right
      width: 1
      height: parent.height
      color: root.look.border || "#ffffff"
    }

    Flickable {
      id: railScroll
      anchors.fill: parent
      anchors.margins: root.centered ? 1 : 0
      clip: true
      interactive: root.interactive
      contentWidth: width
      contentHeight: Math.max(height, brand.implicitHeight + form.implicitHeight + footer.implicitHeight + 2 * root.padding + 48)
      boundsBehavior: Flickable.StopAtBounds
      onContentHeightChanged: Qt.callLater(() => root.reveal(root.Window.window?.activeFocusItem))
      onHeightChanged: Qt.callLater(() => root.reveal(root.Window.window?.activeFocusItem))
      ScrollBar.vertical: ScrollBar {
        policy: ScrollBar.AsNeeded
      }
      RowLayout {
        id: brand

        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: root.padding
        spacing: 13

        GreeterControls.BrandIcon {
          Layout.preferredWidth: 38
          Layout.preferredHeight: 38
          color: root.accent
        }

        ColumnLayout {
          Layout.fillWidth: true
          spacing: 2

          Text {
            text: "HYPRLARP"
            color: root.foreground
            font.family: root.family
            font.pixelSize: Math.round(13 * root.uiScale)
            font.weight: Font.DemiBold
            font.letterSpacing: 2
          }

          Text {
            text: controller.model.hostname || "Inicio de sesión"
            textFormat: Text.PlainText
            color: root.muted
            font.family: root.family
            font.pixelSize: Math.round(10 * root.uiScale)
            elide: Text.ElideRight
            Layout.fillWidth: true
          }
        }

        ColumnLayout {
          visible: root.centered && brand.width >= 360 * root.uiScale
          spacing: 2

          Text {
            text: Qt.formatDateTime(clock.date, "HH:mm")
            color: root.foreground
            font.family: root.family
            font.pixelSize: Math.round(23 * root.uiScale)
            font.weight: Font.Light
            Layout.alignment: Qt.AlignRight
          }

          Text {
            text: Qt.formatDateTime(clock.date, "ddd, dd MMM")
            color: root.muted
            font.family: root.family
            font.pixelSize: Math.round(10 * root.uiScale)
            Layout.alignment: Qt.AlignRight
          }
        }
      }

      Item {
        id: formViewport

        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: brand.bottom
        anchors.bottom: footer.top
        anchors.leftMargin: root.padding
        anchors.rightMargin: root.padding
        anchors.topMargin: 24
        anchors.bottomMargin: 24

        ColumnLayout {
          id: form

          width: formViewport.width
          y: Math.max(0, (formViewport.height - implicitHeight) / 2)
          spacing: 10

          Text {
            text: "Acceder"
            font.family: root.family
            font.pixelSize: Math.round(30 * root.uiScale)
            font.weight: Font.Medium
            color: root.foreground
            Layout.bottomMargin: 20
          }

          Text {
            id: userLabel
            text: "USUARIO"
            color: root.muted
            font.family: root.family
            font.pixelSize: Math.round(10 * root.uiScale)
            font.letterSpacing: 1.5
          }

          TextField {
            id: user
            Accessible.name: "Usuario"
            Accessible.labelledBy: userLabel
            focusPolicy: root.interactive ? Qt.StrongFocus : Qt.NoFocus

            Layout.fillWidth: true
            implicitHeight: Math.max(42 * root.uiScale, root.look.largeTargets ? 44 : 0)
            text: controller.userName
            onTextEdited: controller.userName = text
            enabled: !controller.authenticating
            placeholderText: "Tu usuario"
            placeholderTextColor: root.muted
            color: root.foreground
            selectionColor: root.accent
            selectedTextColor: root.look.onAccent || "#000000"
            font.family: root.family
            font.pixelSize: Math.round(13 * root.uiScale)
            leftPadding: 12
            rightPadding: 12
            onAccepted: password.forceActiveFocus()

            background: Rectangle {
              color: root.look.raised || "#101010"
              radius: root.look.radius || 0
              border.width: user.activeFocus ? 2 : 1
              border.color: user.activeFocus ? root.accent : (root.look.border || "#ffffff")
            }
          }

          Text {
            text: "SESIÓN"
            color: root.muted
            font.family: root.family
            font.pixelSize: Math.round(10 * root.uiScale)
            font.letterSpacing: 1.5
            Layout.topMargin: 6
          }

          GreeterControls.SessionChoice {
            Accessible.name: "Sesión de escritorio"
            focusPolicy: root.interactive ? Qt.StrongFocus : Qt.NoFocus
            Layout.fillWidth: true
            look: root.look
            model: controller.model.sessions
            currentIndex: controller.sessionIndex
            onActivated: controller.sessionIndex = currentIndex
            enabled: !controller.authenticating
          }

          Text {
            id: passwordLabel
            text: controller.awaitingResponse ? controller.prompt : "CONTRASEÑA"
            textFormat: Text.PlainText
            color: root.muted
            font.family: root.family
            font.pixelSize: Math.round(10 * root.uiScale)
            font.letterSpacing: controller.awaitingResponse ? 0 : 1.5
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
            Layout.topMargin: 6
          }

          RowLayout {
            Layout.fillWidth: true
            spacing: 8

            TextField {
              id: password
              Accessible.name: controller.awaitingResponse ? controller.prompt : "Contraseña"
              Accessible.description: controller.awaitingResponse ? controller.prompt : "Contraseña"
              Accessible.labelledBy: passwordLabel
              Accessible.passwordEdit: !root.showPassword && !controller.echoResponse
              focusPolicy: root.interactive ? Qt.StrongFocus : Qt.NoFocus

              Layout.fillWidth: true
              implicitHeight: Math.max(42 * root.uiScale, root.look.largeTargets ? 44 : 0)
              enabled: !controller.busy
              echoMode: root.showPassword || controller.echoResponse ? TextInput.Normal : TextInput.Password
              passwordCharacter: "●"
              inputMethodHints: controller.echoResponse ? Qt.ImhNoPredictiveText : Qt.ImhHiddenText | Qt.ImhSensitiveData | Qt.ImhNoPredictiveText
              placeholderText: controller.awaitingResponse ? "Respuesta" : "Contraseña"
              placeholderTextColor: root.muted
              color: root.foreground
              selectionColor: root.accent
              selectedTextColor: root.look.onAccent || "#000000"
              font.family: root.family
              font.pixelSize: Math.round(13 * root.uiScale)
              leftPadding: 12
              rightPadding: 12
              onAccepted: root.submit()
              Keys.onEscapePressed: controller.cancel()

              background: Rectangle {
                color: root.look.raised || "#101010"
                radius: root.look.radius || 0
                border.width: password.activeFocus ? 2 : 1
                border.color: password.activeFocus ? root.accent : (root.look.border || "#ffffff")
              }
            }

            GreeterControls.ControlButton {
              focusPolicy: root.interactive ? Qt.StrongFocus : Qt.NoFocus
              look: root.look
              text: root.showPassword ? "Ocultar" : "Ver"
              enabled: !controller.busy && !controller.echoResponse
              onClicked: root.showPassword = !root.showPassword
              Accessible.name: root.showPassword ? "Ocultar contraseña" : "Mostrar contraseña"
            }
          }

          GreeterControls.ControlButton {
            focusPolicy: root.interactive ? Qt.StrongFocus : Qt.NoFocus
            Layout.fillWidth: true
            Layout.topMargin: 10
            look: root.look
            primary: true
            text: controller.busy ? "Verificando…" : controller.awaitingResponse ? "Continuar" : "Entrar"
            trailing: controller.busy ? "" : "→"
            enabled: controller.ready && !controller.busy && controller.model.sessions.length > 0
            onClicked: root.submit()
          }

          Text {
            objectName: "greeter-keyboard-status"
            Layout.fillWidth: true
            text: root.keyboardStatusText
            textFormat: Text.PlainText
            font.family: root.family
            font.pixelSize: Math.round(11 * root.uiScale)
            color: controller.keyboard?.capsLock === true ? root.foreground : root.muted
            wrapMode: Text.WordWrap
            Accessible.name: text
          }

          RowLayout {
            Layout.fillWidth: true
            visible: controller.message !== ""
            spacing: 10
            GreeterControls.BrandIcon {
              visible: controller.messageIsError
              name: "error"
              color: root.foreground
              Layout.preferredWidth: 30
              Layout.preferredHeight: 30
              Layout.alignment: Qt.AlignTop
            }
            Text {
              Layout.fillWidth: true
              text: controller.message
              Accessible.role: Accessible.AlertMessage
              Accessible.name: text
              onTextChanged: if (root.interactive && text)
                Accessible.announce(text, Accessible.Assertive)
              textFormat: Text.PlainText
              color: controller.messageIsError ? (root.look.danger || root.foreground) : root.muted
              font.family: root.family
              font.pixelSize: Math.round(12 * root.uiScale)
              wrapMode: Text.WordWrap
            }
            GreeterControls.ControlButton {
              visible: controller.messageIsError && root.interactive
              look: root.look
              text: "Copiar"
              onClicked: Quickshell.clipboardText = controller.message
              Accessible.name: "Copiar mensaje de error"
            }
          }

          GreeterControls.ControlButton {
            focusPolicy: root.interactive ? Qt.StrongFocus : Qt.NoFocus
            visible: controller.authenticating
            text: "Cancelar"
            look: root.look
            onClicked: controller.cancel()
          }
        }
      }

      ColumnLayout {
        id: footer

        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: root.padding
        spacing: 10

        Rectangle {
          Layout.fillWidth: true
          implicitHeight: 1
          color: root.look.border || "#ffffff"
          opacity: 0.3
        }

        Text {
          visible: controller.powerConfirmation !== ""
          text: controller.powerConfirmation === "poweroff" ? "¿Apagar el equipo?" : controller.powerConfirmation === "reboot" ? "¿Reiniciar el equipo?" : "¿Suspender el equipo?"
          font.family: root.family
          font.pixelSize: Math.round(12 * root.uiScale)
          color: root.foreground
        }

        GridLayout {
          visible: controller.powerConfirmation === ""
          Layout.fillWidth: true
          columns: Math.min(3, Math.max(1, Math.floor(width / (130 * root.uiScale))))
          columnSpacing: 6
          rowSpacing: 6

          Repeater {
            model: [
              {
                "name": "Suspender",
                "action": "suspend"
              },
              {
                "name": "Reiniciar",
                "action": "reboot"
              },
              {
                "name": "Apagar",
                "action": "poweroff"
              }
            ]

            GreeterControls.ControlButton {
              focusPolicy: root.interactive ? Qt.StrongFocus : Qt.NoFocus
              required property var modelData

              Layout.fillWidth: true
              implicitHeight: Math.max(36 * root.uiScale, root.look.largeTargets ? 44 : 0)
              look: root.look
              text: modelData.name
              font.pixelSize: Math.round(10 * root.uiScale)
              enabled: !controller.preview && !controller.authenticating
              onClicked: controller.power(modelData.action)
            }
          }
        }

        Flow {
          visible: controller.powerConfirmation !== ""
          Layout.fillWidth: true
          spacing: 8

          GreeterControls.ControlButton {
            focusPolicy: root.interactive ? Qt.StrongFocus : Qt.NoFocus
            look: root.look
            text: "Cancelar"
            onClicked: controller.powerConfirmation = ""
          }

          GreeterControls.ControlButton {
            focusPolicy: root.interactive ? Qt.StrongFocus : Qt.NoFocus
            look: root.look
            text: "Confirmar"
            primary: true
            onClicked: controller.power(controller.powerConfirmation)
          }
        }
      }
    }
  }

  Rectangle {
    visible: !root.centered && root.width - rail.width >= 170 * root.uiScale + 2 * root.padding
    anchors.right: parent.right
    anchors.bottom: parent.bottom
    anchors.margins: root.padding
    width: Math.max(170 * root.uiScale, Math.min(254 * root.uiScale, root.width - rail.width - 2 * root.padding))
    height: 118 * root.uiScale
    radius: root.look.radius || 0
    color: root.surface
    border.width: 1
    border.color: root.look.border || "#ffffff"

    Column {
      anchors.fill: parent
      anchors.margins: 18
      spacing: 5

      Text {
        text: Qt.formatDateTime(clock.date, "HH:mm")
        color: root.foreground
        font.family: root.family
        font.pixelSize: Math.round(42 * root.uiScale)
        font.weight: Font.Light
      }

      Text {
        text: Qt.formatDateTime(clock.date, "ddd, dd MMM yyyy")
        color: root.muted
        font.family: root.family
        font.pixelSize: Math.round(11 * root.uiScale)
      }
    }
  }

  Connections {
    function onClearInput() {
      password.text = "";
      root.showPassword = false;
      if (root.interactive)
        password.forceActiveFocus();
    }

    function onModelUpdated() {
      if (!user.activeFocus)
        user.text = controller.userName;
    }

    target: controller
  }
}
