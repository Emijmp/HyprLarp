import QtQuick
import QtQuick.Layouts
import "../core"
import "../components"

ColumnLayout {
  id: root
  spacing: 10
  property int delay: 0
  property bool annotate: false
  property bool frozen: false
  SettingChoice {
    title: "Modo de captura"
    choices: ["dynamic", "frozen"]
    labels: ["Dinámica", "Estática"]
    value: root.frozen ? "frozen" : "dynamic"
    onEdited: value => root.frozen = value === "frozen"
  }
  Label {
    text: root.frozen ? "La pantalla se congela mientras seleccionas el área. Esc cancela." : "La pantalla sigue actualizándose mientras seleccionas el área."
    color: Theme.muted
    wrapMode: Text.WordWrap
    font.pixelSize: Theme.fontPx(11)
    Layout.fillWidth: true
  }
  SettingChoice {
    title: "Temporizador"
    choices: ["0", "3", "5", "10"]
    labels: ["Sin espera", "3 s", "5 s", "10 s"]
    value: String(root.delay)
    onEdited: value => root.delay = Number(value)
  }
  SettingToggle {
    title: "Editar antes de guardar"
    checked: root.annotate
    onEdited: checked => root.annotate = checked
  }
  ControlRow {
    title: "Seleccionar región"
    detail: root.frozen ? "Ctrl + Impr Pant · estática" : "Impr Pant · dinámica"
    onClicked: ShellState.capture("region", root.delay, root.annotate, root.frozen)
  }
  ControlRow {
    title: "Ventana activa"
    detail: "Área de la ventana enfocada"
    onClicked: ShellState.capture("window", root.delay, root.annotate, root.frozen)
  }
  ControlRow {
    title: "Escritorio completo"
    detail: "Shift + Impr Pant"
    onClicked: ShellState.capture("screen", root.delay, root.annotate, root.frozen)
  }
  Rule {}
  Label {
    text: "PNG en Imágenes / Screenshots y en el portapapeles. El editor permite recorte, flechas, texto y ocultación sólida."
    color: Theme.muted
    wrapMode: Text.WordWrap
    font.pixelSize: Theme.fontPx(11)
    Layout.fillWidth: true
  }
}
