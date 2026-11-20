pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Services.Notifications

Singleton {
  id: root
  property var history: []
  property bool historyInitialized: false
  property bool historyDirty: false
  property bool readStoredHistory: false
  property bool discardStoredHistory: false
  property var popups: []
  property var deadlines: ({})
  property var liveTokens: ({})
  property var liveHandlers: ({})
  property var liveOrder: []
  property int sequence: 0
  function batteryWarnings() {
    const pending = Bridge.batteryAlerts;
    if (!pending.length)
      return;
    Bridge.batteryAlerts = [];
    if (Bridge.preview || Bridge.settingsOnly)
      return;
    for (const alert of pending) {
      const now = Date.now();
      const item = {
        id: -1, token: "battery:" + now + ":" + (++sequence), app: "HyprLarp", appId: "hyprlarp-battery",
        summary: alert.level === "critical" ? "Batería crítica" : "Batería baja",
        body: "Queda " + alert.percent + "% de batería. Conecta el cargador.", icon: "", time: now,
        urgency: alert.level === "critical" ? 2 : 1, read: false, timeout: now + 10000
      };
      const rule = (Bridge.settings.notificationRules || {})[item.appId] || {};
      if (rule.history !== false) {
        history = [item].concat(history).slice(0, Bridge.settings.notificationHistoryLimit ?? 100);
        persist();
      }
      if (rule.popup !== false && !Presentation.active && (!Bridge.settings.doNotDisturb || alert.level === "critical")) {
        popups = popups.concat([item]).slice(-3);
        deadlines = Object.assign({}, deadlines, {[item.token]: item.timeout});
      }
    }
  }
  function loadHistory(entries) {
    if (!historyInitialized) {
      const received = new Set(history.map(item => item.token));
      const stored = discardStoredHistory ? [] : entries.filter(item => !received.has(item.token)).map(item => readStoredHistory ? Object.assign({}, item, {read: true}) : item);
      history = history.concat(stored).slice(0, Bridge.settings.notificationHistoryLimit ?? 100);
      historyInitialized = true;
      if (historyDirty)
        persist();
    } else if (historyDirty || JSON.stringify(history) !== JSON.stringify(entries)) {
      // The in-memory history remains authoritative after a backend restart.
      // Replay edits that had not reached disk, without restoring removed rows.
      persist();
    }
  }
  Component.onCompleted: {
    if (Bridge.notificationHistoryReady)
      loadHistory(Bridge.history);
    batteryWarnings();
  }
  Connections {
    target: Bridge
    function onBatteryAlertsChanged() { root.batteryWarnings(); }
    function onHistoryLoaded(entries) { root.loadHistory(entries); }
    function onConnectedChanged() {
      if (!Bridge.connected)
        persistTimer.stop();
    }
  }
  readonly property int unread: history.filter(n => !n.read).length
  function persist() {
    historyDirty = true;
    if (historyInitialized && Bridge.connected && Bridge.notificationHistoryReady && !persistTimer.running)
      persistTimer.start();
  }
  function forget(id) {
    const previous = liveHandlers[id];
    if (previous) {
      try {
        previous.notification.closed.disconnect(previous.handler);
      } catch (error) {}
    }
    const handlers = Object.assign({}, liveHandlers), tokens = Object.assign({}, liveTokens), times = Object.assign({}, deadlines);
    const token = tokens[id];
    delete handlers[id];
    delete tokens[id];
    delete times[id];
    liveHandlers = handlers;
    liveTokens = tokens;
    deadlines = times;
    liveOrder = liveOrder.filter(value => value !== id);
    popups = popups.filter(item => item.token !== token);
  }
  function scheduleExpiry() {
    const pending = Object.values(deadlines).filter(value => value > 0);
    if (!pending.length) {
      expiryTimer.stop();
      return;
    }
    expiryTimer.interval = Math.max(1, Math.min(2147483647, Math.min(...pending) - Date.now()));
    expiryTimer.restart();
  }
  onDeadlinesChanged: scheduleExpiry()
  function boundedText(value, maximum) {
    value = value || "";
    if (value.length <= maximum)
      return value;
    const last = value.charCodeAt(maximum - 1);
    if (last >= 0xd800 && last <= 0xdbff)
      maximum--;
    const codes = [];
    for (let index = 0; index < maximum; index++)
      codes.push(value.charCodeAt(index));
    return String.fromCharCode(...codes);
  }
  function receive(notification) {
    const oversized = notification.body.length > 8192 || notification.summary.length > 1024 || notification.appName.length > 1024 || notification.desktopEntry.length > 1024 || notification.appIcon.length > 4096 || notification.actions.length > 32 || Array.prototype.some.call(notification.actions, action => action.text.length > 256);
    notification.tracked = !oversized;
    const now = Date.now();
    const previousToken = liveTokens[notification.id];
    if (previousToken)
      forget(notification.id);
    if (liveOrder.length >= 64) {
      const id = liveOrder[0], old = live(id, liveTokens[id]);
      if (old)
        old.dismiss();
      forget(id);
    }
    sequence++;
    const item = {
      id: notification.id,
      token: String(now) + ":" + notification.id + ":" + sequence,
      app: boundedText(notification.appName || "Aplicación", 128),
      appId: boundedText(notification.desktopEntry || notification.appName || "Aplicación", 128),
      summary: boundedText(notification.summary, 256),
      body: boundedText(notification.body, 2048),
      icon: boundedText(notification.appIcon, 1024),
      time: now,
      urgency: notification.urgency,
      read: false,
      timeout: notification.expireTimeout === 0 || (notification.urgency === NotificationUrgency.Critical && notification.expireTimeout < 0) ? 0 : now + (notification.expireTimeout > 0 ? notification.expireTimeout : 6000)
    };
    if (oversized)
      item.timeout = now + 6000;
    liveOrder = liveOrder.concat([notification.id]);
    liveTokens = Object.assign({}, liveTokens, {
      [notification.id]: item.token
    });
    deadlines = Object.assign({}, deadlines, {
      [notification.id]: item.timeout
    });
    const rule = (Bridge.settings.notificationRules || {})[item.appId] || (Bridge.settings.notificationRules || {})[item.app] || {};
    if (!notification.transient && rule.history !== false) {
      history = [item].concat(history.filter(n => n.token !== previousToken)).slice(0, Bridge.settings.notificationHistoryLimit === undefined ? 100 : Bridge.settings.notificationHistoryLimit);
      persist();
    }
    if (rule.popup !== false && !Presentation.active && (!Bridge.settings.doNotDisturb || notification.urgency === NotificationUrgency.Critical))
      popups = popups.filter(n => n.id !== item.id).concat([item]).slice(-3);
    if (rule.sound === true && !Bridge.preview && !Bridge.settingsOnly && !Bridge.settings.doNotDisturb && !Presentation.active && !notification.hints["suppress-sound"] && !sound.running)
      sound.running = true;
    const id = notification.id;
    const handler = function () {
      if (root.liveTokens[id] !== item.token)
        return;
      root.forget(id);
    };
    if (!oversized) {
      liveHandlers = Object.assign({}, liveHandlers, {
        [id]: {
          notification: notification,
          handler: handler
        }
      });
      notification.closed.connect(handler);
    }
  }
  function grouped(query, app) {
    query = query.toLowerCase().trim();
    const groups = Object.create(null), order = [];
    for (const item of history) {
      if ((app && item.app !== app) || (query && !(item.app + " " + item.summary + " " + item.body).toLowerCase().includes(query)))
        continue;
      if (!groups[item.app]) {
        groups[item.app] = [];
        order.push(item.app);
      }
      groups[item.app].push(item);
    }
    const result = [];
    for (const name of order) {
      result.push({
        kind: "header",
        app: name,
        count: groups[name].length
      });
      for (const item of groups[name])
        result.push({
          kind: "notice",
          entry: item
        });
    }
    return result;
  }
  Connections {
    target: Presentation
    function onActiveChanged() {
      if (Presentation.active)
        root.popups = [];
    }
  }
  Process {
    id: sound
    command: ["pw-play", Quickshell.shellPath("assets/notification.wav")]
  }
  function live(id, token) {
    if (token !== undefined && liveTokens[id] !== token)
      return null;
    return daemon.item ? daemon.item.trackedNotifications.values.find(n => n.id === id) : null;
  }
  function dismiss(id, token) {
    if (id === -1) {
      const times = Object.assign({}, deadlines);
      delete times[token];
      deadlines = times;
      popups = popups.filter(item => item.token !== token);
      return;
    }
    const notification = live(id, token);
    if (notification)
      notification.dismiss();
    else
      forget(id);
    popups = popups.filter(n => token !== undefined ? n.token !== token : n.id !== id);
  }
  function actions(id, token) {
    const n = live(id, token);
    return n ? Array.prototype.slice.call(n.actions, 0, 8) : [];
  }
  function markRead() {
    if (!historyInitialized)
      readStoredHistory = true;
    history = history.map(n => Object.assign({}, n, {
        read: true
      }));
    persist();
  }
  function remove(token) {
    history = history.filter(n => n.token !== token);
    persist();
  }
  function clear() {
    if (!historyInitialized)
      discardStoredHistory = true;
    history = [];
    persist();
  }
  LazyLoader {
    id: daemon
    active: !Bridge.preview && !Bridge.settingsOnly
    component: NotificationServer {
      keepOnReload: false
      actionsSupported: true
      bodySupported: true
      bodyMarkupSupported: false
      persistenceSupported: true
      onNotification: notification => root.receive(notification)
    }
  }
  Timer {
    id: persistTimer
    interval: 200
    onTriggered: {
      if (!root.historyInitialized || !Bridge.connected || !Bridge.notificationHistoryReady)
        return;
      root.historyDirty = false;
      Bridge.send("history", root.history);
    }
  }
  Timer {
    id: expiryTimer
    onTriggered: {
      const expired = Object.keys(root.deadlines).filter(id => root.deadlines[id] > 0 && root.deadlines[id] <= Date.now());
      for (const id of expired) {
        if (id.startsWith("battery:")) {
          root.dismiss(-1, id);
          continue;
        }
        const notification = root.live(Number(id));
        if (notification)
          notification.expire();
        root.forget(Number(id));
      }
      root.scheduleExpiry();
    }
  }
}
