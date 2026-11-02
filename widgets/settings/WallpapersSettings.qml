import QtQuick
import "../../core"

Loader {
  source: Qt.resolvedUrl("../../panels/WallpapersPanel.qml")
  onLoaded: {
    item.configurationEditor = true;
    Bridge.send("refresh", {
      name: "wallpapers"
    });
  }
}
