import QtQuick
import QtQuick.Layouts
import "../../core"
import "../../components"
import "../../core/panelDraft.js" as PanelDraft
import "." as SettingsControls

ColumnLayout {
  id: root
  objectName: "appearance-settings"
  readonly property bool custom: Bridge.settings.theme === "custom"
  property var panelDraft: PanelDraft.create(Bridge.confirmedSettings)
  readonly property bool panelPreviewPending: PanelDraft.pending(panelDraft)
  readonly property bool panelApplying: panelDraft.submitted !== null
  function editPanel(key, value) {
    panelDraft = PanelDraft.edit(panelDraft, key, value);
  }
  function discardPanel() {
    panelDraft = PanelDraft.create(Bridge.confirmedSettings);
  }
  function applyPanel() {
    if (!panelPreviewPending || panelApplying || !Bridge.connected || Bridge.saving || Bridge.hasPendingSettings)
      return;
    panelDraft = PanelDraft.submit(panelDraft);
    Bridge.configureMany(panelDraft.submitted);
    Bridge.flush(true);
  }
  Connections {
    target: Bridge
    function onConfirmedSettingsChanged() {
      root.panelDraft = PanelDraft.sync(root.panelDraft, Bridge.confirmedSettings);
    }
    function onSettingsSettled() {
      root.panelDraft = PanelDraft.settle(root.panelDraft, Bridge.confirmedSettings);
    }
    function onActionFailed(action, reason) {
      if (action === "settings" && root.panelApplying)
        root.panelDraft = PanelDraft.fail(root.panelDraft, reason);
    }
    function onConnectedChanged() {
      if (!Bridge.connected && root.panelApplying)
        root.panelDraft = PanelDraft.fail(root.panelDraft, "El servicio se desconectó. Revisa el diseño guardado al reconectar.");
    }
  }
  readonly property var extractedWallpaperColors: Bridge.wallpaperPalette.path === Bridge.settings.wallpaper ? Bridge.wallpaperPalette.colors || [] : []
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
  SettingsControls.WindowGapsSettings {}
  Rule {}
  SettingChoice {
    title: "Detalles visuales"
    choices: ["minimal", "subtle"]
    labels: ["Mínimo", "Sutil"]
    value: Bridge.settings.decoration || "subtle"
    onEdited: value => Bridge.configure("decoration", value)
  }
  Repeater {
    model: [
      {
        key: "panelCorners",
        title: "Remates en las esquinas de paneles"
      },
      {
        key: "sectionMarks",
        title: "Marcas junto a los títulos de sección"
      },
      {
        key: "moduleIndicators",
        title: "Indicadores de actividad en módulos"
      },
      {
        key: "separators",
        title: "Líneas divisorias"
      },
      {
        key: "headerIcons",
        title: "Iconos en cabeceras de paneles"
      },
      {
        key: "notificationMarks",
        title: "Marca lateral en notificaciones"
      }
    ]
    SettingToggle {
      required property var modelData
      title: modelData.title
      enabled: Theme.decorated
      checked: (Bridge.settings.decorationOptions || {})[modelData.key] !== false
      onEdited: checked => Theme.setDetail(modelData.key, checked)
    }
  }
  SectionTitle {
    text: "Tema"
  }
  SettingToggle {
    objectName: "setting-theme-schedule"
    title: "Cambiar tema según el horario"
    checked: !!Bridge.settings.themeScheduleEnabled
    onEdited: checked => Bridge.configure("themeScheduleEnabled", checked)
  }
  RowLayout {
    visible: !!Bridge.settings.themeScheduleEnabled
    Layout.fillWidth: true
    SettingChoice {
      Layout.fillWidth: true
      title: "Tema de día"
      choices: Object.keys(Theme.palettes).filter(name => name !== "custom")
      labels: Object.keys(Theme.palettes).filter(name => name !== "custom").map(name => Theme.palettes[name].name)
      value: Bridge.settings.themeDay || "paper"
      onEdited: value => Bridge.configure("themeDay", value)
    }
    SettingChoice {
      Layout.fillWidth: true
      title: "Tema de noche"
      choices: Object.keys(Theme.palettes).filter(name => name !== "custom")
      labels: Object.keys(Theme.palettes).filter(name => name !== "custom").map(name => Theme.palettes[name].name)
      value: Bridge.settings.themeNight || "amoled"
      onEdited: value => Bridge.configure("themeNight", value)
    }
  }
  RowLayout {
    visible: !!Bridge.settings.themeScheduleEnabled
    Layout.fillWidth: true
    Label {
      text: "Día desde"
      color: Theme.muted
    }
    Field {
      Layout.preferredWidth: 100
      text: Bridge.settings.themeDayStart || "07:00"
      Accessible.name: "Hora de inicio del tema diurno"
      validator: RegularExpressionValidator {
        regularExpression: /(?:[01]\d|2[0-3]):[0-5]\d/
      }
      onEditingFinished: Bridge.configure("themeDayStart", text)
    }
    Label {
      text: "Noche desde"
      color: Theme.muted
    }
    Field {
      Layout.preferredWidth: 100
      text: Bridge.settings.themeNightStart || "19:00"
      Accessible.name: "Hora de inicio del tema nocturno"
      validator: RegularExpressionValidator {
        regularExpression: /(?:[01]\d|2[0-3]):[0-5]\d/
      }
      onEditingFinished: Bridge.configure("themeNightStart", text)
    }
  }
  Label {
    visible: !!Bridge.settings.themeScheduleEnabled
    Layout.fillWidth: true
    wrapMode: Text.WordWrap
    text: "El horario usa la hora local y actualiza el shell automáticamente."
    color: Theme.muted
    font.pixelSize: Theme.fontPx(11)
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
          font.pixelSize: Theme.fontPx(12)
        }
        Label {
          text: Theme.palettes[option.modelData].surface
          color: Theme.muted
          font.family: Theme.mono
          font.pixelSize: Theme.fontPx(11)
        }
        ActionButton {
          text: Theme.scheduledTheme === option.modelData ? "Activo" : "Elegir"
          selected: Theme.scheduledTheme === option.modelData
          onClicked: Theme.apply(option.modelData)
        }
      }
    }
  }
  SectionTitle {
    objectName: "setting-theme-preview"
    text: "Vista previa de temas"
  }
  Label {
    text: "Compara barra, panel, acento y texto antes de aplicar una paleta."
    color: Theme.muted
    wrapMode: Text.WordWrap
    Layout.fillWidth: true
  }
  Flow {
    Layout.fillWidth: true
    spacing: 10
    Repeater {
      model: Object.keys(Theme.palettes)
      Item {
        id: previewOption
        required property string modelData
        width: root.width >= Theme.px(520) ? (root.width - 12) / 2 : root.width
        implicitHeight: previewCard.implicitHeight
        ThemePreview {
          id: previewCard
          width: previewOption.width
          themeId: previewOption.modelData
          palette: Theme.palettes[previewOption.modelData]
          selected: Theme.scheduledTheme === previewOption.modelData
          onApplyRequested: name => Theme.apply(name)
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
      font.pixelSize: Theme.fontPx(11)
      wrapMode: Text.WordWrap
      Layout.fillWidth: true
    }
    RowLayout {
      Label {
        text: "Nombre"
        Layout.fillWidth: true
      }
      Field {
        Accessible.name: "Nombre del tema personalizado"
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
  SectionTitle {
    objectName: "setting-wallpaper-colors"
    text: "Colores del fondo"
  }
  Label {
    Layout.fillWidth: true
    wrapMode: Text.WordWrap
    color: Theme.muted
    text: Bridge.externalWallpaper ? "Waypaper administra el fondo actual; selecciona una imagen desde HyprLarp para extraer sus colores." : "Extrae hasta seis colores del fondo seleccionado. El análisis es local y no cambia el tema hasta que elijas un color."
  }
  ActionButton {
    objectName: "extract-wallpaper-colors"
    text: Bridge.isBusy("wallpaper-palette-extract") ? "Analizando fondo…" : "Extraer colores del fondo"
    enabled: !!Bridge.settings.wallpaper && !Bridge.externalWallpaper && !Bridge.isBusy("wallpaper-palette-extract")
    onClicked: Bridge.perform("wallpaper-palette-extract")
  }
  Label {
    visible: root.extractedWallpaperColors.length > 0
    Layout.fillWidth: true
    text: "Colores de " + Bridge.wallpaperPalette.name + " · elige una variante legible como acento"
    color: Theme.muted
    wrapMode: Text.WordWrap
  }
  Flow {
    visible: root.extractedWallpaperColors.length > 0
    Layout.fillWidth: true
    spacing: 8
    Repeater {
      model: root.extractedWallpaperColors
      ColumnLayout {
        id: swatch
        required property string modelData
        readonly property string adjusted: Theme.safeAccent(modelData)
        readonly property bool changed: adjusted.toLowerCase() !== modelData.toLowerCase()
        spacing: 4
        RowLayout {
          spacing: 5
          Repeater {
            model: [swatch.modelData, swatch.adjusted]
            Rectangle {
              required property string modelData
              width: Theme.controlHeight(22)
              height: Theme.controlHeight(22)
              radius: Theme.radiusFor("button")
              color: modelData
              border.width: 1
              border.color: Theme.border
              Accessible.ignored: true
            }
          }
          Label {
            text: swatch.modelData
            font.family: Theme.mono
            font.pixelSize: Theme.fontPx(10)
          }
        }
        Label {
          text: swatch.changed ? "Original → ajustado para contraste" : "Original · contraste suficiente"
          color: Theme.muted
          font.pixelSize: Theme.fontPx(10)
        }
        ActionButton {
          text: "Usar " + swatch.adjusted
          selected: Theme.accent.toString().toLowerCase() === swatch.adjusted
          hint: "Usar la variante legible del color " + swatch.modelData + " como acento"
          onClicked: Bridge.configure("accent", swatch.adjusted)
        }
      }
    }
  }
  RowLayout {
    Label {
      text: "Tipografía"
      Layout.fillWidth: true
    }
    Field {
      Accessible.name: "Tipografía"
      Layout.preferredWidth: 220
      text: Bridge.settings.font || "Inter"
      onEditingFinished: Bridge.configure("font", text)
    }
  }
  Rule {}
  SettingChoice {
    title: "Pantalla de inicio de sesión"
    choices: ["sidebar", "centered"]
    labels: ["Barra lateral", "Centrado"]
    value: Bridge.settings.greeterLayout || "sidebar"
    onEdited: value => Bridge.configure("greeterLayout", value)
  }
  SettingsControls.GreeterPreview {}
  Label {
    text: "Vista aproximada con tu fondo y tema actuales. El diseño se guarda automáticamente y también se utiliza en el bloqueo."
    font.pixelSize: Theme.fontPx(11)
    color: Theme.muted
    wrapMode: Text.WordWrap
    Layout.fillWidth: true
  }
  Rule {}
  SectionTitle {
    objectName: "setting-panel-layout"
    text: "Diseño y estilo de paneles"
  }
  SettingChoice {
    objectName: "setting-panel-distribution"
    enabled: !root.panelApplying
    title: "Distribución"
    choices: ["floating", "centered", "sidebar"]
    labels: ["Flotante junto a la barra", "Centrada", "Lateral a pantalla completa"]
    value: root.panelDraft.values.panelLayout
    onEdited: value => root.editPanel("panelLayout", value)
  }
  SettingChoice {
    objectName: "setting-panel-surface"
    enabled: !root.panelApplying
    title: "Superficie"
    choices: ["standard", "glass", "flat"]
    labels: ["Estándar", "Vidrio translúcido", "Plana · sin borde"]
    value: root.panelDraft.values.panelStyle
    onEdited: value => root.editPanel("panelStyle", value)
  }
  SettingSlider {
    title: "Opacidad de paneles"
    enabled: !root.panelApplying
    from: 0
    to: 1
    step: 0.01
    value: root.panelDraft.values.panelOpacity
    displayValue: Math.round(value * 100) + "%"
    onEdited: value => root.editPanel("panelOpacity", value)
  }
  SettingToggle {
    title: "Desenfoque en paneles de vidrio"
    enabled: !root.panelApplying && root.panelDraft.values.panelStyle === "glass" && Theme.effectsEnabled
    checked: root.panelDraft.values.panelBlur
    onEdited: checked => root.editPanel("panelBlur", checked)
  }
  PanelDesignPreview {
    Layout.fillWidth: true
    Layout.preferredHeight: implicitHeight
    layoutMode: root.panelDraft.values.panelLayout
    surfaceStyle: root.panelDraft.values.panelStyle
    previewOpacity: root.panelDraft.values.panelOpacity
    blur: root.panelDraft.values.panelBlur
  }
  Flow {
    Layout.fillWidth: true
    spacing: 8
    ActionButton {
      objectName: "apply-panel-design"
      text: root.panelApplying ? "Guardando diseño…" : "Aplicar diseño del panel"
      enabled: root.panelPreviewPending && !root.panelApplying && Bridge.connected && !Bridge.saving && !Bridge.hasPendingSettings
      onClicked: root.applyPanel()
    }
    ActionButton {
      objectName: "discard-panel-preview"
      text: "Descartar vista previa"
      enabled: root.panelPreviewPending && !root.panelApplying
      onClicked: root.discardPanel()
    }
  }
  Label {
    text: "La vista previa usa tu fondo actual. Los cambios son temporales hasta Aplicar; el desenfoque final depende del compositor y se desactiva con alto contraste o el perfil eficiente."
    color: Theme.muted
    wrapMode: Text.WordWrap
    font.pixelSize: Theme.fontPx(11)
    Layout.fillWidth: true
  }
  StatusMessage {
    visible: !!root.panelDraft.error
    text: root.panelDraft.error
    error: true
    Layout.fillWidth: true
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
    font.pixelSize: Theme.fontPx(11)
    color: Theme.muted
    wrapMode: Text.WordWrap
    Layout.fillWidth: true
  }
  Rule {}
  SettingToggle {
    title: "Transiciones cortas de color (80 ms)"
    checked: !!Bridge.settings.animations
    onEdited: checked => Bridge.configure("animations", checked)
  }
}
