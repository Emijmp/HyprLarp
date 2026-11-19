pragma Singleton
import QtQuick
import Quickshell
import "fuzzy.js" as Fuzzy
import "../assets/branding.js" as Branding

Singleton {
  id: root
  readonly property bool showIcons: Bridge.settings.showAppIcons === true
  readonly property string fallbackIcon: Branding.source("application", String(Theme.text), 1)
  readonly property var favoriteIds: new Set(Bridge.launcher.favorites || [])
  property var pendingIcons: new Set()
  property var requestedIcons: new Set()
  property var searchCache: new Map()
  readonly property var recency: {
    const result = Object.create(null);
    const recent = Bridge.launcher.recent || [];
    recent.forEach((entry, position) => result[entry.id] = recent.length - position);
    return result;
  }
  // Sorted once per desktop-entry update, rather than once per keystroke.
  readonly property var index: DesktopEntries.applications.values.filter(app => !app.noDisplay).map(app => ({
        app: app,
        name: Fuzzy.normalize(app.name),
        keywords: Fuzzy.normalize(app.name + " " + app.genericName + " " + app.comment),
        tokens: Fuzzy.normalize(app.name).split(/[^a-z0-9]+/).filter(Boolean)
      })).sort((a, b) => a.app.name.localeCompare(b.app.name))
  onIndexChanged: {
    const active = new Set(index.map(entry => entry.app.icon));
    const next = Object.create(null);
    for (const name of Object.keys(Bridge.appIcons))
      if (active.has(name))
        next[name] = Bridge.appIcons[name];
    Bridge.appIcons = next;
    searchCache.clear();
    requestedIcons = new Set();
  }
  function icon(name) {
    name = name || "";
    if (!name || !showIcons)
      return fallbackIcon;
    if (!name.startsWith("/") && Quickshell.hasThemeIcon(name))
      return Quickshell.iconPath(name);
    if (Bridge.appIcons[name] !== undefined)
      return Bridge.appIcons[name] || fallbackIcon;
    if (!requestedIcons.has(name)) {
      pendingIcons.add(name);
      resolveTimer.restart();
    }
    return fallbackIcon;
  }
  Timer {
    id: resolveTimer
    interval: 0
    onTriggered: {
      const names = Array.from(root.pendingIcons).slice(0, 128);
      root.pendingIcons.clear();
      if (names.length && root.showIcons) {
        for (const name of names)
          root.requestedIcons.add(name);
        Bridge.send("app-icons", {names: names});
      }
    }
  }
  function favorite(app) {
    return favoriteIds.has(app.id);
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
  function releaseSearch() {
    searchCache.clear();
    pendingIcons.clear();
    resolveTimer.stop();
  }
  function search(text, filter) {
    const query = Fuzzy.normalize(text).trim().slice(0, 128);
    // Read dependencies even for a cached query, so saved favorites/recent edits
    // invalidate the binding and its small result cache.
    const favorites = favoriteIds, recent = recency, currentIndex = index;
    const key = JSON.stringify([query, filter, Array.from(favorites), recent]);
    if (searchCache.has(key))
      return searchCache.get(key);
    const words = query ? query.split(/\s+/).slice(0, 8) : [];
    const result = currentIndex.map(entry => ({
      app: entry.app,
      score: Fuzzy.scoreWords(words, entry.name, entry.keywords, entry.tokens)
    })).filter(entry => entry.score >= 0 && (filter !== "favorites" || favorites.has(entry.app.id)) && (filter !== "recent" || recent[entry.app.id])).sort((a, b) => (b.score - a.score) || (filter === "recent" ? (recent[b.app.id] || 0) - (recent[a.app.id] || 0) : Number(favorites.has(b.app.id)) - Number(favorites.has(a.app.id))) || a.app.name.localeCompare(b.app.name)).map(entry => entry.app);
    if (searchCache.size >= 16)
      searchCache.delete(searchCache.keys().next().value);
    searchCache.set(key, result);
    return result;
  }
}
