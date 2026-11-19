import QtQuick
import QtQuick.Layouts
import "../core"

ColumnLayout {
  id: root
  spacing: 10
  readonly property var applications: Array.from(new Set(Object.keys(Bridge.settings.notificationRules || {}).concat(Notices.history.map(item => item.appId || item.app)))).filter(Boolean).sort()
  function rule(app, key, value) {
    const rules = Object.assign({}, Bridge.settings.notificationRules || {});
    rules[app] = Object.assign({}, rules[app] || {}, {
      [key]: value
    });
    Bridge.configure("notificationRules", rules);
  }
  SectionTitle {
    text: "Notificaciones · reglas por aplicación"
  }
  Label {
    text: "Por defecto se guardan y muestran avisos; el sonido está desactivado. No molestar silencia sonidos y Presentación suprime todos los avisos."
    color: Theme.muted
    wrapMode: Text.WordWrap
    Layout.fillWidth: true
    font.pixelSize: Theme.fontPx(11)
  }
  RowLayout {
    Field {
      id: application
      placeholderText: "ID de escritorio o nombre de aplicación"
      maximumLength: 256
      Layout.fillWidth: true
    }
    ActionButton {
      text: "Añadir regla"
      enabled: application.text.trim().length > 0
      onClicked: {
        root.rule(application.text.trim(), "popup", true);
        application.text = "";
      }
    }
  }
  Repeater {
    model: root.applications
    ColumnLayout {
      id: entry
      required property string modelData
      readonly property var rule: (Bridge.settings.notificationRules || {})[modelData] || {}
      Layout.fillWidth: true
      RowLayout {
        Label {
          text: entry.modelData
          font.pixelSize: Theme.fontPx(12)
          Layout.fillWidth: true
          elide: Text.ElideRight
        }
        ActionButton {
          text: "Heredar"
          enabled: !!(Bridge.settings.notificationRules || {})[entry.modelData]
          onClicked: {
            const rules = Object.assign({}, Bridge.settings.notificationRules);
            delete rules[entry.modelData];
            Bridge.configure("notificationRules", rules);
          }
        }
      }
      RowLayout {
        SettingToggle {
          title: "Avisos"
          checked: entry.rule.popup !== false
          onEdited: checked => root.rule(entry.modelData, "popup", checked)
        }
        SettingToggle {
          title: "Sonido"
          checked: entry.rule.sound === true
          onEdited: checked => root.rule(entry.modelData, "sound", checked)
        }
        SettingToggle {
          title: "Historial"
          checked: entry.rule.history !== false
          onEdited: checked => root.rule(entry.modelData, "history", checked)
        }
      }
      Rule {}
    }
  }
}
