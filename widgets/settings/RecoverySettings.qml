import QtQuick
import QtQuick.Layouts
import "../../core"
import "../../components"

ColumnLayout {
  spacing: 12
  SectionTitle {
    objectName: "setting-recovery"
    text: "Fallos y recuperación"
  }
  Label {
    Layout.fillWidth: true
    wrapMode: Text.WordWrap
    text: "Tras tres fallos en cinco minutos, el componente se desactiva temporalmente. El resto sigue disponible y tus ajustes se conservan."
  }
  Repeater {
    model: Bridge.faults
    ColumnLayout {
      required property var modelData
      Layout.fillWidth: true
      Label {
        text: modelData.id + (modelData.blocked ? " · Desactivado temporalmente" : " · Fallo registrado")
        Layout.fillWidth: true
        wrapMode: Text.WordWrap
      }
      StatusMessage {
        text: modelData.message
        error: true
      }
      ActionButton {
        text: "Reintentar componente"
        onClicked: Resilience.retry(modelData.id)
      }
    }
  }
  Label {
    visible: !Bridge.faults.length
    text: "No hay componentes con fallos registrados."
    color: Theme.muted
  }
  ActionButton {
    text: "Abrir modo de recuperación"
    enabled: !Bridge.preview
    onClicked: Resilience.recover()
  }
}
