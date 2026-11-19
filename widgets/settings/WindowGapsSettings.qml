import QtQuick
import QtQuick.Layouts
import "../../core"
import "../../components"

ColumnLayout {
  id: root
  objectName: "windowGapsEditor"
  Layout.fillWidth: true
  spacing: 12
  readonly property var outer: Bridge.settings.windowGapsOut || {
    top: 8,
    right: 8,
    bottom: 8,
    left: 8
  }
  readonly property bool linked: Bridge.settings.windowGapsLinked !== false
  function setOuter(value, edge) {
    const next = Object.assign({}, outer);
    if (linked || !edge)
      for (const side of ["top", "right", "bottom", "left"])
        next[side] = value;
    else
      next[edge] = value;
    Bridge.configureMany({
      windowGapsEnabled: true,
      windowGapsOut: next
    });
  }
  function setInner(value) {
    Bridge.configureMany({
      windowGapsEnabled: true,
      windowGapsIn: value
    });
  }
  function setLinked(value) {
    const updates = {
      windowGapsLinked: value
    };
    if (value)
      updates.windowGapsOut = {
        top: outer.top,
        right: outer.top,
        bottom: outer.top,
        left: outer.top
      };
    Bridge.configureMany(updates);
  }
  SectionTitle {
    text: "Separación de ventanas"
  }
  SettingToggle {
    title: "Personalizar desde HyprLarp"
    checked: !!Bridge.settings.windowGapsEnabled
    onEdited: checked => Bridge.configure("windowGapsEnabled", checked)
  }
  Label {
    text: "Ajusta las ventanas en mosaico. La distancia a los bordes se suma al espacio reservado de la barra. Mover un control activa la personalización."
    Layout.fillWidth: true
    color: Theme.muted
    font.pixelSize: Theme.fontPx(11)
    wrapMode: Text.WordWrap
  }
  SettingSlider {
    visible: root.linked
    title: "Distancia a los bordes de la pantalla"
    from: 0
    to: 128
    value: root.outer.top
    onEdited: value => root.setOuter(value, "")
  }
  SettingToggle {
    title: "Ajustar cada borde por separado"
    checked: !root.linked
    onEdited: checked => root.setLinked(!checked)
  }
  Repeater {
    model: root.linked ? [] : ["top", "right", "bottom", "left"]
    SettingSlider {
      required property string modelData
      readonly property var names: ({
          top: "Superior",
          right: "Derecho",
          bottom: "Inferior",
          left: "Izquierdo"
        })
      title: names[modelData] || ""
      from: 0
      to: 128
      value: root.outer[modelData] ?? 8
      onEdited: value => root.setOuter(value, modelData)
    }
  }
  SettingSlider {
    title: "Separación interior entre ventanas"
    from: 0
    to: 64
    value: Bridge.settings.windowGapsIn ?? 4
    onEdited: value => root.setInner(value)
  }
  StatusMessage {
    visible: !Bridge.preview && !!Bridge.windowGapsState.error
    text: Bridge.windowGapsState.error || ""
    error: true
  }
  ActionButton {
    text: "Reintentar aplicación"
    visible: !Bridge.preview && !!Bridge.windowGapsState.error
    enabled: Bridge.configurationActive && !Bridge.isBusy("apply-window-gaps")
    onClicked: Bridge.performConfig("apply-window-gaps")
  }
}
