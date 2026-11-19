import QtQuick
import QtQuick.Layouts
import "../core"
import "../components"
import "../core/workspaces.js" as Workspaces

ColumnLayout {
  id: root
  spacing: 12
  readonly property var screen: ShellState.activeScreen
  readonly property var configuration: BarLayout.forScreen(screen)
  readonly property var actions: ModuleCatalog.definitions.filter(entry => ["panel", "settings", "command", "session", "toggle"].includes(entry.kind))
  BarGeometry {
    id: geometry
    configuration: root.configuration
  }
  SectionTitle {
    text: "Espacios de trabajo"
  }
  Flow {
    Layout.fillWidth: true
    spacing: 6
    Repeater {
      model: Workspaces.entries(Compositor.snapshot, root.screen ? root.screen.name : Compositor.focusedScreenName, root.configuration.barWorkspaceCount || 5)
      ActionButton {
        required property var modelData
        text: "Espacio " + modelData.label
        selected: modelData.active
        enabled: Compositor.enabled && !modelData.unavailable
        onClicked: Compositor.activate(modelData, root.screen)
      }
    }
  }
  SectionTitle {
    text: "Bandeja del sistema"
  }
  GuardedLoader {
    id: tray
    moduleId: "bar:tray"
    source: "../widgets/TrayModule.qml"
    Layout.fillWidth: true
    Layout.preferredHeight: implicitHeight
    onLoaded: {
      item.configuration = Qt.binding(() => root.configuration);
      item.guide = geometry;
      item.screen = Qt.binding(() => root.screen);
      item.keyboardPanel = true;
    }
  }
  ModuleFailure {
    moduleId: "bar:tray"
    visible: tray.status === Loader.Error || Resilience.blocked(moduleId)
    Layout.fillWidth: true
  }
  SectionTitle {
    text: "Acciones del shell"
  }
  Flow {
    Layout.fillWidth: true
    spacing: 6
    Repeater {
      model: root.actions
      ActionButton {
        required property var modelData
        text: modelData.title
        enabled: ModuleCatalog.commandAvailable(modelData.id)
        onClicked: ModuleCatalog.activate(modelData.id, root.screen)
      }
    }
  }
}
