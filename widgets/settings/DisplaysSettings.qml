import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import "../../core"
import "../../components"
import "../../core/displays.js" as Displays

ColumnLayout {
  id: root
  objectName: "displaysEditor"
  Layout.fillWidth: true
  spacing: 12
  readonly property var outputs: Bridge.displays.outputs || []
  property var draft: []
  property string selectedName: ""
  property string relativeName: ""
  property bool dirty: false
  property bool wasPending: false
  readonly property bool pending: !!Bridge.displays.pending
  readonly property var selected: draft.find(output => output.name === selectedName) || null
  readonly property var info: outputs.find(output => output.name === selectedName) || ({
      modes: []
    })
  readonly property var references: draft.filter(output => output.name !== selectedName && output.enabled && !output.mirror)
  readonly property bool editable: !!selected && !pending

  function resetDraft() {
    draft = Displays.plan(outputs);
    if (!draft.some(output => output.name === selectedName))
      selectedName = draft.length ? draft[0].name : "";
    dirty = false;
  }
  function update(values) {
    if (!selected)
      return;
    draft = draft.map(output => output.name === selectedName ? Object.assign({}, output, values) : output);
    dirty = true;
  }
  function chooseResolution(value) {
    const mode = value === "preferred" ? value : info.modes.find(mode => Displays.resolution(mode) === value && mode.split("@")[1] === selected.mode.split("@")[1]) || info.modes.find(mode => Displays.resolution(mode) === value);
    const next = Object.assign({}, selected, {
      mode: mode
    });
    const valid = Displays.scales(next, info);
    update({
      mode: mode,
      scale: valid.includes(String(selected.scale)) ? selected.scale : 1
    });
  }
  function place(side) {
    const other = references.find(output => output.name === relativeName) || references[0];
    if (!other || !selected)
      return;
    const own = Displays.size(selected, info), dimensions = Displays.size(other, outputs.find(output => output.name === other.name));
    update({
      mirror: "",
      x: Math.round(side === "right" ? other.x + dimensions.width : side === "left" ? other.x - own.width : other.x),
      y: Math.round(side === "below" ? other.y + dimensions.height : side === "above" ? other.y - own.height : other.y)
    });
  }
  function move(name, x, y) {
    draft = Displays.move(draft, name, x, y, outputs);
    dirty = true;
  }
  Component.onCompleted: {
    resetDraft();
    Bridge.perform("displays-refresh");
  }
  Connections {
    target: Bridge
    function onDisplaysChanged() {
      const changed = root.draft.map(output => output.name).sort().join("|") !== root.outputs.map(output => output.name).sort().join("|");
      if (!root.dirty || root.wasPending || changed || root.pending)
        root.resetDraft();
      root.wasPending = root.pending;
    }
  }
  RowLayout {
    Layout.fillWidth: true
    SectionTitle {
      text: "Pantallas conectadas"
      Layout.fillWidth: true
    }
    ActionButton {
      text: "Actualizar"
      enabled: !root.pending && !Bridge.isBusy("displays-refresh")
      onClicked: Bridge.perform("displays-refresh")
    }
    ActionButton {
      text: "Proyectar…"
      enabled: !Bridge.settingsOnly
      onClicked: ShellState.open("displays")
    }
  }
  Label {
    text: "Selecciona una pantalla y arrástrala para colocarla. Los cambios se prueban antes de guardarse."
    color: Theme.muted
    font.pixelSize: Theme.fontPx(11)
    wrapMode: Text.WordWrap
    Layout.fillWidth: true
  }
  EmptyState {
    visible: !Bridge.displays.available && !root.outputs.length
    error: true
    title: "Pantallas no disponibles"
    description: Bridge.displays.error || "Abre HyprLarp desde una sesión de Hyprland y pulsa Actualizar."
  }
  ProjectionOptions {
    compact: true
    visible: root.outputs.length > 0
  }
  DisplayArrangement {
    visible: root.outputs.length > 0
    outputs: root.draft
    information: root.outputs
    selected: root.selectedName
    interactive: !root.pending
    onSelectedOutput: name => root.selectedName = name
    onMoved: (name, x, y) => root.move(name, x, y)
  }
  Flow {
    Layout.fillWidth: true
    spacing: 6
    Repeater {
      model: root.draft
      ActionButton {
        required property var modelData
        required property int index
        text: (index + 1) + " · " + modelData.name + (!modelData.enabled ? " · Apagada" : modelData.mirror ? " · Duplica " + modelData.mirror : "")
        selected: root.selectedName === modelData.name
        onClicked: root.selectedName = modelData.name
      }
    }
  }
  ColumnLayout {
    visible: !!root.selected
    Layout.fillWidth: true
    spacing: 12
    enabled: root.editable
    Label {
      text: root.info.description || ""
      color: Theme.muted
      Layout.fillWidth: true
      wrapMode: Text.WordWrap
    }
    SettingToggle {
      title: "Usar esta pantalla"
      checked: root.selected ? root.selected.enabled : false
      onEdited: value => {
        root.update({
          enabled: value
        });
        if (value && root.references.length)
          root.place("right");
      }
    }
    GridLayout {
      Layout.fillWidth: true
      columns: 2
      columnSpacing: 18
      rowSpacing: 10
      Label {
        text: "Resolución"
      }
      Selection {
        Layout.fillWidth: true
        choices: Displays.resolutions(root.info)
        labels: choices.map(mode => mode === "preferred" ? "Recomendada" : mode.replace("x", " × "))
        value: root.selected ? Displays.resolution(root.selected.mode) : "preferred"
        onEdited: value => root.chooseResolution(value)
      }
      Label {
        text: "Frecuencia"
      }
      Selection {
        Layout.fillWidth: true
        choices: root.selected ? Displays.rates(root.selected, root.info) : []
        labels: choices.map(rate => rate === "auto" ? "Automática" : rate + " Hz")
        value: root.selected && root.selected.mode !== "preferred" ? root.selected.mode.split("@")[1] : "auto"
        onEdited: value => {
          if (value !== "auto")
            root.update({
              mode: Displays.resolution(root.selected.mode) + "@" + value
            });
        }
      }
      Label {
        text: "Escala"
      }
      Selection {
        Layout.fillWidth: true
        choices: root.selected ? Displays.scales(root.selected, root.info) : []
        labels: choices.map(value => Math.round(Number(value) * 100) + " %")
        value: root.selected ? String(root.selected.scale) : "1"
        onEdited: value => root.update({
            scale: Number(value)
          })
      }
      Label {
        text: "Orientación"
      }
      Selection {
        Layout.fillWidth: true
        choices: ["0", "1", "2", "3"]
        labels: ["Normal", "90°", "180°", "270°"]
        value: root.selected ? String(root.selected.transform) : "0"
        onEdited: value => root.update({
            transform: Number(value)
          })
      }
      Label {
        text: "Contenido"
      }
      Selection {
        Layout.fillWidth: true
        choices: [""].concat(root.references.map(output => output.name))
        labels: ["Escritorio independiente"].concat(root.references.map(output => "Duplicar " + output.name))
        value: root.selected ? root.selected.mirror : ""
        onEdited: value => {
          root.update({
            mirror: value
          });
          if (!value && root.references.length)
            root.place("right");
        }
      }
    }
    RowLayout {
      visible: root.selected && !root.selected.mirror
      spacing: 10
      Label {
        text: "Posición X"
      }
      Field {
        objectName: "displayPositionX"
        Layout.preferredWidth: 100
        text: root.selected ? String(root.selected.x) : "0"
        validator: IntValidator {
          bottom: -32768
          top: 32768
        }
        onEditingFinished: if (acceptableInput)
          root.update({
            x: Number(text)
          })
      }
      Label {
        text: "Y"
      }
      Field {
        objectName: "displayPositionY"
        Layout.preferredWidth: 100
        text: root.selected ? String(root.selected.y) : "0"
        validator: IntValidator {
          bottom: -32768
          top: 32768
        }
        onEditingFinished: if (acceptableInput)
          root.update({
            y: Number(text)
          })
      }
      Item {
        Layout.fillWidth: true
      }
    }
    RowLayout {
      visible: root.references.length > 0 && root.selected && !root.selected.mirror
      Label {
        text: "Colocar respecto a"
      }
      Selection {
        Layout.fillWidth: true
        choices: root.references.map(output => output.name)
        value: root.relativeName || (root.references.length ? root.references[0].name : "")
        onEdited: value => root.relativeName = value
      }
    }
    Flow {
      visible: root.references.length > 0 && root.selected && !root.selected.mirror
      Layout.fillWidth: true
      spacing: 6
      Repeater {
        model: ["left", "right", "above", "below"]
        ActionButton {
          required property string modelData
          required property int index
          text: ["Izquierda", "Derecha", "Arriba", "Abajo"][index]
          onClicked: root.place(modelData)
        }
      }
    }
  }
  Rule {}
  RowLayout {
    ActionButton {
      objectName: "testDisplayChanges"
      text: "Probar cambios"
      accent: true
      enabled: root.dirty && Bridge.displays.available && !root.pending && !Bridge.preview && !Bridge.isBusy("displays-test")
      onClicked: Bridge.performConfig("displays-test", {
        outputs: root.draft
      })
    }
    ActionButton {
      text: "Descartar edición"
      enabled: root.dirty && !root.pending
      onClicked: root.resetDraft()
    }
    Item {
      Layout.fillWidth: true
    }
  }
  Label {
    text: "Al confirmar se recordará el diseño para estas pantallas. Este diseño se guarda aparte de los temas de apariencia."
    color: Theme.muted
    font.pixelSize: Theme.fontPx(11)
    wrapMode: Text.WordWrap
    Layout.fillWidth: true
  }
  StatusMessage {
    visible: !!Bridge.displays.error || !!Bridge.displays.notice
    text: Bridge.displays.error || Bridge.displays.notice || ""
    error: !!Bridge.displays.error
  }
}
