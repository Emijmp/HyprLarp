import QtQuick
import QtQuick.Layouts
import "../../core"
import "../../components"

ColumnLayout {
  spacing: 14
  SectionTitle {
    objectName: "setting-accessibility"
    text: "Accesibilidad"
  }
  SettingSlider {
    title: "Tamaño del texto"
    from: 1
    to: 2
    step: .05
    value: Bridge.settings.accessibilityTextScale || 1
    displayValue: Math.round(value * 100) + "%"
    onEdited: value => Bridge.configure("accessibilityTextScale", value)
  }
  SettingSlider {
    objectName: "setting-minimum-font-size"
    title: "Tamaño mínimo del texto pequeño"
    from: 10
    to: 18
    step: 1
    suffix: " px"
    value: Bridge.settings.accessibilityMinimumFontSize || 12
    onEdited: value => Bridge.configure("accessibilityMinimumFontSize", value)
  }
  Label {
    Layout.fillWidth: true
    wrapMode: Text.WordWrap
    color: Theme.muted
    text: "Aumenta etiquetas y notas pequeñas además del escalado global. Los paneles se desplazan para mantener accesibles los controles."
  }
  SettingToggle {
    title: "Alto contraste"
    checked: !!Bridge.settings.accessibilityHighContrast
    onEdited: checked => Bridge.configure("accessibilityHighContrast", checked)
  }
  SettingToggle {
    title: "Controles más grandes"
    checked: !!Bridge.settings.accessibilityLargeTargets
    onEdited: checked => Bridge.configure("accessibilityLargeTargets", checked)
  }
  SettingToggle {
    title: "Reducir movimiento"
    checked: !!Bridge.settings.accessibilityReducedMotion
    onEdited: checked => Bridge.configure("accessibilityReducedMotion", checked)
  }
  Label {
    Layout.fillWidth: true
    wrapMode: Text.WordWrap
    text: "Tab y Mayús+Tab recorren los controles. Enter o Espacio activan botones; las flechas ajustan valores. Escape cierra el panel. Ctrl+F busca ajustes. En el launcher, escribe > barra para acceder a los módulos, espacios y bandeja por teclado."
  }
  Label {
    Layout.fillWidth: true
    wrapMode: Text.WordWrap
    text: "La interfaz expone nombres, estados y acciones mediante AT-SPI para lectores de pantalla como Orca. El lector se administra desde tu sistema."
    color: Theme.muted
  }
}
