pragma Singleton
import QtQuick
import Quickshell

Singleton {
  readonly property var definitions: Bridge.moduleDefinitions
  readonly property var byId: {
    const result = {};
    for (const entry of definitions)
      result[entry.id] = entry;
    return result;
  }
  readonly property var labels: {
    const result = {};
    for (const entry of definitions)
      result[entry.id] = entry.title;
    return result;
  }
  readonly property var groups: Array.from(new Set(definitions.map(entry => entry.group)))
  readonly property var zones: BarEditor.settings.barZones || {
    start: BarEditor.settings.barModules || [],
    center: [],
    end: []
  }
  readonly property var selected: [].concat(zones.start, zones.center, zones.end)
  readonly property var available: definitions.map(entry => entry.id).filter(name => !selected.includes(name))
  function search(query, group) {
    const normalize = value => value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
    const words = normalize(query.trim()).split(/\s+/);
    return available.filter(name => {
      const entry = byId[name];
      return (!group || entry.group === group) && words.every(word => normalize(entry.title + " " + entry.description + " " + entry.group).includes(word));
    });
  }
  function add(name, zone) {
    if (available.includes(name))
      place(name, zone || "end");
  }
  function place(name, zone, before) {
    if (!byId[name] || !["start", "center", "end"].includes(zone))
      return;
    const next = {};
    for (const key of ["start", "center", "end"])
      next[key] = zones[key].filter(item => item !== name);
    const position = before ? next[zone].indexOf(before) : -1;
    next[zone].splice(position < 0 ? next[zone].length : position, 0, name);
    BarEditor.configure({
      barZones: next
    });
  }
  function remove(name) {
    const next = {};
    for (const zone of ["start", "center", "end"])
      next[zone] = zones[zone].filter(item => item !== name);
    BarEditor.configure({
      barZones: next
    });
  }
  function move(index, direction) {
    const name = selected[index], other = selected[index + direction];
    if (!name || !other)
      return;
    const targetZone = ["start", "center", "end"].find(zone => zones[zone].includes(other));
    const next = {};
    for (const zone of ["start", "center", "end"])
      next[zone] = zones[zone].filter(item => item !== name);
    next[targetZone].splice(next[targetZone].indexOf(other) + (direction > 0 ? 1 : 0), 0, name);
    BarEditor.configure({
      barZones: next
    });
  }
  function appearance(key, value) {
    BarEditor.set(key, value);
  }
  function iconFor(name) {
    if (name === "wifi" && Bridge.network.ethernet)
      return "ethernet";
    if (["volume", "mute"].includes(name))
      return Audio.muted ? "muted" : name === "mute" ? "muted" : "volume";
    if (["microphone", "microphone-mute"].includes(name))
      return Audio.microphoneMuted ? "microphone-off" : byId[name].icon;
    if (name === "media-play-pause")
      return Media.player && Media.player.isPlaying ? "pause" : "play";
    return byId[name] ? byId[name].icon : "grid";
  }
  function active(name) {
    const entry = byId[name];
    if (!entry)
      return false;
    if (name === "night-light")
      return Bridge.nightLight.active || ShellState.panel === "night-light";
    if (entry.kind === "settings")
      return ShellState.settingsOpen && ShellState.settingsPage === entry.target;
    if (entry.kind === "panel")
      return ShellState.panel === entry.target;
    if (name === "presentation")
      return Presentation.active;
    if (name === "do-not-disturb")
      return !!Bridge.settings.doNotDisturb;
    if (name === "clipboard-pause")
      return !!Bridge.settings.clipboardPaused;
    if (name === "mute")
      return Audio.muted;
    if (name === "microphone-mute")
      return Audio.microphoneMuted;
    if (name === "media-play-pause")
      return Media.player !== null && Media.player.isPlaying;
    if (entry.kind === "session")
      return ShellState.panel === "session" && ShellState.sessionRequest === entry.target;
    return false;
  }
  function commandAvailable(name) {
    if (name === "mute")
      return Audio.available;
    if (name === "microphone-mute")
      return Audio.microphoneAvailable;
    if (name === "media-play-pause")
      return Media.player !== null && Media.player.canTogglePlaying;
    if (name === "media-previous")
      return Media.player !== null && Media.player.canGoPrevious;
    if (name === "media-next")
      return Media.player !== null && Media.player.canGoNext;
    if (name === "clipboard-pause")
      return Bridge.settings.clipboardEnabled === true;
    return true;
  }
  function activate(name, screen) {
    const entry = byId[name];
    if (!entry || !commandAvailable(name))
      return;
    if (entry.kind === "panel")
      ShellState.toggle(entry.target, screen);
    else if (entry.kind === "settings") {
      if (screen && ["Bar", "Modules"].includes(entry.target))
        BarEditor.target = screen.name;
      ShellState.openSettings(entry.target);
    } else if (entry.kind === "session")
      ShellState.openSession(entry.target, screen);
    else if (name === "presentation")
      Presentation.toggle();
    else if (entry.kind === "toggle")
      Bridge.set(entry.target, !Bridge.settings[entry.target]);
    else if (name === "mute")
      Audio.setMuted(!Audio.muted);
    else if (name === "microphone-mute")
      Audio.setNodeMuted(Audio.source, !Audio.microphoneMuted);
    else if (name === "media-play-pause")
      Media.playPause();
    else if (name === "media-previous")
      Media.previous();
    else if (name === "media-next")
      Media.next();
    else if (name === "lock") {
      ShellState.close();
      Bridge.perform("session", {
        command: "lock"
      });
    } else if (name.startsWith("screenshot-"))
      ShellState.capture(name.slice("screenshot-".length));
  }
}
