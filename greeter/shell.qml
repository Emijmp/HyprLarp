//@ pragma Env QT_QUICK_CONTROLS_STYLE=Basic
//@ pragma Env QT_LINUX_ACCESSIBILITY_ALWAYS_ON=1
import QtQuick
import QtQuick.Window
import Quickshell
import Quickshell.Io

ShellRoot {
  id: root
  // Exercise the real window policy with the isolated, simulated login tests.
  readonly property bool windowedPreview: loginController.preview && !(loginController.testMode && Quickshell.env("HYPRLARP_GREETER_TEST_FULLSCREEN") === "1")
  Controller {
    id: loginController
  }
  Variants {
    id: greeterWindows
    model: Qt.application.screens
    delegate: Component {
      Window {
        required property var modelData
        screen: modelData
        title: loginController.preview ? "HyprLarp · Vista previa" : "HyprLarp"
        // The native compositor sets the output size but does not acknowledge
        // xdg fullscreen requests. Keep decorations off even in that state.
        flags: root.windowedPreview ? Qt.Window : Qt.Window | Qt.FramelessWindowHint
        visibility: root.windowedPreview ? Window.Windowed : Window.FullScreen
        width: root.windowedPreview ? 1280 : screen.width
        height: root.windowedPreview ? 800 : screen.height
        onClosing: event => {
          event.accepted = root.windowedPreview;
          if (root.windowedPreview)
            Qt.quit();
        }
        color: loginController.model.appearance.surface || "#000000"
        GreeterView {
          anchors.fill: parent
          controller: loginController
        }
      }
    }
  }
  LazyLoader {
    active: loginController.testMode
    component: IpcHandler {
      target: "greeterTest"
      function status(): string {
        return JSON.stringify({
          ready: loginController.ready,
          busy: loginController.busy,
          awaiting: loginController.awaitingResponse,
          message: loginController.message,
          user: loginController.userName,
          appearance: loginController.model.appearance,
          revision: loginController.model.revision,
          keyboard: loginController.keyboard
        });
      }
      function submit(response: string): void {
        loginController.submit(response);
      }
      function cancel(): void {
        loginController.cancel();
      }
      function windows(): string {
        return JSON.stringify(greeterWindows.instances.map(window => ({
              visible: window.visible,
              frameless: !!(window.flags & Qt.FramelessWindowHint),
              width: window.width,
              height: window.height,
              screenWidth: window.screen.width,
              screenHeight: window.screen.height
            })));
      }
      function closeWindow(index: int): bool {
        return greeterWindows.instances[index]?.close() ?? false;
      }
      function captureWindow(index: int, path: string): bool {
        return greeterWindows.instances[index]?.contentItem.grabToImage(result => result.saveToFile(path)) ?? false;
      }
    }
  }
}
