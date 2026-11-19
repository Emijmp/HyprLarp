import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../core"

RowLayout {
  id: root
  required property string title
  required property string value
  signal edited(string color)
  Layout.fillWidth: true
  function openPicker() {
    picker.red = parseInt(root.value.slice(1, 3), 16);
    picker.green = parseInt(root.value.slice(3, 5), 16);
    picker.blue = parseInt(root.value.slice(5, 7), 16);
    picker.open();
  }
  function finishPicker(apply) {
    if (apply)
      root.edited(picker.selected);
    picker.close();
  }
  function hex(red, green, blue) {
    return "#" + [red, green, blue].map(v => Math.round(v).toString(16).padStart(2, "0")).join("");
  }
  Label {
    text: root.title
    font.pixelSize: Theme.fontPx(12)
    Layout.fillWidth: true
    wrapMode: Text.WordWrap
  }
  Rectangle {
    id: swatch
    implicitWidth: Theme.controlHeight(26)
    implicitHeight: Theme.controlHeight(26)
    activeFocusOnTab: true
    Keys.onReturnPressed: root.openPicker()
    Keys.onSpacePressed: root.openPicker()
    Accessible.role: Accessible.Button
    Accessible.name: "Elegir color · " + root.title
    Accessible.onPressAction: root.openPicker()
    FocusRing {
      control: swatch
    }
    color: root.value
    border.width: 1
    border.color: Theme.border
    MouseArea {
      anchors.fill: parent
      cursorShape: Qt.PointingHandCursor
      onClicked: {
        root.openPicker();
      }
    }
  }
  Field {
    Accessible.name: "Color hexadecimal · " + root.title
    text: root.value
    Layout.preferredWidth: Theme.px(120)
    maximumLength: 7
    font.family: Theme.mono
    onEditingFinished: {
      const color = text.trim().toLowerCase();
      if (/^#[0-9a-f]{6}$/.test(color)) {
        if (color !== root.value.toLowerCase())
          root.edited(color);
      } else
        Bridge.toast("Color inválido: usa #RRGGBB", true);
      text = Qt.binding(() => root.value);
    }
  }
  Popup {
    id: picker
    parent: Overlay.overlay
    x: Math.max(8, Math.min(parent.width - width - 8, swatch.mapToItem(parent, 0, 0).x - 260))
    y: Math.max(8, Math.min(parent.height - height - 8, swatch.mapToItem(parent, 0, swatch.height).y + 6))
    width: Math.min(360, parent.width - 16)
    padding: 16
    modal: true
    property int red: 0
    property int green: 0
    property int blue: 0
    readonly property string selected: root.hex(red, green, blue)
    background: Rectangle {
      radius: Theme.radiusFor("panel")
      color: Theme.surface
      border.width: 1
      border.color: Theme.border
    }
    contentItem: ColumnLayout {
      spacing: 10
      SectionTitle {
        text: root.title + " · RGB"
      }
      Rectangle {
        Layout.fillWidth: true
        implicitHeight: 58
        color: picker.selected
        border.width: 1
        border.color: Theme.border
        Label {
          anchors.centerIn: parent
          text: picker.selected.toUpperCase()
          color: (picker.red * 0.299 + picker.green * 0.587 + picker.blue * 0.114) > 145 ? "#000000" : "#ffffff"
          font.family: Theme.mono
        }
      }
      SettingSlider {
        title: "Rojo"
        to: 255
        suffix: ""
        value: picker.red
        onEdited: value => picker.red = value
      }
      SettingSlider {
        title: "Verde"
        to: 255
        suffix: ""
        value: picker.green
        onEdited: value => picker.green = value
      }
      SettingSlider {
        title: "Azul"
        to: 255
        suffix: ""
        value: picker.blue
        onEdited: value => picker.blue = value
      }
      RowLayout {
        ActionButton {
          text: "Cancelar"
          onClicked: picker.close()
        }
        ActionButton {
          text: "Aplicar color"
          accent: true
          onClicked: {
            root.edited(picker.selected);
            picker.close();
          }
        }
      }
    }
  }
}
