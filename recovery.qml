//@ pragma UseQApplication
//@ pragma Env QT_QUICK_CONTROLS_STYLE=Basic
//@ pragma Env QT_LINUX_ACCESSIBILITY_ALWAYS_ON=1
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
import Quickshell
import Quickshell.Io
import Quickshell.Wayland

// Intentionally independent of Theme, Bridge, custom controls and normal panels.
ShellRoot {
  id: root
  property real textScale: 1
  readonly property string executable: Quickshell.env("HYPRLARP_EXECUTABLE") || Quickshell.shellPath("bin/hyprlarp")
  property string message: Quickshell.env("HYPRLARP_RECOVERY_REASON") || "Se abrió el modo de recuperación."
  property string report: ""
  function run(action) {
    operation.command = action === "terminal" ? ["/usr/bin/python3", Quickshell.shellPath("backend/recovery_tools.py"), "terminal"] : [executable, action];
    operation.running = true;
  }
  IpcHandler {
    target: "recovery"
    function health(): string {
      return JSON.stringify({
        mode: "recovery",
        ready: true
      });
    }
    function show(): void {
      dialog.visible = true;
      dialog.contentItem.forceActiveFocus();
    }
  }
  Process {
    id: preferences
    command: ["/usr/bin/python3", Quickshell.shellPath("backend/recovery_tools.py"), "preferences"]
    running: true
    stdout: StdioCollector {
      onStreamFinished: {
        try {
          root.textScale = JSON.parse(text).textScale;
        } catch (error) {}
      }
    }
  }
  Process {
    id: operation
    stderr: StdioCollector {
      onStreamFinished: if (text.trim())
        root.message = text.trim()
    }
    onExited: (code, status) => {
      if (code !== 0)
        root.message = "La acción no se pudo completar. Puedes abrir una terminal para revisar el sistema.";
    }
  }
  Process {
    id: diagnostics
    command: [root.executable, "doctor", "--no-logs"]
    stdout: StdioCollector {
      onStreamFinished: root.report = text
    }
  }
  Variants {
    model: Quickshell.env("HYPRLARP_RECOVERY_PREVIEW") === "1" ? [] : Quickshell.screens
    PanelWindow {
      required property var modelData
      screen: modelData
      anchors {
        top: true
        left: true
        right: true
      }
      color: "#000000"
      implicitHeight: toolbar.implicitHeight + 16
      exclusiveZone: implicitHeight
      WlrLayershell.namespace: "hyprlarp-recovery"
      WlrLayershell.layer: WlrLayer.Top
      WlrLayershell.keyboardFocus: WlrKeyboardFocus.OnDemand
      Column {
        id: toolbar
        anchors {
          left: parent.left
          right: parent.right
          top: parent.top
          margins: 8
        }
        spacing: 12
        Label {
          text: "HyprLarp · Recuperación"
          color: "#ffffff"
          font.pixelSize: 16 * root.textScale
          width: Math.min(implicitWidth, parent.width)
          height: Math.max(44, implicitHeight)
          wrapMode: Text.WrapAtWordBoundaryOrAnywhere
        }
        Button {
          text: "Abrir recuperación"
          font.pixelSize: 14 * root.textScale
          implicitHeight: Math.max(44, contentItem.implicitHeight + topPadding + bottomPadding)
          onClicked: dialog.visible = true
        }
      }
    }
  }
  FloatingWindow {
    id: dialog
    title: "HyprLarp · Recuperación"
    implicitWidth: 740
    implicitHeight: 640
    minimumSize: Qt.size(420, 360)
    color: "#000000"
    Connections {
      target: dialog.contentItem.Window.window
      function onActiveFocusItemChanged() {
        const item = target.activeFocusItem;
        let inside = false;
        for (let parent = item; parent; parent = parent.parent)
          if (parent === content) {
            inside = true;
            break;
          }
        if (!inside)
          return;
        Qt.callLater(() => {
          const top = item.mapToItem(content, 0, 0).y;
          const flickable = scroll.contentItem;
          if (top < flickable.contentY || top + item.height > flickable.contentY + scroll.availableHeight)
            flickable.contentY = Math.max(0, Math.min(top - 8, flickable.contentHeight - scroll.availableHeight));
        });
      }
    }
    ScrollView {
      id: scroll
      anchors.fill: parent
      anchors.margins: 20
      contentWidth: availableWidth
      ColumnLayout {
        id: content
        width: parent.width
        spacing: 20
        Label {
          text: "HyprLarp · Recuperación"
          color: "#ffffff"
          font.pixelSize: 24 * root.textScale
          Layout.fillWidth: true
          wrapMode: Text.WrapAtWordBoundaryOrAnywhere
          Accessible.role: Accessible.Heading
        }
        Label {
          text: root.message
          color: "#ffffff"
          font.pixelSize: 16 * root.textScale
          Layout.fillWidth: true
          wrapMode: Text.WrapAtWordBoundaryOrAnywhere
          Accessible.role: Accessible.AlertMessage
        }
        Label {
          text: "Tus ajustes y las aplicaciones abiertas se conservan. Puedes reintentar el shell, revisar la configuración o abrir una terminal."
          color: "#dedede"
          font.pixelSize: 16 * root.textScale
          Layout.fillWidth: true
          wrapMode: Text.WrapAtWordBoundaryOrAnywhere
        }
        Flow {
          Layout.fillWidth: true
          spacing: 12
          Button {
            text: "Reintentar shell"
            focus: true
            font.pixelSize: 16 * root.textScale
            onClicked: root.run("retry")
          }
          Button {
            text: "Abrir terminal"
            font.pixelSize: 16 * root.textScale
            onClicked: root.run("terminal")
          }
          Button {
            text: "Configuración"
            font.pixelSize: 16 * root.textScale
            onClicked: root.run("settings")
          }
          Button {
            text: "Diagnóstico"
            font.pixelSize: 16 * root.textScale
            onClicked: diagnostics.running = true
          }
        }
        TextArea {
          visible: root.report !== ""
          text: root.report
          readOnly: true
          wrapMode: TextEdit.Wrap
          color: "#ffffff"
          font.pixelSize: 14 * root.textScale
          Layout.fillWidth: true
          Accessible.name: "Informe de diagnóstico"
          background: Rectangle {
            color: "#111111"
          }
        }
      }
    }
  }
}
