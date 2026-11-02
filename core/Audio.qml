pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Services.Pipewire

Singleton {
  id: root
  readonly property bool detailed: ShellState.panel === "audio"
  readonly property bool enabled: !Bridge.preview && !Bridge.settingsOnly
  readonly property var node: enabled && (detailed || Bridge.settings.osdEnabled !== false || ["volume", "audio", "mute"].some(name => BarLayout.enabledModules.includes(name)) || ["control", "media"].includes(ShellState.panel)) ? Pipewire.defaultAudioSink : null
  readonly property var source: enabled && (detailed || Bridge.settings.osdEnabled !== false || ["microphone", "microphone-mute"].some(name => BarLayout.enabledModules.includes(name))) ? Pipewire.defaultAudioSource : null
  readonly property var nodes: enabled && detailed ? Pipewire.nodes.values : []
  readonly property var outputs: nodes.filter(n => n.audio && !n.isStream && n.isSink)
  readonly property var inputs: nodes.filter(n => n.audio && !n.isStream && !n.isSink)
  readonly property var streams: nodes.filter(n => n.audio && n.isStream)
  readonly property bool available: usable(node)
  readonly property real volume: available ? node.audio.volume : 0
  readonly property bool muted: available && node.audio.muted
  readonly property bool microphoneAvailable: usable(source)
  readonly property real microphoneVolume: microphoneAvailable ? source.audio.volume : 0
  readonly property bool microphoneMuted: microphoneAvailable && source.audio.muted
  function usable(item) {
    return item !== null && item.ready && item.audio !== null;
  }
  function setNodeVolume(item, value) {
    if (usable(item) && Number.isFinite(value))
      item.audio.volume = Math.max(0, Math.min(1, value));
  }
  function setNodeMuted(item, value) {
    if (usable(item))
      item.audio.muted = value;
  }
  function setVolume(value) {
    setNodeVolume(node, value);
  }
  function setMuted(value) {
    setNodeMuted(node, value);
  }
  function select(item, input) {
    if (!usable(item))
      return;
    if (input)
      Pipewire.preferredDefaultAudioSource = item;
    else
      Pipewire.preferredDefaultAudioSink = item;
  }
  PwObjectTracker {
    objects: root.detailed ? root.nodes : [root.node, root.source].filter(n => n !== null)
  }
}
