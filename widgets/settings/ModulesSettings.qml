import QtQuick
import QtQuick.Layouts
import "../../core"
import "../../components"

ColumnLayout {
  id: root
  spacing: 12
  property string draggingModule: ""
  property string category: ""
  property string mode: "layout"
  MonitorSelector {}
  RowLayout {
    ActionButton {
      text: "En la barra · " + ModuleCatalog.selected.length
      selected: root.mode === "layout"
      onClicked: root.mode = "layout"
    }
    ActionButton {
      text: "Añadir · " + ModuleCatalog.available.length
      selected: root.mode === "add"
      onClicked: root.mode = "add"
    }
    ActionButton {
      text: "Aspecto"
      selected: root.mode === "appearance"
      onClicked: root.mode = "appearance"
    }
  }
  ColumnLayout {
    Layout.fillWidth: true
    spacing: 12
    visible: root.mode === "layout"
    Label {
      text: "Arrastra el tirador para ordenar o usa las flechas. El centro conserva su posición mientras haya espacio."
      color: Theme.muted
      font.pixelSize: Theme.fontPx(11)
      wrapMode: Text.WordWrap
      Layout.fillWidth: true
    }
    Item {
      id: dragProxy
      width: 1
      height: 1
      Drag.active: root.draggingModule !== ""
      Drag.keys: ["hyprlarp-module"]
      Drag.hotSpot.x: 0
      Drag.hotSpot.y: 0
    }
    Repeater {
      model: ["start", "center", "end"]
      ColumnLayout {
        id: zoneEntry
        required property string modelData
        Layout.fillWidth: true
        spacing: 6
        SectionTitle {
          text: ({
              start: "Inicio",
              center: "Centro",
              end: "Final"
            })[zoneEntry.modelData]
        }
        Repeater {
          model: root.mode === "layout" ? ModuleCatalog.zones[zoneEntry.modelData] : []
          ColumnLayout {
            id: entry
            required property string modelData
            Layout.fillWidth: true
            spacing: 6
            RowLayout {
              Item {
                Layout.preferredWidth: 24
                Layout.preferredHeight: 28
                Icon {
                  anchors.centerIn: parent
                  name: "drag"
                  width: 14
                  height: 14
                }
                MouseArea {
                  anchors.fill: parent
                  cursorShape: Qt.SizeAllCursor
                  drag.target: dragProxy
                  onPressed: {
                    const point = mapToItem(dragProxy.parent, mouseX, mouseY);
                    dragProxy.x = point.x;
                    dragProxy.y = point.y;
                    root.draggingModule = entry.modelData;
                  }
                  onReleased: {
                    dragProxy.Drag.drop();
                    root.draggingModule = "";
                  }
                  onCanceled: root.draggingModule = ""
                }
              }
              Label {
                text: ModuleCatalog.labels[entry.modelData]
                Layout.fillWidth: true
                font.pixelSize: Theme.fontPx(12)
              }
              ActionButton {
                icon: "up"
                hint: "Mover antes"
                enabled: ModuleCatalog.selected.indexOf(entry.modelData) > 0
                onClicked: ModuleCatalog.move(ModuleCatalog.selected.indexOf(entry.modelData), -1)
              }
              ActionButton {
                icon: "down"
                hint: "Mover después"
                enabled: ModuleCatalog.selected.indexOf(entry.modelData) < ModuleCatalog.selected.length - 1
                onClicked: ModuleCatalog.move(ModuleCatalog.selected.indexOf(entry.modelData), 1)
              }
              ActionButton {
                text: "Quitar"
                onClicked: ModuleCatalog.remove(entry.modelData)
              }
            }
            RowLayout {
              Label {
                text: "Zona"
                color: Theme.muted
                font.pixelSize: Theme.fontPx(10)
              }
              Repeater {
                model: ["start", "center", "end"]
                ActionButton {
                  required property string modelData
                  text: ({
                      start: "Inicio",
                      center: "Centro",
                      end: "Final"
                    })[modelData]
                  selected: modelData === zoneEntry.modelData
                  onClicked: ModuleCatalog.place(entry.modelData, modelData)
                }
              }
            }
            SettingSlider {
              title: "Opacidad · " + ModuleCatalog.labels[entry.modelData]
              to: 1
              step: 0.01
              value: Theme.opacityFor(entry.modelData, BarEditor.settings)
              displayValue: Math.round(value * 100) + "%"
              onEdited: value => BarEditor.set("moduleOpacities", Object.assign({}, BarEditor.settings.moduleOpacities || {}, {
                  [entry.modelData]: value
                }))
            }
            DropArea {
              Layout.fillWidth: true
              Layout.preferredHeight: containsDrag ? 12 : 6
              keys: ["hyprlarp-module"]
              onDropped: drop => {
                ModuleCatalog.place(root.draggingModule, zoneEntry.modelData, entry.modelData);
                drop.accept();
              }
              Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                color: parent.containsDrag ? Theme.border : Theme.separator
                height: 1
              }
            }
          }
        }
        DropArea {
          Layout.fillWidth: true
          Layout.preferredHeight: 26
          keys: ["hyprlarp-module"]
          onDropped: drop => {
            ModuleCatalog.place(root.draggingModule, zoneEntry.modelData);
            drop.accept();
          }
          Label {
            anchors.fill: parent
            text: parent.containsDrag ? "Soltar aquí" : ModuleCatalog.zones[zoneEntry.modelData].length === 0 ? "Zona vacía · suelta un módulo aquí" : "Soltar al final"
            color: parent.containsDrag ? Theme.text : Theme.muted
            font.pixelSize: Theme.fontPx(10)
          }
        }
      }
    }
  }
  ColumnLayout {
    Layout.fillWidth: true
    spacing: 12
    visible: root.mode === "add"
    SectionTitle {
      text: "Añadir módulos"
    }
    Field {
      id: moduleSearch
      Layout.fillWidth: true
      placeholderText: "Buscar una función para añadir…"
    }
    Flow {
      Layout.fillWidth: true
      spacing: 4
      Repeater {
        model: [""].concat(ModuleCatalog.groups)
        ActionButton {
          required property string modelData
          text: modelData || "Todas"
          selected: root.category === modelData
          onClicked: root.category = modelData
        }
      }
    }
    Repeater {
      model: root.mode === "add" ? ModuleCatalog.search(moduleSearch.text, root.category) : []
      RowLayout {
        id: availableEntry
        required property string modelData
        Layout.fillWidth: true
        spacing: 10
        Icon {
          name: ModuleCatalog.byId[availableEntry.modelData].icon
          width: 16
          height: 16
          color: Theme.muted
        }
        ColumnLayout {
          Layout.fillWidth: true
          spacing: 2
          Label {
            text: ModuleCatalog.labels[availableEntry.modelData]
            font.pixelSize: Theme.fontPx(12)
            Layout.fillWidth: true
          }
          Label {
            text: ModuleCatalog.byId[availableEntry.modelData].description
            font.pixelSize: Theme.fontPx(10)
            color: Theme.muted
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
          }
        }
        ActionButton {
          text: "Añadir"
          onClicked: ModuleCatalog.add(availableEntry.modelData)
        }
      }
    }
    Label {
      visible: ModuleCatalog.search(moduleSearch.text, root.category).length === 0
      text: "No hay módulos disponibles con ese filtro."
      color: Theme.muted
      font.pixelSize: Theme.fontPx(11)
    }
  }
  ColumnLayout {
    Layout.fillWidth: true
    spacing: 12
    visible: root.mode === "appearance"
    Rule {}
    SectionTitle {
      text: "Aspecto de los módulos"
    }
    SettingSlider {
      title: "Opacidad general"
      to: 1
      step: 0.01
      value: BarEditor.settings.moduleOpacity
      displayValue: Math.round(value * 100) + "%"
      onEdited: value => BarEditor.set("moduleOpacity", value)
    }
    SettingSlider {
      title: "Opacidad del fondo"
      to: 1
      step: 0.01
      value: BarEditor.settings.moduleBackgroundOpacity
      displayValue: Math.round(value * 100) + "%"
      onEdited: value => BarEditor.set("moduleBackgroundOpacity", value)
    }
    SettingSlider {
      title: "Borde"
      to: 4
      value: BarEditor.settings.moduleBorderWidth
      onEdited: value => BarEditor.set("moduleBorderWidth", value)
    }
    SettingSlider {
      title: "Radio"
      to: 8
      value: BarEditor.settings.moduleRadius
      onEdited: value => BarEditor.set("moduleRadius", value)
    }
    SettingSlider {
      title: "Padding horizontal del módulo"
      to: 16
      value: BarEditor.settings.modulePaddingX
      onEdited: value => BarEditor.set("modulePaddingX", value)
    }
    SettingSlider {
      title: "Padding vertical del módulo"
      to: 16
      value: BarEditor.settings.modulePaddingY
      onEdited: value => BarEditor.set("modulePaddingY", value)
    }
    Loader {
      active: root.mode === "appearance" && ModuleCatalog.selected.includes("tray")
      Layout.fillWidth: true
      source: Qt.resolvedUrl("../../components/TraySettings.qml")
    }
  }
}
