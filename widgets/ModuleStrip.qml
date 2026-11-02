import QtQuick
import "../core"

Item {
  id: root
  required property var names
  required property var configuration
  required property var guide
  property var screen: null
  readonly property bool vertical: guide.vertical
  implicitWidth: vertical ? column.implicitWidth : row.implicitWidth
  implicitHeight: vertical ? column.implicitHeight : row.implicitHeight
  Component {
    id: entry
    Loader {
      required property string modelData
      width: root.vertical ? root.width : implicitWidth
      height: root.vertical ? implicitHeight : root.height
      Component.onCompleted: setSource(Qt.resolvedUrl(modelData === "tray" ? "TrayModule.qml" : "BarModule.qml"), modelData === "tray" ? {} : {
        moduleName: modelData
      })
      onLoaded: {
        item.configuration = Qt.binding(() => root.configuration);
        item.guide = Qt.binding(() => root.guide);
        item.vertical = Qt.binding(() => root.vertical);
        item.screen = Qt.binding(() => root.screen);
      }
    }
  }
  Row {
    id: row
    spacing: root.guide.spacing
    height: root.height
    visible: !root.vertical
    Repeater {
      model: root.vertical ? [] : root.names
      delegate: entry
    }
  }
  Column {
    id: column
    spacing: root.guide.spacing
    width: root.width
    visible: root.vertical
    Repeater {
      model: root.vertical ? root.names : []
      delegate: entry
    }
  }
}
