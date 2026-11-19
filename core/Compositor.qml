pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Hyprland
import "workspaces.js" as Workspaces

Singleton {
  id: root
  readonly property bool enabled: !Bridge.preview && !Bridge.settingsOnly && !!Quickshell.env("HYPRLAND_INSTANCE_SIGNATURE")
  readonly property string focusedScreenName: enabled && Hyprland.focusedMonitor ? Hyprland.focusedMonitor.name : ""
  Connections {
    target: Hyprland
    enabled: root.enabled
    function onRawEvent(event) {
      if (["monitoradded", "monitoraddedv2", "monitorremoved", "monitorremovedv2", "configreloaded"].includes(event.name)) {
        displayEvents.reason = event.name === "configreloaded" ? "configreloaded" : "event";
        displayEvents.restart();
      }
    }
  }
  Timer {
    id: displayEvents
    property string reason: "event"
    interval: 350
    onTriggered: Bridge.send("displays-event", {reason: reason})
  }
  readonly property var snapshot: enabled ? ({
      monitors: Hyprland.monitors.values.map(m => ({
            name: m.name,
            activeId: m.activeWorkspace ? m.activeWorkspace.id : null
          })),
      workspaces: Hyprland.workspaces.values.map(w => ({
            id: w.id,
            name: w.name,
            monitor: w.monitor ? w.monitor.name : "",
            occupied: w.toplevels.values.length > 0,
            urgent: w.urgent
          }))
    }) : ({
      monitors: [],
      workspaces: []
    })
  function entriesFor(screen, count, mode) {
    const name = screen ? screen.name : focusedScreenName;
    return Workspaces.display(Workspaces.entries(snapshot, name, count ?? Bridge.settings.barWorkspaceCount ?? 5), mode || Bridge.settings.barWorkspaceDisplay || "current");
  }
  function cycle(screen, direction, count) {
    const name = screen ? screen.name : focusedScreenName;
    const all = Workspaces.entries(snapshot, name, count ?? Bridge.settings.barWorkspaceCount ?? 5);
    const next = Workspaces.adjacent(all, direction);
    if (next)
      activate(next, screen);
  }
  function activate(workspace, screen) {
    if (!workspace || workspace.unavailable)
      return;
    const target = workspace.gap ? workspace.target : workspace;
    if (!enabled || !target)
      return;
    for (const request of Workspaces.focusCommands(target, screen ? screen.name : focusedScreenName, Hyprland.usingLua))
      Hyprland.dispatch(request);
  }
}
