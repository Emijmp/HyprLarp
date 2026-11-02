pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Services.Notifications

Singleton {
  id: root
  property var history: Bridge.history
  property var popups: []
  property var deadlines: ({})
  property var liveTokens: ({})
  readonly property int unread: history.filter(n => !n.read).length
  function persist() {
    Bridge.send("history", history);
  }
  function receive(notification) {
    notification.tracked = true;
    const now = Date.now();
    const item = {
      id: notification.id,
      token: String(now) + ":" + notification.id,
      app: notification.appName || "Aplicación",
      appId: notification.desktopEntry || notification.appName || "Aplicación",
      summary: notification.summary,
      body: notification.body,
      icon: notification.appIcon,
      time: now,
      urgency: notification.urgency,
      read: false,
      timeout: notification.expireTimeout === 0 || (notification.urgency === NotificationUrgency.Critical && notification.expireTimeout < 0) ? 0 : now + (notification.expireTimeout > 0 ? notification.expireTimeout : 6000)
    };
    const previousToken = liveTokens[notification.id];
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
    notification.closed.connect(function () {
      if (root.liveTokens[id] !== item.token)
        return;
      root.popups = root.popups.filter(n => n.token !== item.token);
      const nextDeadlines = Object.assign({}, root.deadlines);
      delete nextDeadlines[id];
      root.deadlines = nextDeadlines;
      const nextTokens = Object.assign({}, root.liveTokens);
      delete nextTokens[id];
      root.liveTokens = nextTokens;
    });
  }
  function grouped(query, app) {
    query = query.toLowerCase().trim();
    const groups = {}, order = [];
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
    const notification = live(id, token);
    if (notification)
      notification.dismiss();
    popups = popups.filter(n => token !== undefined ? n.token !== token : n.id !== id);
  }
  function actions(id, token) {
    const n = live(id, token);
    return n ? n.actions : [];
  }
  function markRead() {
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
    interval: 500
    running: Object.keys(root.deadlines).some(id => root.deadlines[id] > 0)
    repeat: true
    onTriggered: {
      const expired = Object.keys(root.deadlines).filter(id => root.deadlines[id] > 0 && root.deadlines[id] <= Date.now());
      for (const id of expired) {
        const notification = root.live(Number(id));
        if (notification)
          notification.expire();
      }
    }
  }
}
