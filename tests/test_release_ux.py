"""Release checks use actual QML controls with temporary settings and no devices."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which("quickshell"), "Quickshell unavailable")
class ReleaseUxTests(unittest.TestCase):
  def run_qml(self, body, *, timeout=8):
    with tempfile.TemporaryDirectory(prefix="hyprlarp-release-ux-") as folder:
      app = Path(folder)
      (app / "backend").symlink_to(ROOT / "backend", target_is_directory=True)
      imports = "\n".join('import "' + (ROOT / directory).as_uri() + '" as ' + alias
        for directory, alias in [("core", "Core"), ("components", "Controls"),
          ("panels", "Panels"), ("widgets", "Widgets")])
      source = '''//@ pragma UseQApplication
//@ pragma Env QT_QUICK_CONTROLS_STYLE=Basic
//@ pragma Env HYPRLARP_PREVIEW=1
import QtQuick
import QtQuick.Window
import QtTest
import Quickshell
''' + imports + '''
ShellRoot {
  id: root
  property int step: 0
  function verify(ok, message) {
    if (!ok) { console.error(message); Qt.quit(); throw new Error(message); }
  }
  function find(item, name) {
    if (!item) return null;
    if (item.objectName === name) return item;
    for (const child of item.children || []) { const found = find(child, name); if (found) return found; }
    return item.item ? find(item.item, name) : null;
  }
''' + body + "\n}"
      (app / "shell.qml").write_text(source)
      environment = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "QT_QUICK_BACKEND": "software",
        "XDG_RUNTIME_DIR": folder, "HYPRLARP_STATE_DIR": str(app / "settings"), "HYPRLARP_PREVIEW": "1"}
      environment.pop("WAYLAND_DISPLAY", None)
      result = subprocess.run(["quickshell", "--path", str(app / "shell.qml"), "--no-color"],
        env=environment, text=True, capture_output=True, timeout=timeout)
      output = result.stdout + result.stderr
      self.assertEqual(result.returncode, 0, output)
      self.assertIn("RELEASE UX COMPLETE", output)
      for error in ("ReferenceError:", "TypeError:", "Failed to load", "Binding loop", "Unable to assign"):
        self.assertNotIn(error, output)

  def test_error_messages_honor_minimum_font_and_text_scale(self):
    self.run_qml('''
  FloatingWindow {
    implicitWidth: 700; implicitHeight: 400
    Controls.StatusMessage { id: status; width: parent.width; text: "No se pudo conectar. Reintenta."; error: true }
  }
  Timer {
    interval: 100; repeat: true; running: true
    onTriggered: {
      if (!Core.Bridge.ready) return;
      Core.Bridge.settings = Object.assign({}, Core.Bridge.settings, {accessibilityMinimumFontSize: 16, accessibilityTextScale: 1.75});
      const label = root.find(status, "status-message-text");
      root.verify(label.font.pixelSize === 28, "errors must honor the minimum font size and accessibility scale");
      status.fontSize = 20;
      root.verify(label.font.pixelSize === 35, "explicit error font size must still scale");
      root.verify(status.Accessible.name === status.text && status.Accessible.role === Accessible.AlertMessage, "error remains available as an accessible alert");
      console.log("RELEASE UX COMPLETE"); stop(); Qt.quit();
    }
  }''')

  def test_unavailable_cpu_never_appears_as_a_measured_zero(self):
    self.run_qml('''
  FloatingWindow {
    implicitWidth: 600; implicitHeight: 700
    Panels.ResourcesPanel { id: resources; width: parent.width }
  }
  Timer {
    interval: 100; repeat: true; running: true
    onTriggered: {
      if (!Core.Bridge.ready) return;
      const cpu = root.find(resources, "resource-cpu");
      for (const value of [null, undefined]) {
        Core.Bridge.system = {cpu: value};
        root.verify(cpu.detail === "N/D", "missing CPU sample must be unavailable");
      }
      Core.Bridge.system = {cpu: 0};
      root.verify(cpu.detail === "0%", "an actual zero must remain a valid measurement");
      Core.Bridge.system = {cpu: 42.4};
      root.verify(cpu.detail === "42%", "numeric CPU measurements keep their formatting");
      console.log("RELEASE UX COMPLETE"); stop(); Qt.quit();
    }
  }''')

  def test_empty_connection_states_offer_an_action_matching_the_device_state(self):
    self.run_qml('''
  FloatingWindow {
    implicitWidth: 700; implicitHeight: 700
    Panels.NetworkPanel { id: network; width: parent.width }
    Panels.BluetoothPanel { id: bluetooth; width: parent.width; visible: false }
  }
  Timer {
    interval: 100; repeat: true; running: true
    onTriggered: {
      if (!Core.Bridge.ready) return;
      const wifi = root.find(network, "network-empty");
      const blue = root.find(bluetooth, "bluetooth-empty");
      Core.Bridge.network = {available: false, enabled: false, networks: []};
      root.verify(wifi.description.includes("NetworkManager"), "unavailable network service must name the missing service");
      Core.Bridge.network = {available: true, enabled: false, networks: []};
      root.verify(wifi.description.startsWith("Activa"), "disabled Wi-Fi must explain how to enable it");
      Core.Bridge.network = {available: true, enabled: true, networks: []};
      root.verify(wifi.description.startsWith("Pulsa Buscar"), "enabled Wi-Fi must offer a scan instead of asking to enable it");
      Core.Bridge.bluetooth = {available: false, enabled: false, devices: []};
      root.verify(blue.description.includes("adaptador") && blue.description.includes("BlueZ"), "missing Bluetooth adapter must not ask for pairing");
      Core.Bridge.bluetooth = {available: true, enabled: false, devices: []};
      root.verify(blue.title === "Bluetooth desactivado" && blue.description.startsWith("Activa Bluetooth"), "disabled Bluetooth must be identified");
      Core.Bridge.bluetooth = {available: true, enabled: true, devices: []};
      root.verify(blue.description.includes("vinculación"), "enabled Bluetooth offers pairing instructions");
      console.log("RELEASE UX COMPLETE"); stop(); Qt.quit();
    }
  }''')

  def test_every_primary_panel_accepts_keyboard_focus_and_escape_at_large_text(self):
    self.run_qml('''
  readonly property var panels: ["control", "audio", "brightness", "energy", "night-light", "usb", "launcher", "navigation", "wifi", "bluetooth", "notifications", "clipboard", "media", "calendar", "session", "resources", "performance", "battery", "wallpapers", "capture", "displays"]
  property int index: 0
  FloatingWindow {
    id: window
    implicitWidth: 900; implicitHeight: 700
    TestEvent { id: keys }
    Widgets.PanelSurface { id: surface; anchors.fill: parent; availableHeight: height }
  }
  Timer {
    interval: 100; repeat: true; running: true
    onTriggered: {
      if (!Core.Bridge.ready || Core.Bridge.saving || Core.Bridge.hasPendingSettings) return;
      if (root.step === 0) {
        Core.Bridge.settings = Object.assign({}, Core.Bridge.settings, {accessibilityTextScale: 2, accessibilityLargeTargets: true});
        window.contentItem.Window.window.requestActivate();
        Core.ShellState.open(root.panels[root.index]); root.step = 1; return;
      }
      const loader = root.find(surface, "panel-content-loader");
      if (!loader || loader.status !== 1 || !loader.item) return;
      root.verify(!!window.contentItem.Window.window.activeFocusItem, "panel has a keyboard focus target: " + root.panels[root.index]);
      root.verify(keys.keyClick(Qt.Key_Tab, 0, 0) && keys.keyClick(Qt.Key_Backtab, Qt.ShiftModifier, 0), "panel supports Tab traversal: " + root.panels[root.index]);
      root.verify(keys.keyClick(Qt.Key_Escape, 0, 0) && Core.ShellState.panel === "", "Escape closes panel: " + root.panels[root.index]);
      root.index++;
      if (root.index === root.panels.length) { console.log("RELEASE UX COMPLETE"); stop(); Qt.quit(); }
      else { Core.ShellState.open(root.panels[root.index]); }
    }
  }''', timeout=15)

  def test_focused_control_remains_visible_when_the_panel_viewport_shrinks(self):
    self.run_qml('''
  FloatingWindow {
    id: window
    implicitWidth: 760; implicitHeight: 700
    Widgets.PanelSurface { id: surface; anchors.fill: parent; availableHeight: height }
  }
  Timer {
    interval: 150; repeat: true; running: true
    onTriggered: {
      if (!Core.Bridge.ready) return;
      if (root.step === 0) {
        Core.Bridge.settings = Object.assign({}, Core.Bridge.settings, {accessibilityTextScale: 2});
        Core.Bridge.network = {available: true, enabled: true, networks: Array.from({length: 30}, (_, i) => ({ssid: "Red " + i, security: "WPA2", signal: 80, interface: "wlan0", connected: false}))};
        window.contentItem.Window.window.requestActivate();
        Core.ShellState.open("wifi"); root.step = 1; return;
      }
      const target = root.find(surface, "network-manager");
      const scroll = root.find(surface, "panel-scroll");
      if (!target || !scroll) return;
      if (root.step === 1) { target.forceActiveFocus(); root.step = 2; return; }
      const y = target.mapToItem(scroll, 0, 0).y;
      root.verify(y >= -1 && y + target.height <= scroll.availableHeight + 1, "focused control must remain entirely visible after changing available height");
      if (root.step === 2) { window.implicitHeight = 360; root.step = 3; return; }
      console.log("RELEASE UX COMPLETE"); stop(); Qt.quit();
    }
  }''')
