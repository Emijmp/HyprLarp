import QtQuick
import Quickshell
import "../core"
import "../components"
import "../core/configuration.js" as SettingsIndex

Scope {
  id: root
  required property var view
  property int step: 0
  property var saved: ({})
  signal completed
  function verify(condition, message) {
    if (!condition)
      throw new Error("Daily regression: " + message);
  }
  StatusMessage {
    id: errorMessage
    parent: root.view
    visible: false
    text: "Error de prueba · ñ\n<detalle literal>"
    error: true
  }
  Timer {
    interval: 250
    repeat: true
    running: true
    onTriggered: {
      if (!Bridge.ready || Bridge.saving || Bridge.hasPendingSettings)
        return;
      switch (root.step++) {
      case 0:
        for (const key of ["clockFormat", "clockSeconds", "clockDateFormat", "calendarFirstDay", "calendarWeekNumbers"])
          root.saved[key] = Bridge.settings[key];
        Bridge.setMany({clockFormat: "12h", clockSeconds: true, clockDateFormat: "yyyy-MM-dd", calendarFirstDay: "sunday", calendarWeekNumbers: true});
        break;
      case 1:
        root.verify(Clock.precision === SystemClock.Seconds, "clock ticks in seconds when requested");
        root.verify(/\d{2}:\d{2}:\d{2} [AP]M/.test(Clock.timeText), "12-hour display includes seconds and AM/PM");
        root.verify(/^\d{4}-\d{2}-\d{2}$/.test(Clock.dateText), "selected date format is used");
        ShellState.open("calendar");
        root.view.activateSearchResult(SettingsIndex.search("segundos")[0]);
        break;
      case 2: {
        const target = root.view.findSetting(root.view.currentPage, "setting-clockSeconds");
        root.verify(root.view.tab === 5 && target && root.view.revealedSetting === "Mostrar segundos", "search opens the exact clock preference");
        root.verify(target.mapToItem(root.view, 0, 0).y > 0 && target.mapToItem(root.view, 0, 0).y < root.view.height, "clock preference is scrolled into view");
        root.view.activateSearchResult(SettingsIndex.search("batería crítica")[0]);
        break;
      }
      case 3: {
        const target = root.view.findSetting(root.view.currentPage, "setting-batteryAlerts");
        root.verify(target && target.mapToItem(root.view, 0, 0).y < root.view.height, "battery preference is scrolled into view");
        root.view.activateSearchResult(SettingsIndex.search("opacidad paneles")[0]);
        break;
      }
      case 4:
        root.verify(root.view.tab === 0 && root.view.findSetting(root.view.currentPage, "Opacidad de paneles"), "search crosses pages and finds opacity");
        errorMessage.copyError();
        root.verify(Quickshell.clipboardText === errorMessage.text && errorMessage.copied, "error copies the exact plain-text message");
        Bridge.setMany(root.saved);
        break;
      default:
        root.verify(Clock.precision === (Bridge.settings.clockSeconds ? SystemClock.Seconds : SystemClock.Minutes), "clock precision restores with preferences");
        ShellState.close();
        stop();
        console.log("SMOKE daily preferences COMPLETE");
        root.completed();
      }
    }
  }
}
