import QtQuick
import QtQuick.Layouts
import Quickshell
import "../core"
import "../components"
import "../core/datetime.js" as Dates

ColumnLayout {
  id: root
  spacing: 14
  property date displayed: new Date()
  readonly property var cells: Dates.monthGrid(displayed.getFullYear(), displayed.getMonth(), Bridge.settings.calendarFirstDay, !!Bridge.settings.calendarWeekNumbers)
  function move(delta) {
    displayed = new Date(displayed.getFullYear(), displayed.getMonth() + delta, 1);
  }
  Label {
    text: Clock.timeText
    font.pixelSize: Theme.fontPx(26)
    font.family: Theme.mono
  }
  Label {
    text: Clock.dateText
    font.pixelSize: Theme.fontPx(11)
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
    columns: Bridge.settings.calendarWeekNumbers ? 8 : 7
    rowSpacing: 3
    columnSpacing: 3
    Repeater {
      model: root.cells
      Item {
        id: day
        required property var modelData
        readonly property bool today: modelData.kind === "day" && modelData.valid && modelData.number === Clock.date.getDate() && root.displayed.getMonth() === Clock.date.getMonth() && root.displayed.getFullYear() === Clock.date.getFullYear()
        Layout.fillWidth: true
        implicitHeight: 29
        Label {
          anchors.centerIn: parent
          text: day.modelData.kind === "day" ? (day.modelData.valid ? day.modelData.number : "") : day.modelData.label
          color: day.modelData.kind === "day" ? Theme.text : Theme.muted
          font.family: Theme.mono
          font.pixelSize: Theme.fontPx(11)
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
