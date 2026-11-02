import QtQuick
import QtQuick.Layouts
import "../core"

ColumnLayout {
  id: root
  property bool configurationEditor: false
  spacing: 12
  function write(key, value) {
    if (configurationEditor)
      Bridge.configure(key, value);
    else
      Bridge.set(key, value);
  }
  SettingChoice {
    title: "Activación"
    choices: ["manual", "schedule"]
    labels: ["Manual", "Por horario"]
    value: Bridge.settings.nightLightSchedule ? "schedule" : "manual"
    onEdited: value => root.write("nightLightSchedule", value === "schedule")
  }
  SettingToggle {
    title: "Filtro nocturno"
    enabled: !Bridge.settings.nightLightSchedule
    checked: NightLight.desired
    onEdited: checked => root.write("nightLightEnabled", checked)
  }
  SettingSlider {
    title: "Temperatura de color"
    settingsControl: root.configurationEditor
    from: 1000
    to: 6500
    step: 100
    suffix: " K"
    value: Bridge.settings.nightLightTemperature || 4000
    onEdited: value => root.write("nightLightTemperature", value)
  }
  RowLayout {
    visible: !!Bridge.settings.nightLightSchedule
    Label {
      text: "Desde"
      font.pixelSize: 11
    }
    Field {
      text: Bridge.settings.nightLightStart || "20:00"
      Layout.preferredWidth: 76
      maximumLength: 5
      onEditingFinished: {
        if (/^(?:[01]\d|2[0-3]):[0-5]\d$/.test(text))
          root.write("nightLightStart", text);
        else
          Bridge.toast("Usa HH:MM, de 00:00 a 23:59", true);
        text = Qt.binding(() => Bridge.settings.nightLightStart);
      }
    }
    Label {
      text: "Hasta"
      font.pixelSize: 11
    }
    Field {
      text: Bridge.settings.nightLightEnd || "07:00"
      Layout.preferredWidth: 76
      maximumLength: 5
      onEditingFinished: {
        if (/^(?:[01]\d|2[0-3]):[0-5]\d$/.test(text))
          root.write("nightLightEnd", text);
        else
          Bridge.toast("Usa HH:MM, de 00:00 a 23:59", true);
        text = Qt.binding(() => Bridge.settings.nightLightEnd);
      }
    }
  }
  Label {
    text: Bridge.preview ? "Vista previa · el filtro de pantalla está desactivado." : Bridge.settingsOnly ? "Inicia el shell para aplicar el filtro." : Bridge.nightLight.error || (Bridge.nightLight.active ? "Filtro activo · " + Bridge.nightLight.temperature + " K" : NightLight.desired ? "Aplicando filtro…" : "Filtro desactivado")
    color: Theme.muted
    Layout.fillWidth: true
    wrapMode: Text.WordWrap
    font.pixelSize: 11
  }
  Label {
    text: "La temperatura baja da un tono más cálido. El horario admite cruzar medianoche; dos horas iguales mantienen el filtro todo el día."
    color: Theme.muted
    font.pixelSize: 10
    wrapMode: Text.WordWrap
    Layout.fillWidth: true
  }
  ActionButton {
    text: "Reintentar filtro"
    visible: !!Bridge.nightLight.error && !Bridge.preview && !Bridge.settingsOnly
    onClicked: Bridge.perform("system-refresh", {
      name: "night-light"
    })
  }
}
