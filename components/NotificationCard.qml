import QtQuick
import QtQuick.Layouts
import "../core"

Rectangle {
  id: root
  required property var entry
  property bool toast: false
  Accessible.role: toast ? Accessible.AlertMessage : Accessible.Grouping
  Accessible.name: entry.app + " · " + entry.summary + (entry.body ? " · " + entry.body : "")
  Component.onCompleted: if (toast)
    Accessible.announce(Accessible.name, entry.urgency === 2 ? Accessible.Assertive : Accessible.Polite)
  readonly property int padding: toast ? 12 : 0
  implicitHeight: content.implicitHeight + padding * 2 + 9
  color: Theme.surface
  radius: root.toast ? Theme.radiusFor("notification") : 0
  border.width: toast ? 1 : 0
  border.color: Theme.border
  Rectangle {
    visible: Theme.detail("notificationMarks")
    x: root.padding
    y: root.padding + 5
    width: 2
    height: 10
    color: Theme.muted
  }
  ColumnLayout {
    id: content
    anchors.left: parent.left
    anchors.right: parent.right
    anchors.top: parent.top
    anchors.margins: root.padding
    anchors.leftMargin: root.padding + (Theme.detail("notificationMarks") ? 8 : 0)
    spacing: 6
    RowLayout {
      Label {
        text: root.entry.app
        font.pixelSize: Theme.fontPx(11)
        color: Theme.muted
        Layout.fillWidth: true
      }
      Label {
        text: Clock.formatTime(new Date(root.entry.time))
        font.pixelSize: Theme.fontPx(10)
        color: Theme.muted
        font.family: Theme.mono
      }
      ActionButton {
        icon: "close"
        hint: "Descartar"
        implicitWidth: 22
        implicitHeight: Theme.controlHeight(22)
        onClicked: {
          Notices.dismiss(root.entry.id, root.entry.token);
          if (!root.toast)
            Notices.remove(root.entry.token);
        }
      }
    }
    Label {
      text: root.entry.summary
      font.pixelSize: Theme.fontPx(12)
      font.weight: Font.Medium
      wrapMode: Text.WordWrap
      Layout.fillWidth: true
    }
    Label {
      visible: text !== ""
      text: root.entry.body
      wrapMode: Text.WordWrap
      maximumLineCount: root.toast ? 3 : 7
      color: Theme.muted
      font.pixelSize: Theme.fontPx(11)
      Layout.fillWidth: true
    }
    Flow {
      Layout.fillWidth: true
      spacing: 4
      Repeater {
        model: Notices.actions(root.entry.id, root.entry.token)
        ActionButton {
          required property var modelData
          text: modelData.text
          onClicked: {
            modelData.invoke();
            Notices.dismiss(root.entry.id, root.entry.token);
          }
        }
      }
    }
  }
  Rectangle {
    visible: !root.toast && Theme.detail("separators")
    anchors.left: parent.left
    anchors.right: parent.right
    anchors.bottom: parent.bottom
    height: 1
    color: Theme.separator
  }
}
