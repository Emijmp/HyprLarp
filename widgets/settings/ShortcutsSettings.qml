import QtQuick
import QtQuick.Layouts
import "../../core"
import "../../components"

ColumnLayout {
  id: root
  spacing: 12
  property string mode: "shell"
  property var draft: null
  readonly property var custom: Bridge.settings.customBindings || []
  readonly property var labels: ({
      energy: "Perfiles de energía",
      "night-light": "Modo nocturno",
      usb: "Dispositivos USB",
      osd: "Ajustes OSD",
      launcher: "Aplicaciones",
      control: "Centro de control",
      notifications: "Notificaciones",
      clipboard: "Portapapeles",
      media: "Multimedia",
      calendar: "Calendario",
      wallpapers: "Fondos",
      session: "Sesión",
      settings: "Configuración",
      wifi: "Wi-Fi",
      bluetooth: "Bluetooth",
      resources: "Recursos",
      battery: "Batería",
      capture: "Menú de capturas",
      "screenshot-region": "Capturar región",
      "screenshot-screen": "Capturar escritorio",
      lock: "Bloquear",
      audio: "Audio",
      presentation: "Presentación"
    })
  readonly property var actions: Object.keys(Bridge.settings.shortcuts || {})
  readonly property var availableActions: actions.filter(action => !Bridge.settings.shortcuts[action])
  function identifier() {
    return "bind-" + Date.now() + "-" + Math.random().toString(36).slice(2, 8);
  }
  function edit(entry, builtin) {
    draft = Object.assign({
      id: identifier(),
      name: "",
      chord: "",
      type: "command",
      action: "launcher",
      command: "",
      source: "",
      enabled: true,
      repeat: false,
      locked: false,
      release: false,
      replace: false,
      builtin: !!builtin
    }, entry || {});
  }
  function updateDraft(key, value) {
    if (!draft)
      return;
    draft = Object.assign({}, draft, {
      name: nameField.text,
      command: commandField.text,
      chord: chordField.chordText
    }, {
      [key]: value
    });
  }
  function removeBuiltin(action) {
    Bridge.configure("shortcuts", Object.assign({}, Bridge.settings.shortcuts, {
      [action]: ""
    }));
  }
  function removeCustom(id) {
    Bridge.configure("customBindings", custom.filter(item => item.id !== id));
  }
  function toggleCustom(entry) {
    Bridge.configure("customBindings", custom.map(item => item.id === entry.id ? Object.assign({}, item, {
        enabled: !item.enabled
      }) : item));
  }
  function personalize(entry, disabled) {
    const existing = custom.find(item => item.source === entry.source);
    const value = existing || {
      id: identifier(),
      name: entry.command || "Acción de Hyprland",
      chord: entry.chord,
      type: "inherit",
      source: entry.source,
      enabled: true
    };
    if (disabled) {
      const item = Object.assign({
        action: "",
        command: "",
        repeat: false,
        locked: false,
        release: false,
        replace: false
      }, value, {
        enabled: false
      });
      item.name = item.name.slice(0, 80);
      Bridge.configure("customBindings", custom.filter(other => other.source !== entry.source).concat([item]));
    } else
      edit(Object.assign({}, value, {
        name: value.name.slice(0, 80)
      }));
  }
  function refresh() {
    if (!Bridge.preview && Bridge.configurationActive && !Bridge.isBusy("shortcut-list"))
      Bridge.performConfig("shortcut-list");
  }
  function adoptCurrent() {
    const legacy = {
      "panel-toggle launcher": "launcher",
      "panel-toggle control-center": "control",
      "settings-toggle": "settings",
      "panel-toggle session": "session",
      "panel-toggle clipboard": "clipboard",
      "screenshot-region": "screenshot-region",
      "screenshot-screen": "screenshot-screen"
    };
    const imported = {};
    for (const entry of Bridge.shortcutState.bindings || []) {
      const match = entry.command.match(/^\s*noctalia\s+msg\s+(.+?)\s*$/);
      if (match && legacy[match[1]] && !entry.submap)
        imported[legacy[match[1]]] = entry.chord;
    }
    if (!Object.keys(imported).length) {
      Bridge.toast("No se detectaron combinaciones de Noctalia en la lista actual", true);
      return;
    }
    const next = Object.assign({}, Bridge.settings.shortcuts, imported);
    const reserved = Object.values(imported).map(chord => chordField.canonical(chord));
    for (const action of Object.keys(next))
      if (!imported[action] && next[action] && reserved.includes(chordField.canonical(next[action])))
        next[action] = "";
    Bridge.configureMany({
      shortcuts: next,
      migrateNoctaliaBinds: true
    });
    mode = "shell";
  }
  function saveDraft() {
    if (!draft)
      return;
    const chord = chordField.chordText;
    if (!chordField.valid(chord)) {
      Bridge.toast("Formato de combinación: SUPER SHIFT, S", true);
      return;
    }
    const canonical = chordField.canonical(chord);
    const duplicate = actions.some(action => (!draft.builtin || action !== draft.action) && Bridge.settings.shortcuts[action] && chordField.canonical(Bridge.settings.shortcuts[action]) === canonical) || custom.some(item => item.id !== draft.id && item.enabled && chordField.canonical(item.chord) === canonical);
    if (draft.enabled && duplicate) {
      Bridge.toast("Esta combinación ya pertenece a otro bind configurado", true);
      return;
    }
    if (draft.builtin) {
      Bridge.configure("shortcuts", Object.assign({}, Bridge.settings.shortcuts, {
        [draft.action]: chord
      }));
      draft = null;
      return;
    }
    const item = Object.assign({}, draft, {
      name: nameField.text.trim(),
      chord: chord,
      command: draft.type === "command" ? commandField.text.trim() : "",
      action: draft.type === "shell" ? draft.action : ""
    });
    delete item.builtin;
    if (!item.name || (item.type === "command" && !item.command)) {
      Bridge.toast("Escribe un nombre y la acción del bind", true);
      return;
    }
    Bridge.configure("customBindings", custom.filter(other => other.id !== item.id).concat([item]));
    draft = null;
  }
  Component.onCompleted: Qt.callLater(refresh)
  onModeChanged: if (mode === "current")
    refresh()
  SettingChoice {
    title: "Binds"
    choices: ["shell", "custom", "current"]
    labels: ["Shell", "Personalizados", "Actuales en Hyprland"]
    value: root.mode
    onEdited: value => {
      root.mode = value;
      root.draft = null;
    }
  }
  Label {
    Layout.fillWidth: true
    text: "Tus binds actuales tienen prioridad. Los cambios se guardan con Deshacer/Rehacer; pulsa Aplicar para activarlos."
    color: Theme.muted
    font.pixelSize: 11
    wrapMode: Text.WordWrap
  }
  ColumnLayout {
    visible: root.mode === "shell" && !root.draft
    Layout.fillWidth: true
    spacing: 8
    Repeater {
      model: root.mode === "shell" && !root.draft ? root.actions.filter(action => !!Bridge.settings.shortcuts[action]) : []
      RowLayout {
        id: shellEntry
        required property string modelData
        Layout.fillWidth: true
        Label {
          text: root.labels[shellEntry.modelData] || shellEntry.modelData
          Layout.fillWidth: true
          font.pixelSize: 12
        }
        ShortcutField {
          action: shellEntry.modelData
        }
        ActionButton {
          text: "Eliminar"
          onClicked: root.removeBuiltin(shellEntry.modelData)
        }
      }
    }
    ActionButton {
      text: "Añadir acción del shell"
      enabled: root.availableActions.length > 0
      onClicked: root.edit({
        type: "shell",
        action: root.availableActions[0]
      }, true)
    }
  }
  ColumnLayout {
    visible: root.mode === "custom" && !root.draft
    Layout.fillWidth: true
    spacing: 10
    ActionButton {
      text: "Añadir bind"
      accent: true
      onClicked: root.edit()
    }
    Label {
      visible: root.custom.length === 0
      text: "Añade un comando, una acción del shell o personaliza un bind de Hyprland."
      color: Theme.muted
      font.pixelSize: 11
      Layout.fillWidth: true
      wrapMode: Text.WordWrap
    }
    ListView {
      Layout.fillWidth: true
      implicitHeight: Math.min(420, contentHeight)
      clip: true
      reuseItems: true
      cacheBuffer: 80
      spacing: 10
      model: root.mode === "custom" && !root.draft ? root.custom : []
      delegate: ColumnLayout {
        id: customEntry
        required property var modelData
        width: ListView.view.width
        spacing: 4
        RowLayout {
          Layout.fillWidth: true
          Label {
            text: customEntry.modelData.name
            Layout.fillWidth: true
            elide: Text.ElideRight
          }
          Label {
            text: customEntry.modelData.chord
            color: Theme.muted
            font.family: Theme.mono
            font.pixelSize: 11
          }
          ActionButton {
            text: customEntry.modelData.enabled ? "Activo" : "Desactivado"
            selected: customEntry.modelData.enabled
            onClicked: root.toggleCustom(customEntry.modelData)
          }
          ActionButton {
            text: "Editar"
            onClicked: root.edit(customEntry.modelData)
          }
          ActionButton {
            text: "Eliminar"
            onClicked: root.removeCustom(customEntry.modelData.id)
          }
        }
        Label {
          text: customEntry.modelData.type === "inherit" ? "Conserva la acción Lua y sus opciones originales" : customEntry.modelData.type === "shell" ? root.labels[customEntry.modelData.action] : customEntry.modelData.command
          color: Theme.muted
          font.pixelSize: 11
          Layout.fillWidth: true
          elide: Text.ElideRight
        }
        Rule {}
      }
    }
  }
  ColumnLayout {
    visible: root.mode === "current" && !root.draft
    Layout.fillWidth: true
    spacing: 8
    ActionButton {
      text: "Actualizar lista"
      enabled: !Bridge.preview && !Bridge.isBusy("shortcut-list")
      onClicked: root.refresh()
    }
    ActionButton {
      text: "Usar mis combinaciones de Noctalia"
      enabled: Bridge.shortcutState.available
      onClicked: root.adoptCurrent()
    }
    Label {
      visible: !Bridge.shortcutState.available
      text: "Carga bindings-prelude.lua antes de tus binds y hyprlarp.lua al final de hyprland.lua para ver y personalizar los actuales."
      Layout.fillWidth: true
      color: Theme.muted
      wrapMode: Text.WordWrap
      font.pixelSize: 11
    }
    ListView {
      Layout.fillWidth: true
      implicitHeight: Math.min(420, contentHeight)
      clip: true
      reuseItems: true
      cacheBuffer: 80
      spacing: 8
      model: root.mode === "current" && !root.draft ? Bridge.shortcutState.bindings || [] : []
      delegate: ColumnLayout {
        id: nativeEntry
        required property var modelData
        width: ListView.view.width
        RowLayout {
          Layout.fillWidth: true
          Label {
            text: nativeEntry.modelData.chord + (nativeEntry.modelData.submap ? " · " + nativeEntry.modelData.submap : "")
            Layout.fillWidth: true
            font.family: Theme.mono
            font.pixelSize: 11
          }
          ActionButton {
            text: "Editar"
            onClicked: root.personalize(nativeEntry.modelData, false)
          }
          ActionButton {
            text: "Desactivar"
            onClicked: root.personalize(nativeEntry.modelData, true)
          }
        }
        Label {
          text: nativeEntry.modelData.command || "Acción Lua de tu configuración"
          Layout.fillWidth: true
          elide: Text.ElideRight
          color: Theme.muted
          font.pixelSize: 11
        }
        Rule {}
      }
    }
  }
  ColumnLayout {
    visible: !!root.draft
    Layout.fillWidth: true
    spacing: 10
    SectionTitle {
      text: root.draft && root.draft.source ? "Personalizar bind actual" : "Editar bind"
    }
    Field {
      id: nameField
      objectName: "bindName"
      visible: !!root.draft && !root.draft.builtin
      text: root.draft ? root.draft.name : ""
      placeholderText: "Nombre"
      maximumLength: 80
      Layout.fillWidth: true
    }
    ShortcutField {
      id: chordField
      objectName: "bindChord"
      value: root.draft ? root.draft.chord : ""
      onEdited: chord => root.updateDraft("chord", chord)
    }
    Selection {
      objectName: "bindType"
      visible: !!root.draft && !root.draft.builtin
      choices: root.draft && root.draft.source ? ["inherit", "command", "shell"] : ["command", "shell"]
      labels: root.draft && root.draft.source ? ["Conservar acción actual", "Ejecutar comando", "Acción del shell"] : ["Ejecutar comando", "Acción del shell"]
      value: root.draft ? root.draft.type : "command"
      onEdited: value => root.updateDraft("type", value)
    }
    Selection {
      visible: !!root.draft && root.draft.type === "shell"
      choices: root.draft && root.draft.builtin ? root.availableActions : root.actions
      labels: choices.map(action => root.labels[action] || action)
      value: root.draft ? root.draft.action : "launcher"
      onEdited: value => root.updateDraft("action", value)
    }
    Field {
      id: commandField
      objectName: "bindCommand"
      visible: !!root.draft && root.draft.type === "command"
      text: root.draft ? root.draft.command : ""
      placeholderText: "Comando, por ejemplo: kitty"
      maximumLength: 4096
      Layout.fillWidth: true
    }
    Label {
      visible: !!root.draft && root.draft.type === "inherit"
      text: "Se conservan la función Lua, sus flags y los callbacks al pulsar y soltar."
      color: Theme.muted
      Layout.fillWidth: true
      wrapMode: Text.WordWrap
      font.pixelSize: 11
    }
    SettingToggle {
      visible: !!root.draft && !root.draft.builtin && root.draft.type !== "inherit"
      title: "Repetir al mantener pulsado"
      checked: root.draft ? root.draft.repeat : false
      onEdited: checked => root.updateDraft("repeat", checked)
    }
    SettingToggle {
      visible: !!root.draft && !root.draft.builtin && root.draft.type !== "inherit"
      title: "Ejecutar al soltar"
      checked: root.draft ? root.draft.release : false
      onEdited: checked => root.updateDraft("release", checked)
    }
    SettingToggle {
      visible: !!root.draft && !root.draft.builtin && root.draft.type !== "inherit"
      title: "Disponible con la sesión bloqueada"
      checked: root.draft ? root.draft.locked : false
      onEdited: checked => root.updateDraft("locked", checked)
    }
    SettingToggle {
      visible: !!root.draft && !root.draft.builtin
      title: "Reemplazar otros binds de esta combinación"
      checked: root.draft ? root.draft.replace : false
      onEdited: checked => root.updateDraft("replace", checked)
    }
    RowLayout {
      ActionButton {
        text: "Guardar bind"
        accent: true
        onClicked: root.saveDraft()
      }
      ActionButton {
        text: "Cancelar"
        onClicked: root.draft = null
      }
    }
  }
  Rule {}
  SettingToggle {
    title: "Transferir las acciones de Noctalia a HyprLarp"
    checked: Bridge.settings.migrateNoctaliaBinds !== false
    onEdited: checked => Bridge.configure("migrateNoctaliaBinds", checked)
  }
  Label {
    text: "Conserva las combinaciones actuales de launcher, control, sesión y configuración. Las teclas multimedia mantienen tus callbacks; Alt+Tab recorre ventanas con Hyprland."
    color: Theme.muted
    Layout.fillWidth: true
    wrapMode: Text.WordWrap
    font.pixelSize: 11
  }
  RowLayout {
    ActionButton {
      text: "Comprobar estado"
      enabled: !Bridge.preview && !Bridge.isBusy("shortcut-list")
      onClicked: root.refresh()
    }
    ActionButton {
      text: "Aplicar binds"
      accent: true
      enabled: !Bridge.preview && !Bridge.restoring && !Bridge.isBusy("apply-shortcuts")
      onClicked: Bridge.performConfig("apply-shortcuts")
    }
  }
  Repeater {
    model: Bridge.shortcutConflicts
    Label {
      required property var modelData
      text: modelData.chord + " · Se conserva: " + modelData.command
      color: Theme.muted
      font.pixelSize: 11
      wrapMode: Text.WordWrap
      Layout.fillWidth: true
    }
  }
}
