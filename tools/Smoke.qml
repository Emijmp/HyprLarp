import QtQuick
import QtQuick.Window
import Quickshell
import "../core"
import "../widgets"

Scope {
  id: root
  property int step: 0
  readonly property var themeNames: Object.keys(Theme.palettes)
  readonly property int themeStart: panels.length + settings.sections.length + 7
  readonly property int moduleStart: themeStart + themeNames.length
  readonly property var panels: ["control", "launcher", "wifi", "bluetooth", "notifications", "clipboard", "media", "calendar", "session", "resources", "battery", "wallpapers", "capture", "audio", "brightness", "energy", "night-light", "usb"]
  readonly property var geometryCases: [
    {
      barPosition: "top",
      barSize: 34,
      barPaddingX: 0,
      barPaddingY: 0,
      barSpacing: 0,
      barBorderWidth: 0,
      barMargins: {
        top: 0,
        right: 0,
        bottom: 0,
        left: 0
      },
      barOpacity: 0,
      barBlur: true,
      barReserveSpace: false
    },
    {
      barPosition: "left",
      barSize: 48,
      barPaddingX: 4,
      barPaddingY: 4,
      barLength: 25,
      barAlignment: "end",
      barFontSize: 16,
      barIconSize: 18,
      barWorkspaceCount: 10
    },
    {
      barPosition: "bottom",
      barSize: 34,
      barPaddingX: 8,
      barPaddingY: 3,
      barSpacing: 10,
      barBorderWidth: 1,
      barMargins: {
        top: 0,
        right: 16,
        bottom: 24,
        left: 32
      },
      barOpacity: 1,
      barBlur: false,
      barReserveSpace: true,
      barFontSize: 12,
      barIconSize: 14,
      barWorkspaceCount: 5,
      barLength: 75,
      barAlignment: "start"
    }
  ]
  FloatingWindow {
    color: "transparent"
    implicitWidth: 900
    implicitHeight: Number(Quickshell.env("HYPRLARP_SETTINGS_HEIGHT") || "720")
    visible: true
    SettingsContent {
      id: settings
      anchors.fill: parent
      tab: Number(Quickshell.env("HYPRLARP_SETTINGS_TAB") || "0")
      confirmReset: Quickshell.env("HYPRLARP_SETTINGS_RESET") === "1"
    }
  }
  Timer {
    interval: 200
    running: !!Quickshell.env("HYPRLARP_SETTINGS_CAPTURE")
    onTriggered: {
      const mode = Quickshell.env("HYPRLARP_SETTINGS_MODULES_MODE");
      if (settings.tab === 2 && mode && settings.currentPage)
        settings.currentPage.mode = mode;
      if (settings.Window.window)
        settings.Window.window.requestActivate();
    }
  }
  Timer {
    interval: 1200
    running: !!Quickshell.env("HYPRLARP_SETTINGS_CAPTURE")
    onTriggered: settings.grabToImage(result => {
      console.log("Settings capture:", result.saveToFile(Quickshell.env("HYPRLARP_SETTINGS_CAPTURE")));
      if (Quickshell.env("HYPRLARP_CAPTURE_ONLY") === "1")
        Qt.quit();
    })
  }
  Timer {
    id: cycle
    interval: 500
    repeat: true
    running: true
    onTriggered: {
      if (Quickshell.env("HYPRLARP_REVIEW_CHECKS_ONLY") === "1") {
        stop();
        reviewChecks.setSource(Qt.resolvedUrl("ReviewChecks.qml"));
        return;
      }
      if (Quickshell.env("HYPRLARP_CONNECTION_CHECKS_ONLY") === "1") {
        stop();
        connectionChecks.setSource(Qt.resolvedUrl("ConnectionChecks.qml"));
        return;
      }
      if (root.step < root.panels.length) {
        const name = root.panels[root.step];
        const entry = ModuleCatalog.definitions.find(entry => entry.kind === "panel" && entry.target === name);
        if (entry)
          ModuleCatalog.activate(entry.id);
        else
          ShellState.open(name);
        // Exercise populated delegates without changing any device state.
        if (name === "wifi")
          Bridge.network = {
            available: true,
            enabled: true,
            ssid: "Studio:5G",
            networks: [
              {
                ssid: "Studio:5G",
                signal: 88,
                security: "WPA2",
                connected: true,
                interface: "wlan0"
              }
            ]
          };
        if (name === "bluetooth")
          Bridge.bluetooth = {
            available: true,
            enabled: true,
            devices: [
              {
                name: "Auriculares de prueba",
                address: "AA:BB:CC:DD:EE:FF",
                paired: true,
                connected: false
              }
            ]
          };
        if (name === "notifications")
          Notices.history = [
            {
              id: 100,
              token: "test:100",
              app: "Prueba de interfaz",
              summary: "Una notificación de prueba",
              body: "Contenido de la notificación",
              time: Date.now(),
              read: false,
              urgency: 1
            }
          ];
        if (name === "clipboard")
          Bridge.clipboard = [
            {
              id: "1",
              raw: "1\tTexto de prueba",
              text: "Texto de prueba",
              image: false
            }
          ];
        if (name === "energy")
          Bridge.power = {
            available: true,
            profile: "balanced",
            profiles: ["power-saver", "balanced", "performance"],
            reason: "",
            holds: [],
            error: ""
          };
        if (name === "usb")
          Bridge.usb = {
            available: true,
            error: "",
            devices: [
              {
                id: "fixture",
                name: "Dispositivo de prueba",
                manufacturer: "",
                vendor: "1234",
                product: "5678",
                speed: "480"
              }
            ],
            drives: [
              {
                id: "/org/freedesktop/UDisks2/drives/fixture",
                name: "Unidad de prueba",
                size: 64000000000,
                canEject: true,
                protected: false,
                volumes: [
                  {
                    id: "/org/freedesktop/UDisks2/block_devices/sdz1",
                    device: "/dev/sdz1",
                    name: "Datos de prueba",
                    filesystem: "exfat",
                    size: 64000000000,
                    mounts: ["/run/media/test/fixture"],
                    mounted: true,
                    mountable: true,
                    protected: false,
                    readOnly: false,
                    free: 32000000000,
                    total: 64000000000
                  }
                ]
              }
            ]
          };
        if (name === "battery")
          Bridge.system = Object.assign({}, Bridge.system, {
            battery: {
              available: true,
              charging: true,
              percent: 72,
              batteries: [
                {
                  name: "BAT0",
                  percent: 72,
                  status: "Charging",
                  health: 90,
                  watts: 12,
                  energyNow: 30,
                  energyFull: 45,
                  energyDesign: 50,
                  cycles: 100,
                  voltage: 12,
                  temperature: 30,
                  manufacturer: "Fixture",
                  model: "Prueba de interfaz",
                  technology: "Li-ion",
                  timeToFull: 3600,
                  timeEstimated: true,
                  degradation: 10
                }
              ]
            }
          });
        console.log("SMOKE panel", root.panels[root.step]);
      } else if (root.step < root.panels.length + settings.sections.length) {
        settings.tab = root.step - root.panels.length;
        console.log("SMOKE settings", settings.tab);
      } else if (root.step < root.panels.length + settings.sections.length + 4) {
        ModuleCatalog.appearance("barPosition", ["top", "bottom", "left", "right"][root.step - root.panels.length - settings.sections.length]);
        console.log("SMOKE bar", Bridge.settings.barPosition);
      } else if (root.step < root.panels.length + settings.sections.length + 7) {
        const values = root.geometryCases[root.step - root.panels.length - settings.sections.length - 4];
        for (const key of Object.keys(values))
          Bridge.set(key, values[key]);
        console.log("SMOKE bar geometry", root.step);
      } else if (root.step < root.moduleStart) {
        Theme.apply(root.themeNames[root.step - root.themeStart]);
        console.log("SMOKE theme", Bridge.settings.theme);
      } else if (root.step === root.moduleStart) {
        ShellState.close();
        Bridge.set("barModules", []);
        settings.tab = 2;
        console.log("SMOKE modules empty");
      } else if (root.step === root.moduleStart + 1) {
        ModuleCatalog.add("clock");
        ModuleCatalog.add("launcher");
        ModuleCatalog.move(1, -1);
        if (ModuleCatalog.selected.join(",") !== "launcher,clock")
          throw new Error("Module add/reorder failed");
        console.log("SMOKE modules add/reorder");
      } else if (root.step === root.moduleStart + 2) {
        ModuleCatalog.remove("launcher");
        if (ModuleCatalog.selected.includes("launcher"))
          throw new Error("Module removal failed");
        for (const name of ModuleCatalog.available)
          ModuleCatalog.add(name);
        console.log("SMOKE modules all");
      } else if (root.step === root.moduleStart + 3) {
        ModuleCatalog.appearance("barPosition", "left");
        console.log("SMOKE modules vertical");
      } else if (root.step === root.moduleStart + 4) {
        for (const key of ["modulePaddingX", "modulePaddingY", "moduleBorderWidth", "moduleRadius", "moduleBackgroundOpacity", "moduleOpacity"])
          Bridge.set(key, 0);
        console.log("SMOKE module geometry zero");
      } else if (root.step === root.moduleStart + 5) {
        Bridge.captureDraft = {
          token: "smoke",
          url: Qt.resolvedUrl("../assets/wallpapers/amoled.svg"),
          width: 1920,
          height: 1080
        };
        ShellState.captureRemaining = 3;
      } else {
        cycle.stop();
        Bridge.captureDraft = null;
        ShellState.captureRemaining = 0;
        featureChecks.setSource(Qt.resolvedUrl("FeatureChecks.qml"));
      }
      root.step += 1;
    }
  }
  Loader {
    id: featureChecks
    onLoaded: item.completed.connect(() => connectionChecks.setSource(Qt.resolvedUrl("ConnectionChecks.qml")))
  }
  Loader {
    id: connectionChecks
    onLoaded: item.completed.connect(() => {
      if (Quickshell.env("HYPRLARP_CONNECTION_CHECKS_ONLY") === "1") {
        console.log("SMOKE COMPLETE");
        Qt.quit();
      } else
        reviewChecks.setSource(Qt.resolvedUrl("ReviewChecks.qml"));
    })
  }
  Loader {
    id: reviewChecks
    onLoaded: item.completed.connect(() => {
      if (Quickshell.env("HYPRLARP_REVIEW_CHECKS_ONLY") === "1") {
        console.log("SMOKE COMPLETE");
        Qt.quit();
      } else
        moduleChecks.setSource(Qt.resolvedUrl("ModuleChecks.qml"), {
          view: settings
        });
    })
  }
  Loader {
    id: moduleChecks
    onLoaded: item.completed.connect(() => settingsChecks.setSource(Qt.resolvedUrl("SettingsChecks.qml"), {
        view: settings,
        running: true
      }))
  }
  Loader {
    id: settingsChecks
    onLoaded: {
      item.completed.connect(() => {
        console.log("SMOKE COMPLETE");
        Qt.quit();
      });
    }
  }
}
