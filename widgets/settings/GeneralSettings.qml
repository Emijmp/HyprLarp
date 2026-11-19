import QtQuick
import QtQuick.Layouts
import "../../core"
import "../../components"
import "." as SettingsControls

ColumnLayout {
  spacing: 18
  SettingsControls.AccessibilitySettings {
    Layout.fillWidth: true
  }
  Rule {}
  SectionTitle {
    objectName: "setting-performance"
    text: "Rendimiento del shell"
  }
  Label {
    Layout.fillWidth: true
    wrapMode: Text.WordWrap
    color: Theme.muted
    text: "Consulta CPU y memoria de HyprLarp, sus tiempos de arranque y compara mediciones guardadas. El muestreo se detiene al cerrar el panel."
  }
  SettingChoice {
    objectName: "setting-performance-mode"
    title: "Perfil de actividad del shell"
    choices: ["efficient", "balanced", "responsive"]
    labels: ["Eficiente · menos sondeos y efectos", "Equilibrado", "Ágil · actualizaciones más frecuentes"]
    value: Bridge.settings.performanceMode || "balanced"
    onEdited: value => Bridge.configure("performanceMode", value)
  }
  Label {
    Layout.fillWidth: true
    wrapMode: Text.WordWrap
    color: Theme.muted
    font.pixelSize: Theme.fontPx(11)
    text: "El perfil eficiente reduce sondeos de sistema, desactiva desenfoques y animaciones y ayuda a mantener estable el uso de CPU y memoria. El panel Rendimiento conserva su intervalo de medición para que las comparaciones sigan siendo útiles."
  }
  ActionButton {
    text: "Abrir rendimiento"
    onClicked: ShellState.open("performance")
  }
  Rule {}
  SectionTitle {
    objectName: "setting-clock"
    text: "Reloj y fecha"
  }
  SettingChoice {
    objectName: "setting-clockFormat"
    title: "Formato de hora"
    choices: ["24h", "12h"]
    labels: ["24 horas", "12 horas · AM/PM"]
    value: Bridge.settings.clockFormat || "24h"
    onEdited: value => Bridge.configure("clockFormat", value)
  }
  SettingToggle {
    objectName: "setting-clockSeconds"
    title: "Mostrar segundos"
    checked: !!Bridge.settings.clockSeconds
    onEdited: checked => Bridge.configure("clockSeconds", checked)
  }
  SettingChoice {
    objectName: "setting-clockDateFormat"
    title: "Formato de fecha"
    choices: ["dd/MM", "dd/MM/yyyy", "MM/dd/yyyy", "yyyy-MM-dd", "ddd, d MMM"]
    labels: ["31/12", "31/12/2026", "12/31/2026", "2026-12-31", "jue, 31 dic"]
    value: Bridge.settings.clockDateFormat || "dd/MM/yyyy"
    onEdited: value => Bridge.configure("clockDateFormat", value)
  }
  Label {
    text: "Vista previa · " + Clock.timeText + " · " + Clock.dateText
    color: Theme.muted
    font.pixelSize: Theme.fontPx(11)
    Layout.fillWidth: true
  }
  Rule {}
  SectionTitle {
    objectName: "setting-calendar"
    text: "Calendario"
  }
  SettingChoice {
    title: "Primer día de la semana"
    choices: ["monday", "sunday"]
    labels: ["Lunes", "Domingo"]
    value: Bridge.settings.calendarFirstDay || "monday"
    onEdited: value => Bridge.configure("calendarFirstDay", value)
  }
  SettingToggle {
    title: "Mostrar números de semana · ISO"
    checked: !!Bridge.settings.calendarWeekNumbers
    onEdited: checked => Bridge.configure("calendarWeekNumbers", checked)
  }
  Label {
    visible: !!Bridge.settings.calendarWeekNumbers && Bridge.settings.calendarFirstDay === "sunday"
    text: "El número ISO corresponde al lunes de cada fila."
    color: Theme.muted
    font.pixelSize: Theme.fontPx(10)
    Layout.fillWidth: true
  }
  Rule {}
  SectionTitle {
    objectName: "setting-batteryAlerts"
    text: "Avisos de batería"
  }
  SettingToggle {
    title: "Avisar cuando la batería esté baja"
    checked: Bridge.settings.batteryAlertsEnabled !== false
    onEdited: checked => Bridge.configure("batteryAlertsEnabled", checked)
  }
  SettingSlider {
    title: "Batería baja"
    enabled: Bridge.settings.batteryAlertsEnabled !== false
    from: (Bridge.settings.batteryAlertLevels?.critical || 10) + 1
    to: 99
    step: 1
    suffix: "%"
    value: Bridge.settings.batteryAlertLevels?.low || 20
    onEdited: value => Bridge.configure("batteryAlertLevels", {
        low: value,
        critical: Bridge.settings.batteryAlertLevels?.critical || 10
      })
  }
  SettingSlider {
    title: "Batería crítica"
    enabled: Bridge.settings.batteryAlertsEnabled !== false
    from: 1
    to: (Bridge.settings.batteryAlertLevels?.low || 20) - 1
    step: 1
    suffix: "%"
    value: Bridge.settings.batteryAlertLevels?.critical || 10
    onEdited: value => Bridge.configure("batteryAlertLevels", {
        low: Bridge.settings.batteryAlertLevels?.low || 20,
        critical: value
      })
  }
  Label {
    text: "Un aviso por nivel durante la descarga. Se rearman al conectar el cargador o recuperar suficiente carga. Presentación oculta los avisos; con No molestar solo aparece el crítico."
    wrapMode: Text.WordWrap
    color: Theme.muted
    font.pixelSize: Theme.fontPx(10)
    Layout.fillWidth: true
  }
  Rule {}
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
    font.pixelSize: Theme.fontPx(10)
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
    text: "Los ajustes se guardan automáticamente. Deshacer, Rehacer y Restablecer funcionan con esta ventana enfocada. El historial conserva hasta 50 cambios de configuración, incluso al reiniciar. En Perfiles puedes comparar y restaurar las últimas 30 versiones. Los cambios de atajos requieren el botón Aplicar atajos."
    wrapMode: Text.WordWrap
    Layout.fillWidth: true
    font.pixelSize: Theme.fontPx(11)
    color: Theme.muted
  }
  Rule {}
  SettingsControls.DiagnosticsSettings {
    Layout.fillWidth: true
  }
  Rule {}
  SettingsControls.RecoverySettings {
    Layout.fillWidth: true
  }
}
