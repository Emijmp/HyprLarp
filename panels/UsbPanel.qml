import QtQuick
import QtQuick.Layouts
import "../core"
import "../components"
import "../core/formats.js" as Format

ColumnLayout {
  id: root
  property string confirmEject: ""
  spacing: 12
  SectionTitle {
    text: "Dispositivos conectados"
  }
  Repeater {
    model: Bridge.usb.devices || []
    ColumnLayout {
      id: peripheral
      required property var modelData
      Layout.fillWidth: true
      spacing: 3
      Label {
        text: peripheral.modelData.name
        font.pixelSize: 12
        Layout.fillWidth: true
        wrapMode: Text.WordWrap
      }
      Label {
        text: [peripheral.modelData.manufacturer, peripheral.modelData.vendor + ":" + peripheral.modelData.product, peripheral.modelData.speed ? peripheral.modelData.speed + " Mb/s" : ""].filter(Boolean).join(" · ")
        color: Theme.muted
        font.pixelSize: 10
        Layout.fillWidth: true
        wrapMode: Text.WordWrap
      }
    }
  }
  Label {
    visible: (Bridge.usb.devices || []).length === 0
    text: Bridge.preview ? "Los dispositivos se consultan en la sesión real." : "Sin dispositivos USB detectados."
    color: Theme.muted
    font.pixelSize: 11
    Layout.fillWidth: true
    wrapMode: Text.WordWrap
  }
  Rule {}
  RowLayout {
    Label {
      text: "Almacenamiento USB"
      Layout.fillWidth: true
      color: Theme.muted
      font.pixelSize: 11
    }
    ActionButton {
      text: "Actualizar"
      enabled: !Bridge.isBusy("system-refresh")
      onClicked: Bridge.perform("system-refresh", {
        name: "usb"
      })
    }
  }
  Label {
    visible: Bridge.isBusyGroup("usb-")
    text: "Operación en curso…"
    color: Theme.muted
    font.pixelSize: 11
  }
  Repeater {
    model: Bridge.usb.drives || []
    ColumnLayout {
      id: drive
      required property var modelData
      Layout.fillWidth: true
      spacing: 10
      SectionTitle {
        text: drive.modelData.name
      }
      ValueRow {
        title: "Capacidad"
        value: Format.bytes(drive.modelData.size)
      }
      Label {
        visible: !!drive.modelData.protected
        text: "Unidad del sistema: acciones deshabilitadas."
        color: Theme.muted
        font.pixelSize: 11
        Layout.fillWidth: true
        wrapMode: Text.WordWrap
      }
      Repeater {
        model: drive.modelData.volumes
        ColumnLayout {
          id: volume
          required property var modelData
          Layout.fillWidth: true
          spacing: 5
          Label {
            text: volume.modelData.name
            Layout.fillWidth: true
            font.pixelSize: 12
          }
          Label {
            text: (volume.modelData.filesystem || "Sin sistema de archivos") + " · " + Format.bytes(volume.modelData.size) + (volume.modelData.readOnly ? " · Solo lectura" : "")
            color: Theme.muted
            font.pixelSize: 10
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
          }
          Label {
            visible: volume.modelData.mounted
            text: volume.modelData.mounts.join("\n")
            color: Theme.muted
            Layout.fillWidth: true
            wrapMode: Text.WrapAnywhere
            font.pixelSize: 10
          }
          ValueRow {
            visible: volume.modelData.free !== null
            title: "Libre"
            value: Format.bytes(volume.modelData.free)
          }
          RowLayout {
            enabled: !Bridge.preview && !Bridge.settingsOnly && !volume.modelData.protected && !Bridge.isBusyGroup("usb-")
            ActionButton {
              text: volume.modelData.mounted ? "Desmontar" : "Montar"
              enabled: volume.modelData.mountable
              onClicked: Bridge.perform(volume.modelData.mounted ? "usb-unmount" : "usb-mount", {
                id: volume.modelData.id
              })
            }
            ActionButton {
              text: "Abrir"
              enabled: volume.modelData.mounted
              onClicked: Bridge.perform("usb-open", {
                id: volume.modelData.id
              })
            }
          }
        }
      }
      RowLayout {
        enabled: drive.modelData.canEject && !Bridge.preview && !Bridge.settingsOnly && !Bridge.isBusyGroup("usb-")
        ActionButton {
          text: root.confirmEject === drive.modelData.id ? "Confirmar expulsión" : "Expulsar unidad"
          onClicked: {
            if (root.confirmEject === drive.modelData.id) {
              Bridge.perform("usb-eject", {
                id: drive.modelData.id
              });
              root.confirmEject = "";
            } else
              root.confirmEject = drive.modelData.id;
          }
        }
        ActionButton {
          visible: root.confirmEject === drive.modelData.id
          text: "Cancelar"
          onClicked: root.confirmEject = ""
        }
      }
      Rule {}
    }
  }
  EmptyState {
    visible: (Bridge.usb.drives || []).length === 0
    title: Bridge.usb.available ? "Sin unidades USB" : "Servicio USB no disponible"
    description: Bridge.usb.error || (Bridge.usb.available ? "Conecta una unidad de almacenamiento." : "Requiere UDisks y python-gobject.")
  }
}
