import QtQuick
import QtQuick.Layouts
import "../core"
import "../core/displays.js" as Displays
import "." as Controls

ColumnLayout {
  id: root
  property bool compact: false
  readonly property var outputs: Bridge.displays.outputs || []
  property string primaryName: ""
  property string secondaryName: ""
  readonly property var primary: outputs.find(output => output.name === primaryName) || outputs.find(output => output.internal) || outputs[0] || null
  readonly property var others: outputs.filter(output => !primary || output.name !== primary.name)
  readonly property var secondary: others.find(output => output.name === secondaryName) || others[0] || null
  readonly property string activeMode: {
    const enabled = outputs.filter(output => output.enabled);
    if (enabled.length === 1)
      return primary && enabled[0].name === primary.name ? "internal-only" : "external-only";
    return Displays.projection(outputs);
  }
  readonly property var options: [
    {
      mode: "internal-only",
      title: "Solo pantalla del equipo",
      detail: "Usar únicamente la pantalla principal",
      icon: "monitor"
    },
    {
      mode: "duplicate",
      title: "Duplicar",
      detail: "Mostrar la misma imagen en las otras pantallas",
      icon: "copy"
    },
    {
      mode: "extend",
      title: "Extender",
      detail: "Ampliar el escritorio entre las pantallas",
      icon: "layout"
    },
    {
      mode: "external-only",
      title: "Solo pantalla externa",
      detail: "Usar únicamente la pantalla secundaria",
      icon: "monitor"
    }
  ]
  Layout.fillWidth: true
  spacing: 10
  function project(mode) {
    Bridge.perform("displays-preset", {
      mode: mode,
      primary: primary ? primary.name : "",
      secondary: secondary ? secondary.name : ""
    });
  }
  GridLayout {
    columns: root.compact && root.width > 650 ? 4 : 2
    columnSpacing: 8
    rowSpacing: 8
    Layout.fillWidth: true
    Repeater {
      model: root.options
      Rectangle {
        id: option
        required property var modelData
        objectName: "projection-" + modelData.mode
        Layout.fillWidth: true
        Layout.minimumWidth: 0
        implicitHeight: root.compact ? 82 : 96
        color: click.containsMouse || activeFocus ? Theme.raised : Theme.surface
        radius: Theme.radiusFor("button")
        border.width: 1
        border.color: root.activeMode === modelData.mode ? Theme.accent : Theme.separator
        enabled: !Bridge.preview && Bridge.displays.available && !Bridge.displays.pending && !Bridge.isBusy("displays-preset") && (modelData.mode === "internal-only" ? root.outputs.length > 0 : root.outputs.length > 1)
        opacity: enabled ? 1 : .4
        activeFocusOnTab: enabled
        Keys.onReturnPressed: root.project(modelData.mode)
        Keys.onSpacePressed: root.project(modelData.mode)
        ColumnLayout {
          anchors.fill: parent
          anchors.margins: 10
          spacing: 4
          RowLayout {
            Controls.Icon {
              name: option.modelData.icon
              Layout.preferredWidth: 15
              Layout.preferredHeight: 15
            }
            Controls.Label {
              text: option.modelData.title
              font.pixelSize: Theme.fontPx(11)
              wrapMode: Text.WordWrap
              Layout.fillWidth: true
            }
          }
          Controls.Label {
            text: option.modelData.detail
            color: Theme.muted
            font.pixelSize: Theme.fontPx(10)
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
          }
          Item {
            Layout.fillHeight: true
          }
        }
        MouseArea {
          id: click
          anchors.fill: parent
          hoverEnabled: true
          cursorShape: Qt.PointingHandCursor
          onClicked: {
            option.forceActiveFocus();
            root.project(option.modelData.mode);
          }
        }
        Accessible.role: Accessible.Button
        Accessible.name: modelData.title + ". " + modelData.detail
        Accessible.onPressAction: if (enabled)
          root.project(modelData.mode)
      }
    }
  }
  GridLayout {
    visible: root.outputs.length > 1
    columns: 2
    columnSpacing: 10
    rowSpacing: 8
    Layout.fillWidth: true
    Controls.Label {
      text: "Principal / origen"
      font.pixelSize: Theme.fontPx(11)
    }
    Controls.Selection {
      Layout.fillWidth: true
      choices: root.outputs.map(output => output.name)
      value: root.primary ? root.primary.name : ""
      enabled: !Bridge.displays.pending
      onEdited: value => root.primaryName = value
    }
    Controls.Label {
      text: "Secundaria / proyector"
      font.pixelSize: Theme.fontPx(11)
    }
    Controls.Selection {
      Layout.fillWidth: true
      choices: root.others.map(output => output.name)
      value: root.secondary ? root.secondary.name : ""
      enabled: !Bridge.displays.pending
      onEdited: value => root.secondaryName = value
    }
  }
  Controls.Label {
    visible: root.outputs.length < 2
    text: "Conecta un proyector u otra pantalla para duplicar o extender."
    color: Theme.muted
    font.pixelSize: Theme.fontPx(11)
    wrapMode: Text.WordWrap
    Layout.fillWidth: true
  }
}
