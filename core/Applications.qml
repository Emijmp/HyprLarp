pragma Singleton
import QtQuick
import Quickshell
import "fuzzy.js" as Fuzzy

Singleton {
  id: root
  readonly property bool showIcons: Bridge.settings.showAppIcons === true
  onShowIconsChanged: if (showIcons)
    resolveTimer.restart()
  // Sorted once per desktop-entry update, rather than once per keystroke.
  readonly property var index: DesktopEntries.applications.values.filter(app => !app.noDisplay).map(app => ({
        app: app,
        name: Fuzzy.normalize(app.name),
        keywords: Fuzzy.normalize(app.name + " " + app.genericName + " " + app.comment)
      })).sort((a, b) => a.app.name.localeCompare(b.app.name))
  onIndexChanged: resolveTimer.restart()
  Component.onCompleted: resolveTimer.restart()
  function icon(name) {
    if (name.startsWith("/"))
      return Bridge.appIcons[name] || Qt.resolvedUrl("../assets/application.svg");
    if (Quickshell.hasThemeIcon(name))
      return Quickshell.iconPath(name);
    return Bridge.appIcons[name] || Qt.resolvedUrl("../assets/application.svg");
  }
  Timer {
    id: resolveTimer
    interval: 0
    onTriggered: {
      const names = Array.from(new Set(root.index.map(entry => entry.app.icon || "").filter(name => name && (name.startsWith("/") || !Quickshell.hasThemeIcon(name)) && Bridge.appIcons[name] === undefined)));
      if (names.length && Bridge.settings.showAppIcons)
        Bridge.send("app-icons", {
          names: names
        });
    }
  }
  function favorite(app) {
    return (Bridge.launcher.favorites || []).includes(app.id);
  }
  function toggleFavorite(app) {
    Bridge.perform("launcher-favorite", {
      id: app.id
    });
  }
  function launched(app) {
    Bridge.perform("launcher-used", {
      id: app.id
    });
  }
  function search(text, filter) {
    const query = Fuzzy.normalize(text).trim().slice(0, 128);
    const recent = Bridge.launcher.recent || [];
    const recency = {};
    recent.forEach((entry, index) => recency[entry.id] = recent.length - index);
    return index.map(entry => ({
          app: entry.app,
          score: Fuzzy.score(query, entry.name, entry.keywords)
        })).filter(entry => entry.score >= 0 && (filter !== "favorites" || favorite(entry.app)) && (filter !== "recent" || recency[entry.app.id])).sort((a, b) => (b.score - a.score) || (filter === "recent" ? (recency[b.app.id] || 0) - (recency[a.app.id] || 0) : Number(favorite(b.app)) - Number(favorite(a.app))) || a.app.name.localeCompare(b.app.name)).map(entry => entry.app);
  }
}
