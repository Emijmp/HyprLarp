//@ pragma UseQApplication
import QtQuick
import Quickshell

ShellRoot {
  Timer {
    interval: 100
    running: true
    onTriggered: {
      let valid = true;
      for (const file of ["Desktop.qml", "OsdWindow.qml"]) {
        const component = Qt.createComponent(Qt.resolvedUrl("../widgets/" + file), Component.PreferSynchronous);
        if (component.status !== Component.Ready) {
          valid = false;
          console.warn("Native types:", component.errorString());
        }
      }
      if (valid) {
        console.log("NATIVE TYPES COMPLETE");
      }
      Qt.exit(valid ? 0 : 1);
    }
  }
}
