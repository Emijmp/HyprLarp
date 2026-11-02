import QtQuick
import QtQuick.Layouts
import "../../core"
import "../../components"

ColumnLayout {
  id: root
  spacing: 18
  function minimum(settings) {
    const padding = ["left", "right"].indexOf(settings.barPosition) !== -1 ? settings.barPaddingX : settings.barPaddingY;
    const inner = ["left", "right"].indexOf(settings.barPosition) !== -1 ? settings.modulePaddingX : settings.modulePaddingY;
    return 2 * (padding + settings.barBorderWidth + inner + settings.moduleBorderWidth) + Math.max(settings.barIconSize, settings.barFontSize + 4);
  }
  function geometry(key, value) {
    BarEditor.set(key, value);
  }
  function margin(edge, value) {
    const next = Object.assign({}, BarEditor.settings.barMargins);
    next[edge] = value;
    BarEditor.set("barMargins", next);
  }
  MonitorSelector {}
  SettingToggle {
    title: "Mostrar barra"
    checked: BarEditor.settings.barEnabled !== false
    onEdited: value => BarEditor.set("barEnabled", value)
  }
  SettingChoice {
    title: "Posición"
    choices: ["top", "bottom", "left", "right"]
    labels: ["Arriba", "Abajo", "Izquierda", "Derecha"]
    value: BarEditor.settings.barPosition
    onEdited: value => root.geometry("barPosition", value)
  }
  SettingChoice {
    title: "Alineación"
    choices: ["start", "center", "end"]
    labels: ["Inicio", "Centro", "Final"]
    value: BarEditor.settings.barAlignment
    onEdited: value => BarEditor.set("barAlignment", value)
  }
  SettingSlider {
    title: "Longitud"
    from: 25
    to: 100
    suffix: "%"
    value: BarEditor.settings.barLength ?? 100
    onEdited: value => BarEditor.set("barLength", value)
  }
  SettingSlider {
    title: "Grosor"
    from: Math.max(22, root.minimum(BarEditor.settings))
    to: 128
    value: BarEditor.settings.barSize
    onEdited: value => BarEditor.set("barSize", value)
  }
  Rule {}
  SectionTitle {
    text: "Espaciado"
  }
  SettingSlider {
    title: "Padding horizontal"
    from: 0
    to: 32
    value: BarEditor.settings.barPaddingX
    onEdited: value => root.geometry("barPaddingX", value)
  }
  SettingSlider {
    title: "Padding vertical"
    from: 0
    to: 32
    value: BarEditor.settings.barPaddingY
    onEdited: value => root.geometry("barPaddingY", value)
  }
  SettingSlider {
    title: "Separación entre módulos"
    from: 0
    to: 32
    value: BarEditor.settings.barSpacing
    onEdited: value => BarEditor.set("barSpacing", value)
  }
  Repeater {
    model: ["top", "right", "bottom", "left"]
    SettingSlider {
      required property string modelData
      required property int index
      title: ["Margen superior", "Margen derecho", "Margen inferior", "Margen izquierdo"][index]
      from: 0
      to: 64
      value: BarEditor.settings.barMargins[modelData]
      onEdited: value => root.margin(modelData, value)
    }
  }
  Rule {}
  SectionTitle {
    text: "Superficie"
  }
  SettingSlider {
    title: "Grosor del borde"
    from: 0
    to: 4
    value: BarEditor.settings.barBorderWidth
    onEdited: value => root.geometry("barBorderWidth", value)
  }
  SettingSlider {
    title: "Opacidad"
    from: 0
    to: 1
    step: 0.01
    value: BarEditor.settings.barOpacity
    displayValue: Math.round(value * 100) + "%"
    onEdited: value => BarEditor.set("barOpacity", value)
  }
  SettingToggle {
    title: "Blur de fondo"
    checked: !!BarEditor.settings.barBlur
    onEdited: checked => BarEditor.set("barBlur", checked)
  }
  Label {
    text: "El blur se aprecia con una opacidad menor al 100%."
    font.pixelSize: 11
    color: Theme.muted
    Layout.fillWidth: true
    wrapMode: Text.WordWrap
  }
  Rule {}
  SectionTitle {
    text: "Contenido"
  }
  SettingSlider {
    title: "Tamaño de texto"
    from: 10
    to: 24
    value: BarEditor.settings.barFontSize
    onEdited: value => root.geometry("barFontSize", value)
  }
  SettingSlider {
    title: "Tamaño de iconos"
    from: 10
    to: 24
    value: BarEditor.settings.barIconSize
    onEdited: value => root.geometry("barIconSize", value)
  }
  SettingChoice {
    title: "Indicador de espacios"
    choices: ["current", "dots", "compact"]
    labels: ["Solo actual", "Actual y puntos", "Números compactos"]
    value: BarEditor.settings.barWorkspaceDisplay || "current"
    onEdited: value => BarEditor.set("barWorkspaceDisplay", value)
  }
  SettingSlider {
    title: "Espacios base para navegación"
    from: 1
    to: 10
    suffix: ""
    value: BarEditor.settings.barWorkspaceCount
    onEdited: value => BarEditor.set("barWorkspaceCount", value)
  }
  Label {
    text: "Solo actual muestra únicamente el número activo. Los otros modos permiten añadir puntos o números compactos. La rueda recorre todos los espacios del monitor, aunque no se vean."
    color: Theme.muted
    font.pixelSize: 11
    wrapMode: Text.WordWrap
    Layout.fillWidth: true
  }
  SettingToggle {
    title: "Mostrar etiquetas"
    checked: !!BarEditor.settings.barShowLabels
    onEdited: checked => BarEditor.set("barShowLabels", checked)
  }
  SettingToggle {
    title: "Reservar espacio para ventanas"
    checked: !!BarEditor.settings.barReserveSpace
    onEdited: checked => BarEditor.set("barReserveSpace", checked)
  }
}
