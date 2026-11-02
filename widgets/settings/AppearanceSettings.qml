import QtQuick
import QtQuick.Layouts
import "../../core"
import "../../components"

ColumnLayout {
  id: root
  readonly property bool custom: Bridge.settings.theme === "custom"
  readonly property var colorLabels: ({
      background: "Fondo del escritorio",
      surface: "Barra y paneles",
      raised: "Hover y selección",
      moduleSurface: "Fondo de los módulos",
      border: "Bordes",
      separator: "Separadores",
      text: "Texto e iconos",
      muted: "Texto secundario",
      accent: "Acento y sliders",
      danger: "Acciones de alerta"
    })
  spacing: 18
  SettingChoice {
    title: "Detalles visuales"
    choices: ["minimal", "subtle"]
    labels: ["Mínimo", "Sutil"]
    value: Bridge.settings.decoration || "subtle"
    onEdited: value => Bridge.configure("decoration", value)
  }
  SectionTitle {
    text: "Tema"
  }
  ColumnLayout {
    Layout.fillWidth: true
    spacing: 6
    Repeater {
      model: Object.keys(Theme.palettes)
      RowLayout {
        id: option
        required property string modelData
        Layout.fillWidth: true
        Rectangle {
          implicitWidth: 24
          implicitHeight: 18
          color: Theme.palettes[option.modelData].surface
          border.width: 1
          border.color: Theme.palettes[option.modelData].border
        }
        Label {
          text: option.modelData === "custom" ? "Personalizado · " + Theme.palettes.custom.name : Theme.palettes[option.modelData].name
          Layout.fillWidth: true
          font.pixelSize: 12
        }
        Label {
          text: Theme.palettes[option.modelData].surface
          color: Theme.muted
          font.family: Theme.mono
          font.pixelSize: 11
        }
        ActionButton {
          text: Bridge.settings.theme === option.modelData ? "Activo" : "Elegir"
          selected: Bridge.settings.theme === option.modelData
          onClicked: Theme.apply(option.modelData)
        }
      }
    }
  }
  ActionButton {
    visible: !root.custom
    text: "Personalizar este tema"
    hint: "Crear una copia editable de la paleta actual"
    onClicked: Theme.customize()
  }
  Rule {}
  ColumnLayout {
    visible: root.custom
    spacing: 12
    Layout.fillWidth: true
    SectionTitle {
      text: "Paleta personalizada"
    }
    Label {
      text: "Edita los colores en formato #RRGGBB. Se aplican al terminar cada campo."
      color: Theme.muted
      font.pixelSize: 11
      wrapMode: Text.WordWrap
      Layout.fillWidth: true
    }
    RowLayout {
      Label {
        text: "Nombre"
        Layout.fillWidth: true
      }
      Field {
        Layout.preferredWidth: 220
        maximumLength: 40
        text: Theme.palettes.custom.name
        onEditingFinished: {
          if (text.trim())
            Theme.setCustom("name", text.trim());
          else
            Bridge.toast("Escribe un nombre para el tema", true);
          text = Qt.binding(() => Theme.palettes.custom.name);
        }
      }
    }
    Repeater {
      model: Object.keys(root.colorLabels)
      ColorField {
        required property string modelData
        title: root.colorLabels[modelData]
        value: Theme.palettes.custom[modelData]
        onEdited: color => Theme.setCustom(modelData, color)
      }
    }
  }
  ColorField {
    visible: !root.custom
    title: "Acento"
    value: String(Theme.accent)
    onEdited: color => Bridge.configure("accent", color)
  }
  RowLayout {
    Label {
      text: "Tipografía"
      Layout.fillWidth: true
    }
    Field {
      Layout.preferredWidth: 220
      text: Bridge.settings.font || "Inter"
      onEditingFinished: Bridge.configure("font", text)
    }
  }
  Rule {}
  SectionTitle {
    text: "Redondez"
  }
  SettingSlider {
    title: "Radio general"
    from: 0
    to: 8
    value: Theme.radius
    onEdited: value => Bridge.configure("radius", value)
  }
  Repeater {
    model: ["bar", "panel", "button", "field", "workspace", "notification", "tooltip"]
    ColumnLayout {
      id: corner
      required property string modelData
      readonly property var labels: ({
          bar: "Barra",
          panel: "Paneles y configuración",
          button: "Botones y casillas",
          field: "Campos de texto",
          workspace: "Espacios de trabajo",
          notification: "Avisos de notificación",
          tooltip: "Ayudas emergentes"
        })
      Layout.fillWidth: true
      spacing: 4
      SettingSlider {
        title: corner.labels[corner.modelData]
        from: 0
        to: 8
        value: Theme.radiusFor(corner.modelData)
        onEdited: value => Theme.setRadius(corner.modelData, value)
      }
      ActionButton {
        text: "Heredar radio general"
        enabled: (Bridge.settings.cornerRadii || {})[corner.modelData] !== undefined
        onClicked: Theme.setRadius(corner.modelData, null)
      }
    }
  }
  Label {
    text: "0 px deja esquinas rectas. La redondez de los módulos se ajusta por monitor en Módulos → Aspecto."
    font.pixelSize: 11
    color: Theme.muted
    wrapMode: Text.WordWrap
    Layout.fillWidth: true
  }
  Rule {}
  SettingSlider {
    title: "Opacidad de paneles"
    from: 0
    to: 1
    step: 0.01
    value: Bridge.settings.panelOpacity ?? 1
    displayValue: Math.round(value * 100) + "%"
    onEdited: value => Bridge.configure("panelOpacity", value)
  }
  SettingToggle {
    title: "Transiciones cortas de color (80 ms)"
    checked: !!Bridge.settings.animations
    onEdited: checked => Bridge.configure("animations", checked)
  }
}
