import QtQuick
import Quickshell
import Quickshell.Widgets
import Quickshell.Services.SystemTray
import "../core"
import "../components"

ModuleFrame {
  id: root
  property var guide: BarLayout
  property bool vertical: false
  property var screen: null
  property bool expanded: false
  property bool keyboardPanel: false
  readonly property var allItems: Bridge.preview || Bridge.settingsOnly ? [] : SystemTray.items.values
  readonly property var hiddenIds: Bridge.settings.trayHiddenItems || []
  readonly property var items: allItems.filter(item => expanded || !hiddenIds.includes(item.id))
  readonly property int cell: Math.max(Theme.largeTargets ? 44 : 0, guide.iconSize + 10)
  readonly property int columns: Math.max(1, Math.floor((width - 8) / cell))
  implicitWidth: keyboardPanel ? Math.min(8, Math.max(1, items.length + (hiddenIds.length ? 1 : 0))) * cell + 8 : vertical ? cell + 8 : Math.max(cell, items.length * cell + (hiddenIds.length ? cell : 0)) + 8
  implicitHeight: keyboardPanel ? Math.max(1, Math.ceil((items.length + (hiddenIds.length ? 1 : 0)) / columns)) * cell + 4 : vertical ? Math.max(cell, items.length * cell + (hiddenIds.length ? cell : 0)) + 4 : cell + 4
  opacity: Theme.opacityFor("tray", configuration)
  Icon {
    visible: !root.keyboardPanel && root.allItems.length === 0
    anchors.centerIn: parent
    width: root.guide.iconSize
    height: width
    name: "grid"
    color: Theme.muted
  }
  Label {
    visible: root.keyboardPanel && root.allItems.length === 0
    anchors.fill: parent
    text: "Sin iconos en la bandeja"
    color: Theme.muted
    wrapMode: Text.WordWrap
  }
  Repeater {
    model: root.items
    Item {
      id: entry
      required property var modelData
      required property int index
      activeFocusOnTab: true
      function activate() {
        if (modelData.onlyMenu && modelData.hasMenu) {
          const position = mapToItem(null, 0, height);
          modelData.display(root.QsWindow.window, position.x, position.y);
        } else
          modelData.activate();
      }
      function menu() {
        if (modelData.hasMenu) {
          const position = mapToItem(null, 0, height);
          modelData.display(root.QsWindow.window, position.x, position.y);
        }
      }
      Keys.onReturnPressed: activate()
      Keys.onSpacePressed: activate()
      Keys.onPressed: event => {
        if (event.key === Qt.Key_Menu || (event.key === Qt.Key_F10 && event.modifiers & Qt.ShiftModifier)) {
          menu();
          event.accepted = true;
        }
      }
      Accessible.role: Accessible.Button
      Accessible.name: modelData.tooltipTitle || modelData.title || modelData.id
      Accessible.description: modelData.hasMenu ? "Enter activa. Mayús+F10 abre el menú." : "Enter activa."
      Accessible.onPressAction: activate()
      FocusRing {
        control: entry
      }
      x: root.keyboardPanel ? 4 + index % root.columns * root.cell : root.vertical ? 4 : 4 + index * root.cell
      y: root.keyboardPanel ? 2 + Math.floor(index / root.columns) * root.cell : root.vertical ? 2 + index * root.cell : 2
      width: root.cell
      height: root.cell
      IconImage {
        anchors.centerIn: parent
        width: root.guide.iconSize
        height: width
        source: entry.modelData.icon
      }
      MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        acceptedButtons: Qt.LeftButton | Qt.MiddleButton | Qt.RightButton
        onClicked: event => {
          if (event.button === Qt.RightButton || entry.modelData.onlyMenu) {
            const position = entry.mapToItem(null, 0, entry.height);
            if (entry.modelData.hasMenu)
              entry.modelData.display(root.QsWindow.window, position.x, position.y);
          } else if (event.button === Qt.MiddleButton)
            entry.modelData.secondaryActivate();
          else
            entry.modelData.activate();
        }
        onWheel: event => entry.modelData.scroll(event.angleDelta.y, false)
      }
      Hint {
        visible: mouse.containsMouse
        text: entry.modelData.tooltipTitle || entry.modelData.title || entry.modelData.id
      }
    }
  }
  ActionButton {
    visible: root.hiddenIds.length > 0
    x: root.keyboardPanel ? 4 + root.items.length % root.columns * root.cell : root.vertical ? 4 : 4 + root.items.length * root.cell
    y: root.keyboardPanel ? 2 + Math.floor(root.items.length / root.columns) * root.cell : root.vertical ? 2 + root.items.length * root.cell : 2
    width: root.cell
    height: root.cell
    icon: root.expanded ? "close" : "chevron"
    hint: root.expanded ? "Ocultar bandeja" : "Mostrar iconos ocultos"
    onClicked: root.expanded = !root.expanded
  }
}
