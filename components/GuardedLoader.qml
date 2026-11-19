import QtQuick
import "../core"

Loader {
  id: root
  required property string moduleId
  active: !Resilience.blocked(moduleId)
  onStatusChanged: if (status === Loader.Error)
    Resilience.report(moduleId, "No se pudo cargar el componente " + moduleId)
  Connections {
    target: Resilience
    function onRetryRequested(id) {
      if (id !== root.moduleId)
        return;
      root.active = false;
      Qt.callLater(() => root.active = Qt.binding(() => !Resilience.blocked(root.moduleId)));
    }
  }
}
