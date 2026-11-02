pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Services.Mpris

Singleton {
  id: root
  property string selected: ""
  readonly property var players: Mpris.players.values
  readonly property var player: players.find(p => p.dbusName === selected) || players.find(p => p.isPlaying) || players[0] || null
  readonly property string title: player ? (player.trackTitle || "Pista sin título") : "Sin reproducción activa"
  readonly property string artist: player ? (player.trackArtist || player.identity) : ""
  function playPause() {
    if (!Bridge.preview && player && player.canTogglePlaying)
      player.togglePlaying();
  }
  function previous() {
    if (!Bridge.preview && player && player.canGoPrevious)
      player.previous();
  }
  function next() {
    if (!Bridge.preview && player && player.canGoNext)
      player.next();
  }
  function time(value) {
    return Math.floor(value / 60) + ":" + String(Math.floor(value % 60)).padStart(2, "0");
  }
  Timer {
    interval: 1000
    repeat: true
    running: root.player !== null && root.player.isPlaying && ShellState.panel === "media"
    onTriggered: {
      if (root.player)
        root.player.positionChanged();
    }
  }
}
