pragma Singleton
import QtQuick
import Quickshell
import "osdState.js" as State

Singleton {
  id: root
  property bool visible: false
  property string kind: "volume"
  property real value: 0
  property bool muted: false
  property bool demo: false
  property var samples: ({})
  readonly property string title: kind === "brightness" ? "Brillo" : kind === "microphone" ? "Micrófono" : "Volumen"
  readonly property string icon: kind === "brightness" ? "sun" : kind === "microphone" ? muted ? "microphone-off" : "microphone" : muted ? "muted" : "volume"
  readonly property string outputSignature: JSON.stringify({
    id: Audio.node ? Audio.node.id : "",
    value: Audio.volume,
    muted: Audio.muted,
    available: Audio.available
  })
  readonly property string inputSignature: JSON.stringify({
    id: Audio.source ? Audio.source.id : "",
    value: Audio.microphoneVolume,
    muted: Audio.microphoneMuted,
    available: Audio.microphoneAvailable
  })
  readonly property string brightnessSignature: JSON.stringify({
    id: "backlight",
    value: (Bridge.system.brightness || 0) / 100,
    muted: false,
    available: !!Bridge.system.brightnessAvailable
  })
  onOutputSignatureChanged: observe("volume", JSON.parse(outputSignature))
  onInputSignatureChanged: observe("microphone", JSON.parse(inputSignature))
  onBrightnessSignatureChanged: observe("brightness", JSON.parse(brightnessSignature))
  function observe(type, sample) {
    const transition = State.update(samples[type], sample, Date.now());
    samples = Object.assign({}, samples, {
      [type]: transition.sample
    });
    if (!Bridge.preview && Bridge.ready && transition.changed)
      show(type, sample.value, sample.muted, false);
  }
  function show(type, amount, silent, demonstration) {
    if (Bridge.settings.osdEnabled === false || !Number.isFinite(amount) || !["volume", "microphone", "brightness"].includes(type))
      return;
    if (!demonstration && (Bridge.preview || Bridge.settingsOnly || Presentation.active))
      return;
    kind = type;
    value = Math.max(0, Math.min(1, amount));
    muted = !!silent;
    demo = !!demonstration;
    visible = true;
    expiry.restart();
  }
  Connections {
    target: Bridge
    function onSettingsChanged() {
      if (Bridge.settings.osdEnabled === false) {
        root.visible = false;
        expiry.stop();
      }
    }
  }
  Timer {
    id: expiry
    interval: Bridge.settings.osdTimeout || 1500
    onTriggered: root.visible = false
  }
}
