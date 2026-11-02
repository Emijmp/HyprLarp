import QtQuick
import QtQuick.Layouts
import Quickshell
import "../core"
import "../components"

ColumnLayout {
  id: root
  spacing: 14
  property date displayed: new Date()
  readonly property int offset: (new Date(displayed.getFullYear(), displayed.getMonth(), 1).getDay() + 6) % 7
  readonly property int days: new Date(displayed.getFullYear(), displayed.getMonth() + 1, 0).getDate()
  function move(delta) {
    displayed = new Date(displayed.getFullYear(), displayed.getMonth() + delta, 1);
  }
  Label {
    text: Qt.formatDateTime(Clock.date, "hh:mm")
    font.pixelSize: 26
    font.family: Theme.mono
  }
  Label {
    text: Clock.date.toLocaleDateString(Qt.locale("es"), "dddd, d 'de' MMMM")
    font.pixelSize: 11
    color: Theme.muted
  }
  Rule {}
  RowLayout {
    Label {
      text: root.displayed.toLocaleDateString(Qt.locale("es"), "MMMM yyyy")
      Layout.fillWidth: true
    }
    ActionButton {
      icon: "previous"
      hint: "Mes anterior"
      onClicked: root.move(-1)
    }
    ActionButton {
      icon: "next"
      hint: "Mes siguiente"
      onClicked: root.move(1)
    }
  }
  GridLayout {
    Layout.fillWidth: true
    columns: 7
    rowSpacing: 3
    columnSpacing: 3
    Repeater {
      model: ["L", "M", "X", "J", "V", "S", "D"]
      Label {
        required property string modelData
        text: modelData
        color: Theme.muted
        font.pixelSize: 10
        Layout.fillWidth: true
        horizontalAlignment: Text.AlignHCenter
      }
    }
    Repeater {
      model: 42
      Item {
        id: day
        required property int index
        readonly property int number: index - root.offset + 1
        readonly property bool validDay: number > 0 && number <= root.days
        readonly property bool today: number === Clock.date.getDate() && root.displayed.getMonth() === Clock.date.getMonth() && root.displayed.getFullYear() === Clock.date.getFullYear()
        Layout.fillWidth: true
        implicitHeight: 29
        Label {
          anchors.centerIn: parent
          text: day.validDay ? day.number : ""
          font.family: Theme.mono
          font.pixelSize: 11
        }
        Rectangle {
          visible: day.today
          anchors.left: parent.left
          anchors.right: parent.right
          anchors.bottom: parent.bottom
          height: 1
          color: Theme.border
        }
      }
    }
  }
  ActionButton {
    text: "Hoy"
    onClicked: root.displayed = new Date()
  }
}
