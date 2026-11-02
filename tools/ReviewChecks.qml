import QtQuick
import Quickshell
import "../core"

Scope {
  id: root
  property int step: 0
  property var originalHistory: Notices.history
  property var emitter: null
  property real expiryStarted: 0
  signal completed
  function verify(condition, message) {
    if (!condition)
      throw new Error("Review regression: " + message);
  }
  function notification(id, name, timeout) {
    const callbacks = [];
    return {
      id: id,
      appName: name,
      desktopEntry: name,
      summary: "s".repeat(1000),
      body: "b".repeat(5000),
      appIcon: "",
      urgency: timeout ? 1 : 2,
      expireTimeout: timeout || 0,
      transient: false,
      hints: {},
      actions: [],
      tracked: false,
      closed: {
        connect: callback => callbacks.push(callback),
        disconnect: callback => {
          const index = callbacks.indexOf(callback);
          if (index >= 0)
            callbacks.splice(index, 1);
        }
      },
      callbacks: callbacks
    };
  }
  Timer {
    interval: 100
    running: true
    repeat: true
    onTriggered: {
      if (root.step === 0) {
        for (let index = 0; index < 160; index++)
          Notices.receive(root.notification(index + 1, index % 2 ? "__proto__" : "constructor", 0));
        root.verify(Notices.liveOrder.length === 64 && Object.keys(Notices.liveHandlers).length === 64, "notification flood stays bounded");
        root.verify(Notices.history.every(entry => entry.body.length <= 2048 && entry.summary.length <= 256), "notification content is bounded before persistence");
        root.verify(Notices.grouped("", "").length > 0, "prototype names cannot break notification grouping");
        root.emitter = root.notification(160, "replacement", 0);
        for (let index = 0; index < 80; index++)
          Notices.receive(root.emitter);
        root.verify(root.emitter.callbacks.length === 1, "replacing a notification disconnects its old handlers");
        const large = root.notification(9000, "oversized", 0);
        large.body = "b".repeat(100000);
        Notices.receive(large);
        root.verify(!large.tracked && !Notices.liveHandlers[9000] && large.callbacks.length === 0, "oversized native notifications are not retained");
        const identity = root.notification(9001, "identity", 0);
        identity.desktopEntry = "x".repeat(100000);
        Notices.receive(identity);
        root.verify(!identity.tracked, "oversized desktop identities are not retained");
        const clipped = Notices.boundedText("a" + String.fromCharCode(0xd83d, 0xde00).repeat(3000), 2048);
        const last = clipped.charCodeAt(clipped.length - 1);
        root.verify(!(last >= 0xd800 && last <= 0xdbff), "text bounds preserve Unicode surrogate pairs");
        root.emitter = root.notification(9999, "expiry", 25);
        Notices.receive(root.emitter);
        root.expiryStarted = Date.now();
      } else {
        if (Notices.liveTokens[9999] && Date.now() - root.expiryStarted < 1000)
          return;
        root.verify(!Notices.liveTokens[9999], "single-shot deadline expires the notification");
        for (const id of Notices.liveOrder.slice())
          Notices.forget(id);
        Notices.history = root.originalHistory;
        Notices.persist();
        stop();
        console.log("SMOKE review COMPLETE");
        root.completed();
      }
      root.step++;
    }
  }
}
