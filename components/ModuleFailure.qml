import QtQuick
import QtQuick.Layouts
import "../core"

ColumnLayout {
  id: root
  required property string moduleId
  property string title: "Este componente no se pudo cargar"
  spacing: 12
  SectionTitle {
    text: root.title
  }
  Label {
    Layout.fillWidth: true
    wrapMode: Text.WordWrap
    text: Resilience.blocked(root.moduleId) ? "Se desactivó temporalmente tras varios fallos. Tus ajustes se conservan." : "Los demás componentes siguen disponibles. Puedes volver a intentarlo."
  }
  ActionButton {
    text: "Reintentar componente"
    onClicked: Resilience.retry(root.moduleId)
  }
  ActionButton {
    text: "Modo de recuperación"
    enabled: !Bridge.preview
    onClicked: Resilience.recover()
  }
  Accessible.role: Accessible.AlertMessage
  Accessible.name: title
}
