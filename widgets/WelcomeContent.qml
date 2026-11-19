import QtQuick
import QtQuick.Window
import QtQuick.Controls as QQC
import QtQuick.Layouts
import "../core"
import "../components"
import "../core/accessibility.js" as Accessibility
import "../core/focus.js" as Focus

Rectangle {
  id: root
  objectName: "welcome-content"
  color: Theme.surface
  border.width: 1
  border.color: Theme.border
  radius: Theme.radiusFor("panel")
  focus: true
  property int step: 0
  property var draft: ({})
  property bool submitting: false
  property string waitingAction: ""
  property string error: ""
  readonly property bool canSubmit: Bridge.ready && Bridge.connected && !Bridge.awaitingInitial && !Bridge.saving && !Bridge.hasPendingSettings && !Bridge.onboarding.readOnly && !submitting
  readonly property var titles: ["Bienvenido a HyprLarp", "Tu escritorio", "A tu medida", "Revisar y empezar"]
  readonly property var labels: ({
      theme: "Tema",
      accent: "Acento del tema",
      themeScheduleEnabled: "Tema según horario",
      panelLayout: "Diseño del panel",
      panelStyle: "Estilo del panel",
      barPosition: "Posición de la barra",
      performanceMode: "Actividad del shell",
      accessibilityTextScale: "Escala del texto",
      accessibilityHighContrast: "Contraste alto",
      accessibilityReducedMotion: "Movimiento reducido",
      accessibilityLargeTargets: "Controles grandes"
    })
  readonly property var changed: Object.keys(updates())
  readonly property string previewTheme: Object.prototype.hasOwnProperty.call(draft, "theme") ? draft.theme : Theme.scheduledTheme
  readonly property var previewPalette: Accessibility.palette(Theme.palettes[previewTheme] || Theme.fallback, !!value("accessibilityHighContrast"))
  readonly property bool previewThemeSelected: Object.prototype.hasOwnProperty.call(draft, "theme")
  readonly property string previewAccentSource: previewThemeSelected || value("accessibilityHighContrast") || previewTheme === "custom" || (value("themeScheduleEnabled") && previewTheme !== Bridge.settings.theme) ? previewPalette.accent : Bridge.settings.accent || previewPalette.accent
  readonly property string previewAccent: Accessibility.ensureContrast(previewAccentSource, [previewPalette.surface, previewPalette.raised, previewPalette.moduleSurface || previewPalette.raised], value("accessibilityHighContrast") ? 7 : 4.5)
  readonly property color previewSurface: previewPalette.surface
  readonly property real previewPanelOpacity: value("accessibilityHighContrast") ? 1 : value("panelStyle") === "glass" ? Math.min(Bridge.settings.panelOpacity ?? 1, .86) : Bridge.settings.panelOpacity ?? 1
  signal finished
  signal closeRequested

  function value(key) {
    return Object.prototype.hasOwnProperty.call(draft, key) ? draft[key] : Bridge.settings[key];
  }
  function revealFocus(item) {
    if (!item || !Focus.contains(pageContent, item))
      return;
    const y = item.mapToItem(pageContent, 0, 0).y;
    const top = scroll.contentItem.contentY;
    const height = scroll.availableHeight;
    if (y < top || y + item.height > top + height) {
      const target = y < top ? y - 12 : y + item.height - height + 12;
      scroll.contentItem.contentY = Math.max(0, Math.min(target, Math.max(0, scroll.contentItem.contentHeight - height)));
    }
  }
  function edit(key, selected) {
    if (submitting)
      return;
    const next = Object.assign({}, draft, {
      [key]: selected
    });
    // Choosing a theme is an explicit switch to manual selection. Merely
    // opening or completing the assistant keeps an existing schedule intact.
    if (key === "theme") {
      next.themeScheduleEnabled = false;
      next.accent = (Theme.palettes[selected] || Theme.fallback).accent;
    }
    draft = next;
    error = "";
  }
  function updates() {
    const result = {};
    for (const key of Object.keys(draft))
      if (JSON.stringify(draft[key]) !== JSON.stringify(Bridge.settings[key]))
        result[key] = draft[key];
    return result;
  }
  function describe(key, selected) {
    if (typeof selected === "boolean")
      return selected ? "Activado" : "Desactivado";
    if (key === "accessibilityTextScale")
      return Math.round(Number(selected) * 100) + "%";
    if (key === "theme")
      return (Theme.palettes[selected] || {}).name || selected;
    return ({
        floating: "Flotante",
        centered: "Centrado",
        sidebar: "Lateral",
        standard: "Estándar",
        glass: "Vidrio",
        flat: "Plano",
        top: "Arriba",
        bottom: "Abajo",
        left: "Izquierda",
        right: "Derecha",
        efficient: "Eficiente",
        balanced: "Equilibrado",
        responsive: "Ágil"
      })[selected] || String(selected);
  }
  function advance() {
    if (submitting || step >= 3)
      return;
    step++;
    scroll.contentItem.contentY = 0;
  }
  function submit() {
    if (!canSubmit || step !== 3)
      return;
    waitingAction = "onboarding-complete";
    submitting = true;
    error = "";
    Bridge.perform(waitingAction, {
      updates: updates()
    });
  }
  function skip() {
    if (!canSubmit)
      return;
    waitingAction = "onboarding-skip";
    submitting = true;
    error = "";
    Bridge.perform(waitingAction);
  }
  Accessible.role: Accessible.Pane
  Accessible.name: "Asistente de primera ejecución de HyprLarp"
  Keys.onEscapePressed: if (!submitting)
    closeRequested()
  Keys.onReturnPressed: {
    if (step < 3)
      advance();
    else
      submit();
  }
  Connections {
    target: root.Window.window
    function onActiveFocusItemChanged() {
      focusReveal.restart();
    }
  }
  Timer {
    id: focusReveal
    interval: 16
    onTriggered: root.revealFocus(root.Window.window ? root.Window.window.activeFocusItem : null)
  }
  Connections {
    target: Bridge
    function onActionFinished(action) {
      if (!root.waitingAction || action !== root.waitingAction)
        return;
      root.waitingAction = "";
      root.submitting = false;
      root.finished();
    }
    function onActionFailed(action, reason) {
      if (action !== root.waitingAction)
        return;
      root.waitingAction = "";
      root.submitting = false;
      root.error = reason;
    }
    function onConnectedChanged() {
      if (!Bridge.connected && root.submitting) {
        root.waitingAction = "";
        root.submitting = false;
        root.error = "Se perdió la conexión. Tu selección sigue aquí; puedes reintentar al reconectar.";
      }
    }
  }

  ColumnLayout {
    anchors.fill: parent
    anchors.margins: 22
    spacing: 16
    RowLayout {
      Layout.fillWidth: true
      Image {
        source: Qt.resolvedUrl("../assets/hyprlarp.svg")
        Layout.preferredWidth: 42
        Layout.preferredHeight: 42
        sourceSize: Qt.size(84, 84)
        fillMode: Image.PreserveAspectFit
        Accessible.ignored: true
      }
      ColumnLayout {
        spacing: 2
        Layout.fillWidth: true
        Label {
          text: "HyprLarp" + (Bridge.releaseVersion ? " · " + Bridge.releaseVersion : "")
          font.pixelSize: Theme.fontPx(16)
          font.weight: Font.DemiBold
          Layout.fillWidth: true
          wrapMode: Text.WordWrap
        }
        Label {
          text: "Primeros pasos · " + (root.step + 1) + " de 4"
          color: Theme.muted
          Layout.fillWidth: true
          wrapMode: Text.WordWrap
        }
      }
      ActionButton {
        objectName: "welcome-close"
        icon: "close"
        hint: "Cerrar sin aplicar · Escape"
        enabled: !root.submitting
        onClicked: root.closeRequested()
      }
    }
    RowLayout {
      spacing: 5
      Layout.fillWidth: true
      Repeater {
        model: 4
        Rectangle {
          required property int index
          Layout.fillWidth: true
          height: 2
          color: index <= root.step ? Theme.accent : Theme.separator
        }
      }
    }
    QQC.ScrollView {
      id: scroll
      objectName: "welcome-scroll"
      Layout.fillWidth: true
      Layout.fillHeight: true
      clip: true
      contentWidth: availableWidth
      QQC.ScrollBar.horizontal.policy: QQC.ScrollBar.AlwaysOff
      QQC.ScrollBar.vertical: SlimScrollBar {}
      ColumnLayout {
        id: pageContent
        objectName: "welcome-pages"
        onImplicitHeightChanged: focusReveal.restart()
        onWidthChanged: focusReveal.restart()
        width: scroll.availableWidth
        spacing: 16
        SectionTitle {
          text: root.titles[root.step]
          font.pixelSize: Theme.fontPx(16)
          Layout.fillWidth: true
          wrapMode: Text.WordWrap
        }
        ColumnLayout {
          visible: root.step === 0
          Layout.fillWidth: true
          spacing: 18
          Label {
            text: "Prepara un escritorio cómodo en unos pocos pasos. Elige su aspecto, ajusta la legibilidad y revisa tu selección antes de guardarla."
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            font.pixelSize: Theme.fontPx(14)
          }
          Label {
            text: "Partimos de tus ajustes actuales. Solo se guardan las opciones que cambies aquí, al pulsar Aplicar y terminar."
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            color: Theme.muted
          }
          Rule {}
          Label {
            text: "Puedes recorrer el asistente con Tab y los botones inferiores. Cierra con Escape para continuar más tarde, u omítelo para conservar tu escritorio."
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            color: Theme.muted
          }
          Label {
            text: "Encontrarás este asistente en Configuración → General cuando quieras volver."
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            color: Theme.muted
          }
        }
        ColumnLayout {
          visible: root.step === 1
          Layout.fillWidth: true
          spacing: 16
          SettingChoice {
            objectName: "welcome-theme"
            title: "Tema"
            choices: Object.keys(Theme.palettes)
            labels: choices.map(name => Theme.palettes[name].name)
            value: root.value("theme") || "amoled"
            enabled: !root.submitting
            onEdited: value => root.edit("theme", value)
          }
          Label {
            visible: !!Bridge.settings.themeScheduleEnabled
            text: Object.prototype.hasOwnProperty.call(root.draft, "theme") ? "Al aplicar, el tema elegido sustituirá al horario automático." : "Tu horario de temas se conserva mientras no elijas otro tema."
            color: Theme.muted
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
          }
          SettingChoice {
            title: "Diseño del panel"
            choices: ["floating", "centered", "sidebar"]
            labels: ["Flotante", "Centrado", "Lateral"]
            value: root.value("panelLayout") || "floating"
            enabled: !root.submitting
            onEdited: value => root.edit("panelLayout", value)
          }
          SettingChoice {
            title: "Estilo del panel"
            choices: ["standard", "glass", "flat"]
            labels: ["Estándar", "Vidrio", "Plano"]
            value: root.value("panelStyle") || "standard"
            enabled: !root.submitting
            onEdited: value => root.edit("panelStyle", value)
          }
          SettingChoice {
            title: "Posición de la barra"
            choices: ["top", "bottom", "left", "right"]
            labels: ["Arriba", "Abajo", "Izquierda", "Derecha"]
            value: root.value("barPosition") || "top"
            enabled: !root.submitting
            onEdited: value => root.edit("barPosition", value)
          }
          Rectangle {
            id: mini
            objectName: "welcome-preview"
            readonly property string position: root.value("barPosition") || "top"
            readonly property bool vertical: position === "left" || position === "right"
            readonly property string layoutMode: root.value("panelLayout") || "floating"
            Layout.fillWidth: true
            implicitHeight: Math.max(180, width * 0.44)
            color: root.previewPalette.background
            border.width: 1
            border.color: root.previewPalette.border
            radius: 5
            clip: true
            Accessible.role: Accessible.Pane
            Accessible.name: "Vista previa del tema, barra y panel elegidos"
            Rectangle {
              x: mini.position === "right" ? mini.width - 27 : 8
              y: mini.position === "bottom" ? mini.height - 27 : 8
              width: mini.vertical ? 19 : mini.width - 16
              height: mini.vertical ? mini.height - 16 : 19
              color: root.previewPalette.surface
              border.width: 1
              border.color: root.previewPalette.border
              Rectangle {
                anchors.centerIn: parent
                width: mini.vertical ? 5 : parent.width * 0.25
                height: mini.vertical ? parent.height * 0.25 : 3
                color: root.previewAccent
              }
            }
            Rectangle {
              readonly property bool sidebar: mini.layoutMode === "sidebar"
              readonly property bool centered: mini.layoutMode === "centered"
              readonly property bool startEdge: mini.position === "left"
              x: centered ? (mini.width - width) / 2 : startEdge ? 35 : mini.width - width - (mini.position === "right" ? 35 : 12)
              y: sidebar ? mini.position === "top" ? 35 : 12 : centered ? (mini.height - height) / 2 : mini.position === "bottom" ? mini.height - height - 35 : 35
              width: Math.min(mini.width * 0.48, 240)
              height: sidebar ? mini.height - (mini.vertical ? 24 : 47) : mini.height * 0.60
              color: Qt.rgba(root.previewSurface.r, root.previewSurface.g, root.previewSurface.b, root.previewPanelOpacity)
              border.width: root.value("panelStyle") === "flat" ? 0 : 1
              border.color: root.previewPalette.border
              radius: sidebar || root.value("panelStyle") === "flat" ? 0 : 5
              Column {
                anchors.fill: parent
                anchors.margins: 12
                spacing: 9
                Rectangle {
                  width: parent.width * .65
                  height: 4
                  color: root.previewPalette.text
                }
                Rectangle {
                  width: parent.width
                  height: 1
                  color: root.previewPalette.separator
                }
                Rectangle {
                  width: parent.width * .8
                  height: 3
                  color: root.previewPalette.muted
                }
                Rectangle {
                  width: parent.width * .55
                  height: 5
                  color: root.previewAccent
                }
              }
            }
          }
          Label {
            text: "Vista orientativa · el fondo, el desenfoque y las barras específicas de cada monitor se ajustan desde Configuración."
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            color: Theme.muted
          }
        }
        ColumnLayout {
          visible: root.step === 2
          Layout.fillWidth: true
          spacing: 18
          SettingChoice {
            title: "Actividad del shell"
            choices: ["efficient", "balanced", "responsive"]
            labels: ["Eficiente", "Equilibrado", "Ágil"]
            value: root.value("performanceMode") || "balanced"
            enabled: !root.submitting
            onEdited: value => root.edit("performanceMode", value)
          }
          Label {
            text: "Equilibrado ofrece un buen punto de partida. Eficiente reduce sondeos y efectos; Ágil actualiza los indicadores con mayor frecuencia."
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            color: Theme.muted
          }
          SettingSlider {
            title: "Escala del texto"
            settingsControl: false
            from: 1
            to: 2
            step: 0.05
            suffix: ""
            displayValue: Math.round(value * 100) + "%"
            value: root.value("accessibilityTextScale") || 1
            enabled: !root.submitting
            onEdited: value => root.edit("accessibilityTextScale", Math.round(value * 100) / 100)
          }
          Rectangle {
            Layout.fillWidth: true
            implicitHeight: sample.implicitHeight + 24
            color: root.previewPalette.raised
            radius: Theme.radiusFor("field")
            Label {
              id: sample
              anchors.fill: parent
              anchors.margins: 12
              text: "Así se verá el texto en tu escritorio."
              color: root.previewPalette.text
              font.pixelSize: Math.round(Math.max(12, Number(Bridge.settings.accessibilityMinimumFontSize || 12)) * Number(root.value("accessibilityTextScale") || 1))
              wrapMode: Text.WordWrap
            }
          }
          SettingToggle {
            title: "Contraste alto"
            checked: !!root.value("accessibilityHighContrast")
            enabled: !root.submitting
            onEdited: checked => root.edit("accessibilityHighContrast", checked)
          }
          SettingToggle {
            title: "Reducir movimiento"
            checked: !!root.value("accessibilityReducedMotion")
            enabled: !root.submitting
            onEdited: checked => root.edit("accessibilityReducedMotion", checked)
          }
          SettingToggle {
            objectName: "welcome-large-targets"
            title: "Controles más grandes"
            checked: !!root.value("accessibilityLargeTargets")
            enabled: !root.submitting
            onEdited: checked => root.edit("accessibilityLargeTargets", checked)
          }
        }
        ColumnLayout {
          visible: root.step === 3
          Layout.fillWidth: true
          spacing: 14
          Label {
            text: root.changed.length ? "Se guardarán estos cambios:" : "Tus ajustes actuales se conservan. Puedes terminar para completar los primeros pasos."
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
          }
          Repeater {
            model: root.changed
            ColumnLayout {
              required property string modelData
              Layout.fillWidth: true
              spacing: 3
              Label {
                text: root.labels[modelData] || modelData
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                font.weight: Font.DemiBold
              }
              Label {
                text: root.describe(modelData, Bridge.settings[modelData]) + " → " + root.describe(modelData, root.draft[modelData])
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                color: Theme.muted
              }
            }
          }
          Rule {}
          SectionTitle {
            text: "Tus atajos configurados"
          }
          Repeater {
            model: [
              {
                key: "launcher",
                title: "Aplicaciones"
              },
              {
                key: "settings",
                title: "Configuración"
              },
              {
                key: "lock",
                title: "Bloqueo"
              },
              {
                key: "screenshot-region",
                title: "Captura dinámica"
              },
              {
                key: "screenshot-region-frozen",
                title: "Captura estática"
              }
            ]
            Label {
              required property var modelData
              text: modelData.title + " · " + ((Bridge.settings.shortcuts || {})[modelData.key] || "Sin asignar")
              Layout.fillWidth: true
              wrapMode: Text.WordWrap
            }
          }
          Label {
            text: "Puedes revisar y aplicar los atajos en Configuración → Atajos. El asistente guarda la apariencia y la comodidad seleccionadas; la integración con Hyprland y el inicio de sesión se gestionan desde sus apartados."
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            color: Theme.muted
          }
        }
      }
    }
    StatusMessage {
      visible: !!root.error || !!Bridge.onboarding.error || !Bridge.connected
      error: !!root.error || !!Bridge.onboarding.error
      text: root.error || Bridge.onboarding.error || "Esperando al servicio de HyprLarp…"
    }
    Rule {}
    Flow {
      Layout.fillWidth: true
      spacing: 8
      ActionButton {
        objectName: "welcome-skip"
        text: root.waitingAction === "onboarding-skip" ? "Omitiendo…" : "Omitir asistente"
        enabled: root.canSubmit
        onClicked: root.skip()
      }
      ActionButton {
        objectName: "welcome-back"
        text: "Atrás"
        visible: root.step > 0
        enabled: !root.submitting
        onClicked: {
          root.step--;
          scroll.contentItem.contentY = 0;
        }
      }
      ActionButton {
        id: nextButton
        objectName: "welcome-next"
        text: root.step === 3 ? root.submitting ? "Guardando…" : "Aplicar y terminar" : "Siguiente"
        accent: true
        enabled: root.step < 3 ? !root.submitting : root.canSubmit
        onClicked: root.step < 3 ? root.advance() : root.submit()
      }
    }
  }
}
