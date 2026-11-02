import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
import "../core"
import "../components"

ColumnLayout {
  id: root
  spacing: 12
  property string filter: "all"
  readonly property var applications: Applications.search(search.text, filter)
  function focusSearch() {
    search.forceActiveFocus();
  }
  function launch(app) {
    if (app) {
      Applications.launched(app);
      app.execute();
      ShellState.close();
    }
  }
  Component.onCompleted: search.forceActiveFocus()
  Component.onDestruction: apps.model = null
  Field {
    id: search
    Layout.fillWidth: true
    placeholderText: "Buscar aplicaciones"
    onTextChanged: apps.currentIndex = 0
    Keys.onDownPressed: apps.currentIndex = Math.min(apps.count - 1, apps.currentIndex + 1)
    Keys.onUpPressed: apps.currentIndex = Math.max(0, apps.currentIndex - 1)
    onAccepted: root.launch(root.applications[apps.currentIndex])
  }
  RowLayout {
    Repeater {
      model: ["all", "favorites", "recent"]
      ActionButton {
        required property string modelData
        text: ({
            all: "Todas",
            favorites: "Favoritas",
            recent: "Recientes"
          })[modelData]
        selected: root.filter === modelData
        onClicked: {
          root.filter = modelData;
          apps.currentIndex = 0;
        }
      }
    }
  }
  ListView {
    id: apps
    Layout.fillWidth: true
    Layout.preferredHeight: 350
    clip: true
    model: root.applications
    currentIndex: 0
    highlightMoveDuration: 0
    boundsBehavior: Flickable.StopAtBounds
    cacheBuffer: 0
    reuseItems: true
    ScrollBar.vertical: SlimScrollBar {}
    delegate: Rectangle {
      id: entry
      required property var modelData
      required property int index
      width: apps.width - 8
      height: 42
      color: apps.currentIndex === index || hover.containsMouse ? Theme.raised : "transparent"
      Rectangle {
        visible: apps.currentIndex === entry.index
        width: 1
        height: parent.height
        color: Theme.border
      }
      RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 10
        anchors.rightMargin: 42
        spacing: 10
        Image {
          visible: !!Bridge.settings.showAppIcons
          readonly property string appIcon: entry.modelData.icon || ""
          property bool failed: false
          onAppIconChanged: failed = false
          onStatusChanged: if (status === Image.Error)
            failed = true
          source: !visible ? "" : failed ? Qt.resolvedUrl("../assets/application.svg") : Applications.icon(appIcon)
          asynchronous: true
          Layout.preferredWidth: 24
          Layout.preferredHeight: 24
          sourceSize.width: 24
          sourceSize.height: 24
        }
        ColumnLayout {
          Layout.fillWidth: true
          spacing: 2
          Label {
            text: entry.modelData.name
            Layout.fillWidth: true
            font.pixelSize: 12
          }
          Label {
            text: entry.modelData.genericName || ""
            visible: text !== ""
            color: Theme.muted
            font.pixelSize: 10
            Layout.fillWidth: true
          }
        }
      }
      MouseArea {
        id: hover
        anchors.fill: parent
        anchors.rightMargin: 38
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: root.launch(entry.modelData)
      }
      ActionButton {
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        visible: entry.y + entry.height / 2 >= apps.contentY + 7 && entry.y + entry.height / 2 <= apps.contentY + apps.height - 7
        icon: "star"
        selected: Applications.favorite(entry.modelData)
        hint: "Alternar favorita"
        onClicked: Applications.toggleFavorite(entry.modelData)
      }
    }
  }
  EmptyState {
    visible: root.applications.length === 0
    title: "Sin resultados"
  }
  Label {
    text: "↑ ↓  seleccionar    Enter  abrir    Esc  cerrar"
    font.pixelSize: 10
    color: Theme.muted
  }
}
