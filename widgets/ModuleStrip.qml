import QtQuick
import "../core"
import "../components"

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
    Item {
      id: slot
      required property string modelData
      width: root.vertical ? root.width : implicitWidth
      height: root.vertical ? implicitHeight : root.height
      readonly property bool failed: moduleLoader.status === Loader.Error || Resilience.blocked("bar:" + modelData)
      implicitWidth: failed ? Math.max(Theme.largeTargets ? 44 : 32, root.guide.iconSize + 12) : moduleLoader.implicitWidth
      implicitHeight: failed ? Math.max(Theme.largeTargets ? 44 : 32, root.guide.iconSize + 12) : moduleLoader.implicitHeight
      GuardedLoader {
        id: moduleLoader
        moduleId: "bar:" + slot.modelData
        anchors.fill: parent
        Component.onCompleted: setSource(Qt.resolvedUrl(slot.modelData === "tray" ? "TrayModule.qml" : "BarModule.qml"), slot.modelData === "tray" ? {} : {
          moduleName: slot.modelData
        })
        onLoaded: {
          item.configuration = Qt.binding(() => root.configuration);
          item.guide = Qt.binding(() => root.guide);
          item.vertical = Qt.binding(() => root.vertical);
          item.screen = Qt.binding(() => root.screen);
        }
      }
      ActionButton {
        anchors.fill: parent
        visible: slot.failed
        icon: "error"
        hint: "Reintentar módulo: " + slot.modelData
        onClicked: Resilience.retry("bar:" + slot.modelData)
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
