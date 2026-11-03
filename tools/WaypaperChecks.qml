import QtQuick
import QtQuick.Window
import Quickshell
import "../core"
import "../widgets"

Scope {
  id: root
  required property var view
  property int step: 0
  property var original: null
  property real deadline: Date.now() + 12000
  readonly property var selector: view.currentPage ? view.currentPage.item : null
  signal completed
  function verify(condition, message) {
    if (!condition)
      throw new Error("Waypaper regression: " + message);
  }
  function find(item, name) {
    if (item.objectName === name)
      return item;
    for (const child of item.children || []) {
      const found = find(child, name);
      if (found)
        return found;
    }
    return null;
  }
  FloatingWindow {
    visible: true
    implicitWidth: 280
    implicitHeight: 160
    Wallpaper {
      id: wallpaper
      anchors.fill: parent
    }
  }
  Timer {
    interval: 110
    repeat: true
    running: true
    onTriggered: {
      root.verify(Date.now() < root.deadline, "wallpaper provider checks timed out");
      if (!Bridge.configurationActive) {
        root.view.Window.window.requestActivate();
        return;
      }
      if (Bridge.saving || Bridge.restoring || Bridge.hasPendingSettings || Bridge.afterSaving.length)
        return;
      switch (root.step) {
      case 0:
        root.original = {
          wallpaper: Bridge.settings.wallpaper,
          wallpaperDirectory: Bridge.settings.wallpaperDirectory,
          wallpaperProvider: Bridge.settings.wallpaperProvider,
          waypaperRestoreOnStartup: Bridge.settings.waypaperRestoreOnStartup
        };
        root.view.tab = 3;
        Bridge.configureMany({
          wallpaperProvider: "internal",
          wallpaper: Quickshell.shellPath("assets/wallpapers/amoled.svg"),
          waypaperRestoreOnStartup: false
        });
        break;
      case 1:
        if (!root.selector || wallpaper.children[0].status !== Image.Ready)
          return;
        root.verify(!Bridge.externalWallpaper, "internal wallpaper remains the initial provider");
        root.selector.edit("wallpaperProvider", "external");
        break;
      case 2:
        root.verify(Bridge.externalWallpaper && root.selector.external, "external provider is reflected in the panel and desktop state");
        root.verify(String(wallpaper.children[0].source) === "", "external provider releases the internal image");
        root.verify(root.find(root.selector, "wallpaperGrid").count === 0, "hidden image gallery releases its delegates");
        root.verify(Bridge.settings.wallpaper.endsWith("amoled.svg"), "external provider retains the previous image");
        Bridge.undo();
        break;
      case 3:
        if (wallpaper.children[0].status !== Image.Ready)
          return;
        root.verify(!Bridge.externalWallpaper, "undo recovers the internal provider and image");
        Bridge.redo();
        break;
      case 4:
        root.verify(Bridge.externalWallpaper, "redo restores external wallpaper mode");
        root.selector.edit("waypaperRestoreOnStartup", true);
        break;
      case 5:
        root.verify(Bridge.confirmedSettings.waypaperRestoreOnStartup, "startup restore choice persists");
        Bridge.undo();
        break;
      case 6:
        root.verify(!Bridge.settings.waypaperRestoreOnStartup, "startup restore is undoable");
        Bridge.redo();
        break;
      case 7:
        Bridge.restoreSettings("settings-reset-section", {
          section: "Wallpapers"
        });
        break;
      case 8:
        root.verify(!Bridge.externalWallpaper && !Bridge.settings.waypaperRestoreOnStartup && !Bridge.settings.wallpaper, "wallpaper section reset restores the internal defaults");
        Bridge.undo();
        break;
      case 9:
        root.verify(Bridge.externalWallpaper && Bridge.settings.waypaperRestoreOnStartup && Bridge.settings.wallpaper.endsWith("amoled.svg"), "undo section reset restores external preferences and saved image");
        Bridge.configureMany(root.original);
        break;
      default:
        stop();
        console.log("SMOKE Waypaper COMPLETE");
        root.completed();
      }
      root.step++;
    }
  }
}
