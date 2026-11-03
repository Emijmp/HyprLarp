import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import "../core"
import "../core/workspaces.js" as Workspaces
import "../components"
import "../widgets"

Scope {
  id: root
  property int step: 0
  property real deadline: Date.now() + 12000
  property int originalSpacing: Bridge.settings.barSpacing
  property int restartBefore: Bridge.restartAttempts
  property string selectedColor: "#ffffff"
  property int originalOsdTimeout: 1500
  property bool originalOsdEnabled: true
  property real osdStarted: 0
  signal completed
  function verify(condition, message) {
    if (!condition)
      throw new Error("Feature regression: " + message);
  }
  BarGeometry {
    id: barGeometry
  }
  function checkBarReservation() {
    const margins = {
      top: 8,
      bottom: 16,
      left: 32,
      right: 24
    };
    for (const screen of [
      {
        width: 1920,
        height: 1080
      },
      {
        width: 1536,
        height: 864
      },
      {
        width: 1080,
        height: 1920
      }
    ]) {
      for (const position of ["top", "bottom", "left", "right"]) {
        for (const length of [25, 75, 100]) {
          for (const alignment of ["start", "center", "end"]) {
            barGeometry.configuration = Object.assign({}, Bridge.settings, {
              barPosition: position,
              barLength: length,
              barAlignment: alignment,
              barMargins: margins,
              barSize: 48,
              barEnabled: true,
              barReserveSpace: true
            });
            const anchors = barGeometry.windowAnchors;
            root.verify(Object.values(anchors).filter(Boolean).length === 3 && anchors[position], "bar reservation has a valid edge on " + position);
            const placement = barGeometry.windowMargins(screen.width, screen.height);
            const extent = barGeometry.vertical ? screen.height : screen.width;
            const leading = barGeometry.vertical ? placement.top : placement.left;
            const trailing = barGeometry.vertical ? placement.bottom : placement.right;
            root.verify(extent - leading - trailing === barGeometry.length(extent), "opposite anchors preserve the chosen bar length");
            root.verify(leading === barGeometry.offset(extent), "opposite anchors preserve bar alignment");
            root.verify(barGeometry.exclusiveZone === 48 + margins[position], "reservation includes bar thickness and its edge margin");
            if (alignment === "start")
              root.verify(leading === (barGeometry.vertical ? margins.top : margins.left), "leading alignment preserves the configured margin");
            if (alignment === "end" || length === 100)
              root.verify(trailing === (barGeometry.vertical ? margins.bottom : margins.right), "trailing alignment preserves the configured margin");
          }
        }
      }
    }
    barGeometry.configuration = Object.assign({}, barGeometry.configuration, {
      barReserveSpace: false
    });
    root.verify(!barGeometry.reserveSpace && barGeometry.exclusiveZone === 0, "turning off reservation releases the work area");
    barGeometry.configuration = Object.assign({}, barGeometry.configuration, {
      barReserveSpace: true,
      barEnabled: false
    });
    root.verify(!barGeometry.reserveSpace && barGeometry.exclusiveZone === 0, "hiding the bar releases the work area");
  }
  FloatingWindow {
    id: window
    title: "Feature checks"
    implicitWidth: 1050
    implicitHeight: 800
    color: Theme.surface
    ColumnLayout {
      anchors.fill: parent
      anchors.margins: 16
      ColorField {
        id: color
        title: "Selector de prueba"
        value: root.selectedColor
        onEdited: color => root.selectedColor = color
      }
      ModuleFrame {
        id: workspacePreview
        Layout.preferredWidth: workspaceRow.implicitWidth + 16
        Layout.preferredHeight: workspaceRow.implicitHeight + 8
        configuration: Object.assign({}, Bridge.settings, {
          moduleBorderWidth: 1,
          moduleRadius: 2,
          moduleBackgroundOpacity: 1
        })
        RowLayout {
          id: workspaceRow
          anchors.centerIn: parent
          spacing: 4
          Repeater {
            model: Workspaces.display(Array.from({
              length: 10
            }, (_, index) => ({
                  id: index + 1,
                  name: String(index + 1),
                  label: String(index + 1),
                  active: index === 5,
                  occupied: true
                })))
            WorkspaceCell {
              required property var modelData
              entry: modelData
              width: 28
              height: 26
            }
          }
        }
      }
      ShortcutField {
        id: shortcut
        action: "launcher"
      }
      AudioStream {
        Layout.fillWidth: true
        node: mockNode
        device: true
      }
      CaptureEditor {
        id: editor
        Layout.fillWidth: true
        Layout.fillHeight: true
        draft: ({
            token: "fixture",
            url: Qt.resolvedUrl("../assets/wallpapers/amoled.svg"),
            width: 1920,
            height: 1080
          })
      }
    }
  }
  QtObject {
    id: mockNode
    property string name: "Prueba de flujo"
    property string description: "Dispositivo de prueba"
    property bool ready: true
    property QtObject audio: QtObject {
      property real volume: 0.5
      property bool muted: false
    }
  }
  Process {
    id: stopService
  }
  Timer {
    interval: 150
    running: true
    repeat: true
    onTriggered: {
      root.verify(Date.now() < root.deadline, "feature checks timed out");
      switch (root.step) {
      case 0:
        root.checkBarReservation();
        root.verify(BarEditor.targets.filter(name => name === "").length === 1, "base monitor selector appears only once");
        root.originalSpacing = Bridge.settings.barSpacing;
        root.restartBefore = Bridge.restartAttempts;
        shortcut.startCapture();
        shortcut.cancelCapture();
        root.verify(Bridge.settings.shortcuts.launcher !== "", "cancelled key capture preserves the binding");
        color.openPicker();
        editor.operations = [
          {
            kind: "arrow",
            x: 100,
            y: 100,
            x2: 600,
            y2: 400
          },
          {
            kind: "text",
            x: 300,
            y: 300,
            x2: 300,
            y2: 300,
            text: "Anotación"
          },
          {
            kind: "redact",
            x: 700,
            y: 300,
            x2: 900,
            y2: 500
          }
        ];
        editor.crop = {
          x: 50,
          y: 50,
          width: 1600,
          height: 900
        };
        break;
      case 1:
        if (Quickshell.env("HYPRLARP_WORKSPACES_CAPTURE"))
          workspacePreview.grabToImage(result => result.saveToFile(Quickshell.env("HYPRLARP_WORKSPACES_CAPTURE")));
        color.finishPicker(true);
        root.verify(root.selectedColor === "#ffffff", "RGB picker commits valid hex");
        Audio.setNodeVolume(mockNode, 0.7);
        Audio.setNodeMuted(mockNode, true);
        root.verify(mockNode.audio.volume === 0.7 && mockNode.audio.muted, "audio stream writes correct node");
        Bridge.beginSettingsEdit();
        Bridge.set("barSpacing", 19);
        stopService.command = ["kill", "-TERM", String(Bridge.backendPid)];
        stopService.running = true;
        break;
      case 2:
        if (!Bridge.connected || Bridge.awaitingInitial || Bridge.restartAttempts <= root.restartBefore)
          return;
        root.verify(Bridge.settings.barSpacing === 19, "restart keeps unsaved preferences");
        Bridge.endSettingsEdit();
        break;
      case 3:
        if (Bridge.saving || Bridge.hasPendingSettings)
          return;
        root.verify(Bridge.confirmedSettings.barSpacing === 19, "restart flushes deferred changes");
        Bridge.set("barSpacing", root.originalSpacing);
        Bridge.flush();
        break;
      case 4:
        if (Bridge.saving || Bridge.hasPendingSettings)
          return;
        root.originalOsdTimeout = Bridge.settings.osdTimeout;
        root.originalOsdEnabled = Bridge.settings.osdEnabled;
        Bridge.set("osdTimeout", 500);
        Bridge.set("osdEnabled", true);
        Osd.show("brightness", 0.72, false, false);
        root.verify(!Osd.visible, "real OSD is suppressed in preview");
        Osd.show("brightness", 0.72, false, true);
        root.verify(Osd.visible && Osd.demo && Osd.kind === "brightness" && Osd.value === 0.72, "explicit OSD demonstration");
        Osd.show("microphone", 1.4, true, true);
        root.verify(Osd.kind === "microphone" && Osd.muted && Osd.value === 1, "microphone OSD clamps values and shows mute");
        root.osdStarted = Date.now();
        break;
      case 5:
        if (Date.now() - root.osdStarted < 650)
          return;
        root.verify(!Osd.visible, "OSD disappears after the configured timeout");
        Osd.show("volume", 0.5, false, true);
        Bridge.set("osdEnabled", false);
        root.verify(!Osd.visible, "disabling OSD immediately hides it");
        Osd.show("volume", 0.5, false, true);
        root.verify(!Osd.visible, "disabled OSD refuses demonstrations");
        Bridge.set("osdTimeout", root.originalOsdTimeout);
        Bridge.set("osdEnabled", root.originalOsdEnabled);
        Bridge.flush();
        break;
      case 6:
        if (Bridge.saving || Bridge.hasPendingSettings)
          return;
        window.visible = false;
        stop();
        console.log("SMOKE features COMPLETE");
        root.completed();
        break;
      }
      root.step++;
    }
  }
}
