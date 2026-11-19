import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../core"
import "../components"

ColumnLayout {
  id: root
  spacing: 10
  property string application: ""
  readonly property var applications: Array.from(new Set(Notices.history.map(item => item.app))).sort()
  readonly property var rows: Notices.grouped(search.text, application)
  Component.onCompleted: Notices.markRead()
  Field {
    id: search
    Layout.fillWidth: true
    placeholderText: "Buscar notificaciones"
  }
  RowLayout {
    SettingToggle {
      title: "No molestar"
      checked: !!Bridge.settings.doNotDisturb
      onEdited: checked => Bridge.set("doNotDisturb", checked)
    }
    ActionButton {
      text: "Vaciar"
      visible: Notices.history.length > 0
      onClicked: Notices.clear()
    }
  }
  ComboBox {
    Layout.fillWidth: true
    model: ["Todas las aplicaciones"].concat(root.applications)
    currentIndex: root.application ? root.applications.indexOf(root.application) + 1 : 0
    onActivated: index => root.application = index === 0 ? "" : root.applications[index - 1]
    font.family: Theme.font
    font.pixelSize: Theme.fontPx(11)
    palette.text: Theme.text
    palette.button: Theme.surface
    palette.buttonText: Theme.text
    palette.base: Theme.surface
    palette.highlight: Theme.raised
    palette.highlightedText: Theme.text
    background: Rectangle {
      radius: Theme.radiusFor("field")
      color: Theme.surface
      border.width: 1
      border.color: Theme.separator
    }
  }
  ListView {
    id: list
    Layout.fillWidth: true
    Layout.preferredHeight: root.rows.length ? 390 : 0
    clip: true
    model: root.rows
    cacheBuffer: 0
    reuseItems: true
    spacing: 8
    boundsBehavior: Flickable.StopAtBounds
    ScrollBar.vertical: SlimScrollBar {}
    delegate: Loader {
      id: entry
      required property var modelData
      width: list.width - 8
      sourceComponent: modelData.kind === "header" ? header : notice
      Component {
        id: header
        SectionTitle {
          text: entry.modelData.app + " · " + entry.modelData.count
        }
      }
      Component {
        id: notice
        NotificationCard {
          entry: parent.modelData.entry
        }
      }
    }
  }
  EmptyState {
    visible: root.rows.length === 0
    title: "Sin notificaciones coincidentes"
  }
}
