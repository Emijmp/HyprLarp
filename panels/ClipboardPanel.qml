import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../core"
import "../components"

ColumnLayout {
  id: root
  property bool confirmClear: false
  property bool pinsOnly: false
  readonly property var filtered: Bridge.clipboard.filter(item => (!pinsOnly || !!item.pin) && item.text.toLowerCase().includes(search.text.toLowerCase()))
  function focusSearch() {
    search.forceActiveFocus();
  }
  function payload(item) {
    return {
      raw: item.raw || "",
      pin: item.pin || "",
      id: item.id
    };
  }
  spacing: 10
  Field {
    id: search
    Layout.fillWidth: true
    placeholderText: "Buscar en el historial"
    Component.onCompleted: forceActiveFocus()
  }
  RowLayout {
    ActionButton {
      text: "Todo"
      selected: !root.pinsOnly
      onClicked: root.pinsOnly = false
    }
    ActionButton {
      text: "Fijados"
      selected: root.pinsOnly
      onClicked: root.pinsOnly = true
    }
    Item {
      Layout.fillWidth: true
    }
    ActionButton {
      text: Bridge.settings.clipboardPaused ? "Reanudar" : "Pausar"
      enabled: !!Bridge.settings.clipboardEnabled
      selected: !!Bridge.settings.clipboardPaused
      onClicked: Bridge.set("clipboardPaused", !Bridge.settings.clipboardPaused)
    }
    ActionButton {
      text: root.confirmClear ? "Confirmar" : "Vaciar"
      hint: "Vaciar historial; los fijados se conservan"
      onClicked: {
        if (root.confirmClear) {
          Bridge.perform("clipboard-clear");
          root.confirmClear = false;
        } else
          root.confirmClear = true;
      }
    }
  }
  Label {
    visible: !!Bridge.settings.clipboardPaused
    text: "Captura pausada · el historial sigue disponible"
    color: Theme.muted
    font.pixelSize: Theme.fontPx(10)
  }
  ListView {
    id: list
    Layout.fillWidth: true
    Layout.preferredHeight: root.filtered.length ? 380 : 0
    clip: true
    model: root.filtered
    cacheBuffer: 0
    reuseItems: true
    spacing: 8
    boundsBehavior: Flickable.StopAtBounds
    ScrollBar.vertical: SlimScrollBar {}
    delegate: Column {
      id: entry
      required property var modelData
      width: list.width - 8
      spacing: 6
      function thumbnail() {
        if (modelData.image && !Bridge.clipboardThumbnails[modelData.id] && !Bridge.preview)
          Bridge.perform("clipboard-thumbnail", root.payload(modelData));
      }
      Component.onCompleted: thumbnail()
      ListView.onReused: thumbnail()
      RowLayout {
        width: parent.width
        Label {
          text: entry.modelData.text
          wrapMode: Text.WrapAnywhere
          maximumLineCount: 2
          Layout.fillWidth: true
          font.pixelSize: Theme.fontPx(12)
        }
        ActionButton {
          icon: "pin"
          selected: !!entry.modelData.pin
          hint: entry.modelData.pin ? "Desfijar" : "Fijar entrada"
          onClicked: Bridge.perform(entry.modelData.pin ? "clipboard-unpin" : "clipboard-pin", root.payload(entry.modelData))
        }
        ActionButton {
          text: "Copiar"
          onClicked: {
            Bridge.perform("clipboard-copy", root.payload(entry.modelData));
            ShellState.close();
          }
        }
        ActionButton {
          icon: "close"
          hint: "Eliminar entrada"
          onClicked: Bridge.perform("clipboard-delete", root.payload(entry.modelData))
        }
      }
      Image {
        visible: !!source
        source: entry.modelData.image ? Bridge.clipboardThumbnails[entry.modelData.id] || "" : ""
        width: 160
        height: visible ? 100 : 0
        sourceSize.width: 192
        sourceSize.height: 128
        fillMode: Image.PreserveAspectFit
        onStatusChanged: if (status === Image.Error) {
          const next = Object.assign({}, Bridge.clipboardThumbnails);
          delete next[entry.modelData.id];
          Bridge.clipboardThumbnails = next;
          // A corrupt cached file may be returned unchanged by the backend.
          // Retry only when this row is loaded/reused again, not from Error.
        }
        asynchronous: true
        cache: false
      }
      Rule {
        width: parent.width
      }
    }
  }
  EmptyState {
    visible: root.filtered.length === 0
    title: Bridge.settings.clipboardEnabled ? "Sin entradas" : "Historial desactivado"
    description: root.pinsOnly ? "Fija entradas para conservarlas al vaciar el historial." : "El shell guarda texto e imágenes copiados mientras está activo y la captura está habilitada."
  }
}
