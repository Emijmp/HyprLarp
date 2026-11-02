pragma Singleton
import QtQuick
import Quickshell
import "nightSchedule.js" as Schedule

Singleton {
  readonly property bool desired: Schedule.active(Bridge.settings, Bridge.settings.nightLightSchedule ? Clock.date : new Date())
  readonly property string nativeSignature: Bridge.ready && Bridge.connected && !Bridge.awaitingInitial && !Bridge.preview && !Bridge.settingsOnly ? String(Schedule.active(Bridge.confirmedSettings, Bridge.confirmedSettings.nightLightSchedule ? Clock.date : new Date())) + ":" + Bridge.confirmedSettings.nightLightTemperature : ""
  onNativeSignatureChanged: if (nativeSignature)
    Bridge.send("night-sync")
}
