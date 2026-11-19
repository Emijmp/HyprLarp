pragma Singleton
import QtQuick
import Quickshell
import "datetime.js" as Dates

SystemClock {
  precision: Bridge.settings.clockSeconds ? SystemClock.Seconds : SystemClock.Minutes
  readonly property string timeText: formatTime(date)
  readonly property string dateText: formatDate(date)
  function formatTime(value): string {
    return Qt.formatDateTime(value, Dates.timePattern(Bridge.settings));
  }
  function formatDate(value): string {
    return value.toLocaleDateString(Qt.locale("es"), Bridge.settings.clockDateFormat || "dd/MM/yyyy");
  }
}
