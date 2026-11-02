import QtQuick
import QtQuick.Layouts
import "../../core"
import "../../components"

ColumnLayout {
  spacing: 18
  SettingToggle {
    title: "Historial del portapapeles"
    checked: !!Bridge.settings.clipboardEnabled
    onEdited: checked => Bridge.configure("clipboardEnabled", checked)
  }
  SettingSlider {
    title: "Notificaciones guardadas"
    from: 0
    to: 500
    step: 10
    suffix: ""
    value: Bridge.settings.notificationHistoryLimit
    onEdited: value => Bridge.configure("notificationHistoryLimit", value)
  }
  SettingToggle {
    title: "Iconos originales de aplicaciones en el launcher"
    checked: !!Bridge.settings.showAppIcons
    onEdited: checked => Bridge.configure("showAppIcons", checked)
  }
  SettingSlider {
    title: "Caducidad del portapapeles · 0 conserva todo"
    from: 0
    to: 8760
    step: 1
    suffix: " h"
    value: Bridge.settings.clipboardRetentionHours || 0
    onEdited: value => Bridge.configure("clipboardRetentionHours", value)
  }
  Label {
    text: "La caducidad empieza a contar al observar cada entrada. Los fijados no caducan."
    Layout.fillWidth: true
    wrapMode: Text.WordWrap
    color: Theme.muted
    font.pixelSize: 10
  }
  SectionTitle {
    text: "OSD · volumen, micrófono y brillo"
  }
  SettingToggle {
    title: "Mostrar indicadores de nivel"
    checked: Bridge.settings.osdEnabled !== false
    onEdited: checked => Bridge.configure("osdEnabled", checked)
  }
  SettingSlider {
    title: "Duración"
    from: 500
    to: 5000
    step: 100
    suffix: " ms"
    value: Bridge.settings.osdTimeout || 1500
    onEdited: value => Bridge.configure("osdTimeout", value)
  }
  SettingChoice {
    title: "Posición del OSD"
    choices: ["bottom", "top"]
    labels: ["Abajo", "Arriba"]
    value: Bridge.settings.osdPosition || "bottom"
    onEdited: value => Bridge.configure("osdPosition", value)
  }
  ActionButton {
    text: "Probar OSD"
    enabled: Bridge.settings.osdEnabled !== false
    onClicked: Osd.show("volume", 0.5, false, true)
  }
  Rule {}
  SectionTitle {
    text: "Modo nocturno / descanso visual"
  }
  NightControls {
    configurationEditor: true
    Layout.fillWidth: true
  }
  Rule {}
  NotificationRules {
    Layout.fillWidth: true
  }
  Rule {}
  SectionTitle {
    text: "HyprLarp 0.5"
  }
  Label {
    text: "Los ajustes se guardan automáticamente. Deshacer, Rehacer y Restablecer funcionan con esta ventana enfocada. El historial conserva hasta 50 cambios hechos desde configuración durante la sesión del shell. Los cambios de atajos requieren el botón Aplicar atajos."
    wrapMode: Text.WordWrap
    Layout.fillWidth: true
    font.pixelSize: 11
    color: Theme.muted
  }
}
