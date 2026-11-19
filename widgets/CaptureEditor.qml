import QtQuick
import QtQuick.Layouts
import "../core"
import "../components"

Rectangle {
  id: root
  required property var draft
  property string tool: "crop"
  property var operations: []
  property var crop: null
  property var current: null
  property real cursorX: draft.width / 2
  property real cursorY: draft.height / 2
  function finishCurrent() {
    if (!current)
      return;
    const operation = current;
    if (operation.kind === "arrow" ? Math.hypot(operation.x2 - operation.x, operation.y2 - operation.y) >= 1 : Math.abs(operation.x2 - operation.x) >= 1 && Math.abs(operation.y2 - operation.y) >= 1) {
      if (operation.kind === "crop")
        crop = {
          x: Math.min(operation.x, operation.x2),
          y: Math.min(operation.y, operation.y2),
          width: Math.abs(operation.x2 - operation.x),
          height: Math.abs(operation.y2 - operation.y)
        };
      else if (operations.length < 100)
        operations = operations.concat([operation]);
    }
    current = null;
    canvas.requestPaint();
  }
  function keyboardAction(key, modifiers) {
    const amount = modifiers & Qt.ShiftModifier ? 10 : 1;
    if (key === Qt.Key_Left)
      cursorX = Math.max(0, cursorX - amount);
    else if (key === Qt.Key_Right)
      cursorX = Math.min(draft.width, cursorX + amount);
    else if (key === Qt.Key_Up)
      cursorY = Math.max(0, cursorY - amount);
    else if (key === Qt.Key_Down)
      cursorY = Math.min(draft.height, cursorY + amount);
    else if (key === Qt.Key_Escape)
      current = null;
    else if ([Qt.Key_Space, Qt.Key_Return, Qt.Key_Enter].includes(key)) {
      if (tool === "text" && annotationText.text.trim() && operations.length < 100)
        operations = operations.concat([
          {
            kind: "text",
            x: cursorX,
            y: cursorY,
            x2: cursorX,
            y2: cursorY,
            text: annotationText.text
          }
        ]);
      else if (current) {
        finishCurrent();
        return true;
      } else
        current = {
          kind: tool,
          x: cursorX,
          y: cursorY,
          x2: cursorX,
          y2: cursorY
        };
    } else
      return false;
    if (current)
      current = Object.assign({}, current, {
        x2: cursorX,
        y2: cursorY
      });
    canvas.requestPaint();
    return true;
  }
  onOperationsChanged: canvas.requestPaint()
  onCropChanged: canvas.requestPaint()
  color: Theme.surface
  EdgeDetail {
    anchors.fill: parent
    inset: 6
  }
  function save() {
    Bridge.perform("capture-save", {
      token: draft.token,
      operations: operations,
      crop: crop
    });
  }
  function discard() {
    if (!Bridge.preview)
      Bridge.perform("capture-discard", {
        token: draft.token
      });
    Bridge.captureDraft = null;
  }
  function draw(context, operation, preview) {
    if (!operation)
      return;
    const x = operation.x, y = operation.y, x2 = operation.x2, y2 = operation.y2;
    const left = Math.min(x, x2), top = Math.min(y, y2), width = Math.abs(x2 - x), height = Math.abs(y2 - y);
    if (operation.kind === "redact") {
      context.fillStyle = "#000000";
      context.fillRect(left, top, width, height);
    } else if (operation.kind === "arrow") {
      const angle = Math.atan2(y2 - y, x2 - x), size = Math.max(10, Math.min(draft.width, draft.height) / 35);
      for (const stroke of [
        {
          color: "#000000",
          width: 7
        },
        {
          color: "#ffffff",
          width: 3
        }
      ]) {
        context.beginPath();
        context.moveTo(x, y);
        context.lineTo(x2, y2);
        context.moveTo(x2 - size * Math.cos(angle - 0.45), y2 - size * Math.sin(angle - 0.45));
        context.lineTo(x2, y2);
        context.lineTo(x2 - size * Math.cos(angle + 0.45), y2 - size * Math.sin(angle + 0.45));
        context.strokeStyle = stroke.color;
        context.lineWidth = stroke.width;
        context.stroke();
      }
    } else if (operation.kind === "text") {
      context.font = Math.max(16, Math.min(draft.width, draft.height) / 28) + "px 'DejaVu Sans'";
      context.lineWidth = 1;
      context.strokeStyle = "#000000";
      context.fillStyle = "#ffffff";
      context.strokeText(operation.text, x, y);
      context.fillText(operation.text, x, y);
    } else if (preview) {
      context.strokeStyle = "#ffffff";
      context.lineWidth = 2 / stage.scaleFactor;
      context.setLineDash([5 / stage.scaleFactor, 4 / stage.scaleFactor]);
      context.strokeRect(left, top, width, height);
      context.setLineDash([]);
    }
  }
  Connections {
    target: Bridge
    function onActionFinished(action) {
      if (action === "capture-save")
        Bridge.captureDraft = null;
    }
  }
  ColumnLayout {
    anchors.fill: parent
    anchors.margins: 16
    spacing: 10
    RowLayout {
      Label {
        text: "Editar captura"
        font.pixelSize: Theme.fontPx(15)
        Layout.fillWidth: true
      }
      ActionButton {
        text: "Descartar"
        enabled: !Bridge.isBusy("capture-save")
        onClicked: root.discard()
      }
      ActionButton {
        text: Bridge.isBusy("capture-save") ? "Guardando…" : "Guardar y copiar"
        accent: true
        enabled: !Bridge.isBusy("capture-save") && !Bridge.preview
        onClicked: root.save()
      }
    }
    RowLayout {
      Repeater {
        model: ["crop", "arrow", "text", "redact"]
        ActionButton {
          required property string modelData
          text: ({
              crop: "Recortar",
              arrow: "Flecha",
              text: "Texto",
              redact: "Ocultar área"
            })[modelData]
          selected: root.tool === modelData
          onClicked: root.tool = modelData
        }
      }
      Item {
        Layout.fillWidth: true
      }
      ActionButton {
        text: "Quitar última"
        enabled: root.operations.length > 0
        onClicked: {
          root.operations = root.operations.slice(0, -1);
          canvas.requestPaint();
        }
      }
      ActionButton {
        text: "Imagen completa"
        enabled: root.crop !== null
        onClicked: {
          root.crop = null;
          canvas.requestPaint();
        }
      }
    }
    Field {
      id: annotationText
      visible: root.tool === "text"
      placeholderText: "Texto de la anotación"
      maximumLength: 200
      Layout.fillWidth: true
    }
    Label {
      text: "Ratón: arrastra o pulsa para anotar. Teclado: enfoca la imagen con Tab, mueve el cursor con flechas (Mayús: 10 px), Espacio fija el inicio y Enter aplica. Escape cancela el trazo."
      Layout.fillWidth: true
      wrapMode: Text.WordWrap
      color: Theme.muted
      font.pixelSize: Theme.fontPx(11)
    }
    Rectangle {
      id: stage
      activeFocusOnTab: true
      Keys.onPressed: event => event.accepted = root.keyboardAction(event.key, event.modifiers)
      Accessible.role: Accessible.Graphic
      Accessible.name: "Imagen de captura · " + root.draft.width + " por " + root.draft.height + " píxeles"
      Accessible.description: "Cursor " + Math.round(root.cursorX) + ", " + Math.round(root.cursorY) + ". Flechas para mover; Espacio para iniciar; Enter para aplicar."
      Accessible.focusable: true
      Accessible.onPressAction: root.keyboardAction(Qt.Key_Space, 0)
      FocusRing {
        control: stage
      }
      Layout.fillWidth: true
      Layout.fillHeight: true
      color: Theme.background
      border.width: 1
      border.color: Theme.separator
      clip: true
      readonly property real scaleFactor: Math.min((width - 16) / root.draft.width, (height - 16) / root.draft.height)
      Item {
        width: root.draft.width * stage.scaleFactor
        height: root.draft.height * stage.scaleFactor
        anchors.centerIn: parent
        Image {
          anchors.fill: parent
          source: root.draft.url
          fillMode: Image.PreserveAspectFit
          asynchronous: true
          cache: false
        }
        Canvas {
          id: canvas
          anchors.fill: parent
          onWidthChanged: requestPaint()
          onHeightChanged: requestPaint()
          onPaint: {
            const context = getContext("2d");
            context.reset();
            context.clearRect(0, 0, width, height);
            context.save();
            context.scale(stage.scaleFactor, stage.scaleFactor);
            for (const operation of root.operations)
              root.draw(context, operation, false);
            if (root.crop)
              root.draw(context, {
                kind: "crop",
                x: root.crop.x,
                y: root.crop.y,
                x2: root.crop.x + root.crop.width,
                y2: root.crop.y + root.crop.height
              }, true);
            root.draw(context, root.current, true);
            if (stage.activeFocus) {
              context.strokeStyle = "#ffffff";
              context.lineWidth = 2 / stage.scaleFactor;
              context.strokeRect(root.cursorX - 4 / stage.scaleFactor, root.cursorY - 4 / stage.scaleFactor, 8 / stage.scaleFactor, 8 / stage.scaleFactor);
            }
            context.restore();
          }
        }
        MouseArea {
          anchors.fill: parent
          enabled: !Bridge.isBusy("capture-save")
          cursorShape: Qt.CrossCursor
          onPressed: event => {
            const x = event.x / stage.scaleFactor, y = event.y / stage.scaleFactor;
            if (root.tool === "text") {
              if (annotationText.text.trim() && root.operations.length < 100)
                root.operations = root.operations.concat([
                  {
                    kind: "text",
                    x: x,
                    y: y,
                    x2: x,
                    y2: y,
                    text: annotationText.text
                  }
                ]);
            } else
              root.current = {
                kind: root.tool,
                x: x,
                y: y,
                x2: x,
                y2: y
              };
            canvas.requestPaint();
          }
          onPositionChanged: event => {
            if (!pressed || !root.current)
              return;
            root.current = Object.assign({}, root.current, {
              x2: Math.max(0, Math.min(root.draft.width, event.x / stage.scaleFactor)),
              y2: Math.max(0, Math.min(root.draft.height, event.y / stage.scaleFactor))
            });
            canvas.requestPaint();
          }
          onReleased: {
            if (!root.current)
              return;
            root.finishCurrent();
          }
          onCanceled: {
            root.current = null;
            canvas.requestPaint();
          }
        }
      }
    }
    Label {
      text: root.draft.width + " × " + root.draft.height + (root.crop ? " · recorte " + Math.round(root.crop.width) + " × " + Math.round(root.crop.height) : "")
      color: Theme.muted
      font.family: Theme.mono
      font.pixelSize: Theme.fontPx(10)
    }
  }
}
