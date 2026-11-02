pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Networking
import Quickshell.Bluetooth

Singleton {
  id: root
  readonly property bool active: !Bridge.preview && !Bridge.settingsOnly
  readonly property bool networkNeeded: active && (BarLayout.enabledModules.includes("wifi") || ["wifi", "control"].includes(ShellState.panel))
  // Subscribe to connection changes, without starting a Wi-Fi scan in the background.
  readonly property string networkSignature: networkNeeded ? JSON.stringify({
    enabled: Networking.wifiEnabled,
    connectivity: Networking.connectivity,
    devices: Networking.devices.values.map(d => ({
          name: d.name,
          connected: d.connected,
          state: d.state,
          networks: d.networks.values.filter(n => n.connected || ShellState.panel === "wifi").map(n => ({
                name: n.name,
                connected: n.connected
              }))
        }))
  }) : ""
  readonly property bool bluetoothNeeded: active && (BarLayout.enabledModules.includes("bluetooth") || ["bluetooth", "control"].includes(ShellState.panel))
  readonly property var adapter: bluetoothNeeded ? Bluetooth.defaultAdapter : null
  readonly property var bluetoothState: ({
      available: adapter !== null,
      enabled: adapter !== null && adapter.enabled,
      adapter: adapter ? adapter.dbusPath : "",
      discovering: adapter !== null && adapter.discovering,
      error: "",
      devices: adapter ? adapter.devices.values.map(d => ({
            address: d.address,
            name: d.name,
            paired: d.paired,
            trusted: d.trusted,
            connected: d.connected
          })).sort((a, b) => Number(b.connected) - Number(a.connected) || Number(b.paired) - Number(a.paired) || a.name.localeCompare(b.name)) : []
    })
  onNetworkSignatureChanged: if (networkSignature && Bridge.ready)
    networkRefresh.restart()
  onBluetoothStateChanged: if (bluetoothNeeded)
    Bridge.bluetooth = bluetoothState
  onBluetoothNeededChanged: if (bluetoothNeeded)
    Bridge.bluetooth = bluetoothState
  Connections {
    target: Bridge
    function onReadyChanged() {
      if (Bridge.ready && root.networkSignature)
        networkRefresh.restart();
    }
  }
  Timer {
    id: networkRefresh
    interval: 250
    onTriggered: if (root.networkNeeded)
      Bridge.send("network-status")
  }
}
