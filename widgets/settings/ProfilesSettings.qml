import QtQuick
import QtQuick.Layouts
import QtQuick.Dialogs
import "../../core"
import "../../components"
import "." as SettingsControls

ColumnLayout {
  id: root
  spacing: 12
  property string pendingFileAction: ""
  property string pendingPath: ""
  property string exportKind: "profile"
  function finishFile() {
    if (!pendingPath || !Bridge.configurationActive)
      return;
    if (pendingFileAction === "import")
      Bridge.restoreSettings("settings-import", {
        path: pendingPath
      });
    else
      Bridge.performConfig("settings-export", {
        path: pendingPath,
        kind: exportKind
      });
    pendingPath = "";
  }
  Connections {
    target: Bridge
    function onConfigurationActiveChanged() {
      root.finishFile();
    }
  }
  Label {
    text: "Los perfiles guardan tema, barra, módulos, monitores y preferencias. Aplicarlos se puede deshacer. Antes de importar o aplicar se conserva settings.backup.json."
    Layout.fillWidth: true
    wrapMode: Text.WordWrap
    color: Theme.muted
    font.pixelSize: Theme.fontPx(11)
  }
  SectionTitle {
    text: "Perfiles"
  }
  RowLayout {
    Field {
      id: profileName
      placeholderText: "Nombre del perfil"
      maximumLength: 40
      Layout.fillWidth: true
    }
    ActionButton {
      text: "Guardar actual"
      enabled: profileName.text.trim().length > 0
      onClicked: Bridge.performConfig("profile-save", {
        name: profileName.text
      })
    }
  }
  Repeater {
    model: Bridge.library.profiles || []
    RowLayout {
      id: profile
      required property string modelData
      Label {
        text: profile.modelData
        Layout.fillWidth: true
      }
      ActionButton {
        text: "Aplicar"
        onClicked: Bridge.restoreSettings("profile-apply", {
          name: profile.modelData
        })
      }
      ActionButton {
        text: "Eliminar"
        onClicked: Bridge.performConfig("profile-delete", {
          name: profile.modelData
        })
      }
    }
  }
  Rule {}
  SectionTitle {
    text: "Mis temas"
  }
  RowLayout {
    Field {
      id: themeName
      placeholderText: "Nombre de la paleta"
      maximumLength: 40
      Layout.fillWidth: true
    }
    ActionButton {
      text: "Guardar paleta"
      enabled: themeName.text.trim().length > 0
      onClicked: Bridge.performConfig("theme-save", {
        name: themeName.text
      })
    }
  }
  Repeater {
    model: Object.keys(Bridge.library.themes || {})
    RowLayout {
      id: theme
      required property string modelData
      Rectangle {
        width: 20
        height: 20
        color: Bridge.library.themes[theme.modelData].surface
        border.width: 1
        border.color: Bridge.library.themes[theme.modelData].border
      }
      Label {
        text: theme.modelData
        Layout.fillWidth: true
      }
      ActionButton {
        text: "Aplicar"
        onClicked: Bridge.restoreSettings("theme-use", {
          name: theme.modelData
        })
      }
      ActionButton {
        text: "Eliminar"
        onClicked: Bridge.performConfig("theme-delete", {
          name: theme.modelData
        })
      }
    }
  }
  Rule {}
  SectionTitle {
    text: "Importar / exportar"
  }
  RowLayout {
    ActionButton {
      text: "Importar JSON…"
      onClicked: {
        root.pendingFileAction = "import";
        file.fileMode = FileDialog.OpenFile;
        file.open();
      }
    }
    ActionButton {
      text: "Exportar perfil…"
      onClicked: {
        root.pendingFileAction = "export";
        root.exportKind = "profile";
        file.fileMode = FileDialog.SaveFile;
        file.open();
      }
    }
    ActionButton {
      text: "Exportar tema…"
      onClicked: {
        root.pendingFileAction = "export";
        root.exportKind = "theme";
        file.fileMode = FileDialog.SaveFile;
        file.open();
      }
    }
  }
  FileDialog {
    id: file
    title: root.pendingFileAction === "import" ? "Importar configuración o tema" : "Exportar " + (root.exportKind === "theme" ? "tema" : "perfil")
    nameFilters: ["JSON (*.json)"]
    defaultSuffix: "json"
    onAccepted: {
      root.pendingPath = selectedFile.toString();
      Qt.callLater(root.finishFile);
    }
  }
  Rule {}
  SettingsControls.RevisionHistory {
    Layout.fillWidth: true
  }
}
