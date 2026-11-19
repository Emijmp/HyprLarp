pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io

Singleton {
  id: root
  readonly property bool preview: Quickshell.env("HYPRLARP_PREVIEW") === "1"
  readonly property bool settingsOnly: Quickshell.env("HYPRLARP_SETTINGS_ONLY") === "1"
  readonly property int backendPid: Number(service.processId) || 0
  property bool ready: false
  onReadyChanged: if (ready && Quickshell.env("HYPRLARP_BENCHMARK") === "1")
    console.log("BENCHMARK_READY " + Date.now())
  property bool connected: false
  property string settingsOperation: ""
  property string queuedSettingsOperation: ""
  property var queuedSettingsData: ({})
  property var afterSaving: []
  property var busyActions: ({})
  property var library: ({
      profiles: [],
      themes: {}
    })
  property var launcher: ({
      favorites: [],
      recent: []
    })
  property var launcherResults: ({
      token: "",
      results: [],
      truncated: false,
      error: ""
    })
  property var captureDraft: null
  property var shortcutConflicts: []
  property var shortcutState: ({
      available: false,
      bindings: [],
      conflicts: []
    })
  property int restartAttempts: 0
  property bool awaitingInitial: true
  property int settingsEditDepth: 0
  readonly property bool saving: settingsOperation !== ""
  readonly property bool restoring: queuedSettingsOperation !== "" || (saving && settingsOperation !== "settings")
  property var confirmedSettings: ({})
  property var submittedSettings: ({})
  property string submittedSource: "shell"
  property string pendingSource: "shell"
  property var settingsQueue: []
  property var configurationWindows: ({})
  readonly property bool configurationActive: Object.values(configurationWindows).some(focused => focused)
  readonly property bool hasPendingSettings: settingsQueue.length > 0 || Object.keys(pending).length > 0
  readonly property bool hasConfigurationEdits: (pendingSource === "config" && Object.keys(pending).length > 0) || settingsQueue.some(batch => batch.source === "config") || (settingsOperation === "settings" && submittedSource === "config")
  property var settingsHistory: ({
      undo: 0,
      redo: 0
    })
  property var settingsRevisions: []
  property var revisionDiff: ({
      id: "",
      changes: []
    })
  property var diagnostics: ({
      checks: [],
      versions: {}
    })
  property var performance: ({
      current: null,
      samples: [],
      history: [],
      recording: null,
      paused: false,
      panelLoads: []
    })
  readonly property bool canUndo: configurationActive && ready && connected && !restoring && (settingsHistory.undo > 0 || hasConfigurationEdits)
  readonly property bool canRedo: configurationActive && ready && connected && !restoring && !saving && !hasPendingSettings && settingsHistory.redo > 0
  readonly property bool canReset: configurationActive && ready && connected && !restoring
  property var settings: ({})
  property var moduleDefinitions: []
  property var palettes: ({})
  property var appIcons: ({})
  property var system: ({})
  property var network: ({
      networks: [],
      enabled: false,
      ssid: ""
    })
  property var bluetooth: ({
      devices: [],
      available: false,
      enabled: false
    })
  property var power: ({
      available: false,
      profile: "",
      profiles: []
    })
  property var usb: ({
      available: false,
      drives: [],
      devices: []
    })
  property var nightLight: ({
      available: false,
      active: false,
      error: ""
    })
  property var clipboard: []
  property var clipboardThumbnails: ({})
  property var wallpapers: []
  property var wallpaperPalette: ({
      path: "",
      name: "",
      colors: []
    })
  readonly property bool externalWallpaper: settings.wallpaperProvider === "external"
  property var wallpaperTools: ({
      waypaper: false,
      mpvpaper: false,
      socat: false
    })
  property var windowGapsState: ({
      enabled: false,
      applied: false,
      error: ""
    })
  property var displays: ({
      available: false,
      outputs: [],
      pending: null,
      error: "",
      notice: ""
    })
  property var wallpaperState: ({
      directory: "",
      browseUrl: "",
      error: "",
      count: 0,
      truncated: false
    })
  property var bluetoothPrompt: null
  property var history: []
  property var batteryAlerts: []
  property var faults: []
  property var pending: ({})
  property string message: ""
  property bool messageIsError: false
  property string busyAction: ""
  signal historyLoaded(var entries)
  signal actionFinished(string action)
  signal actionFailed(string action, string reason)
  signal settingsSettled

  function send(action, data, source) {
    if (!service.running) {
      toast("El servicio del sistema no está disponible", true);
      return;
    }
    service.write(JSON.stringify({
      action: action,
      data: data === undefined ? {} : data,
      source: source || "shell"
    }) + "\n");
  }
  function perform(action, data) {
    if (action === "apply-shortcuts") {
      performConfig(action, data);
      return;
    }
    dispatch(action, data, "shell");
  }
  function isBusyGroup(prefix) {
    return Object.keys(busyActions).some(action => action.startsWith(prefix) && busyActions[action] > 0);
  }
  function isBusy(action) {
    return (busyActions[action] || 0) > 0;
  }
  function dispatch(action, data, source) {
    if (!connected) {
      toast("El servicio se está reconectando", true);
      return;
    }
    busyAction = action;
    busyActions = Object.assign({}, busyActions, {
      [action]: (busyActions[action] || 0) + 1
    });
    send(action, data, source);
  }
  function performConfig(action, data) {
    if (!configurationActive || !connected)
      return;
    afterSaving = afterSaving.concat([
      {
        action: action,
        data: data || {}
      }
    ]);
    saveTimer.stop();
    flush(true);
  }
  function drainActions() {
    if (saving || hasPendingSettings || queuedSettingsOperation)
      return;
    const actions = afterSaving;
    afterSaving = [];
    if (configurationActive)
      for (const item of actions)
        dispatch(item.action, item.data, "config");
  }
  function set(key, value) {
    setMany({
      [key]: value
    });
  }
  function configure(key, value) {
    // Keep the view of origin even when a field commits while losing focus.
    setMany({
      [key]: value
    }, "config");
  }
  function configureMany(updates) {
    setMany(updates, "config");
  }
  function configurationWindow(id, focused) {
    if (!id)
      return;
    const windows = Object.assign({}, configurationWindows);
    if (focused === null)
      delete windows[id];
    else
      windows[id] = focused;
    configurationWindows = windows;
  }
  onConfigurationActiveChanged: {
    if (!configurationActive)
      queuedSettingsOperation = "";
    if (ready && connected)
      send("settings-context", {
        focused: configurationActive
      });
  }
  function queuedValues() {
    const values = {};
    for (const batch of settingsQueue)
      Object.assign(values, batch.updates);
    return values;
  }
  function setMany(updates, source) {
    if (!ready || restoring)
      return;
    source = source || "shell";
    if (Object.keys(pending).length && pendingSource !== source) {
      settingsQueue = settingsQueue.concat([
        {
          updates: pending,
          source: pendingSource
        }
      ]);
      pending = {};
    }
    pendingSource = source;
    const next = Object.assign({}, settings);
    const changes = Object.assign({}, pending);
    const baseline = Object.assign({}, confirmedSettings, submittedSettings, queuedValues());
    let changed = false;
    for (const key of Object.keys(updates)) {
      const value = updates[key];
      if (JSON.stringify(next[key]) === JSON.stringify(value))
        continue;
      changed = true;
      next[key] = value;
      if (JSON.stringify(baseline[key]) === JSON.stringify(value))
        delete changes[key];
      else
        changes[key] = value;
    }
    if (!changed)
      return;
    settings = next;
    pending = changes;
    if (settingsEditDepth === 0)
      saveTimer.restart();
  }
  function beginSettingsEdit() {
    settingsEditDepth++;
    saveTimer.stop();
  }
  function endSettingsEdit() {
    settingsEditDepth = Math.max(0, settingsEditDepth - 1);
    if (settingsEditDepth === 0 && hasPendingSettings)
      saveTimer.restart();
  }
  function undo() {
    if (canUndo)
      restoreSettings("settings-undo");
  }
  function redo() {
    if (canRedo)
      restoreSettings("settings-redo");
  }
  function resetSettings() {
    if (canReset)
      restoreSettings("settings-reset");
  }
  function restoreSettings(action, data) {
    if (!configurationActive)
      return;
    queuedSettingsOperation = action;
    queuedSettingsData = data || {};
    saveTimer.stop();
    flush();
  }
  function flush(force) {
    if (!ready || saving || !connected || (!force && settingsEditDepth > 0 && !queuedSettingsOperation && !settingsQueue.length))
      return;
    if (hasPendingSettings) {
      let batch;
      if (settingsQueue.length) {
        const queue = settingsQueue.slice();
        batch = queue.shift();
        settingsQueue = queue;
      } else {
        batch = {
          updates: pending,
          source: pendingSource
        };
        pending = {};
      }
      submittedSettings = batch.updates;
      submittedSource = batch.source;
      settingsOperation = "settings";
      send("settings", submittedSettings, submittedSource);
    } else if (queuedSettingsOperation !== "" && configurationActive) {
      settingsOperation = queuedSettingsOperation;
      queuedSettingsOperation = "";
      send(settingsOperation, queuedSettingsData, "config");
      queuedSettingsData = {};
    } else {
      drainActions();
    }
  }
  function toast(text, error) {
    message = text;
    messageIsError = error || false;
    toastTimer.restart();
  }
  function consume(line) {
    try {
      const event = JSON.parse(line);
      switch (event.type) {
      case "modules":
        moduleDefinitions = event.data;
        break;
      case "palettes":
        palettes = event.data;
        break;
      case "library":
        library = event.data;
        break;
      case "launcher":
        launcher = event.data;
        break;
      case "launcher-results":
        launcherResults = event.data;
        break;
      case "capture-edit":
        captureDraft = event.data;
        break;
      case "shortcut-conflicts":
        shortcutConflicts = event.data;
        break;
      case "shortcut-state":
        shortcutState = event.data;
        break;
      case "app-icons":
        appIcons = Object.assign(Object.create(null), appIcons, event.data);
        break;
      case "settings":
        const initial = awaitingInitial;
        awaitingInitial = false;
        confirmedSettings = event.data;
        submittedSettings = {};
        settings = Object.assign({}, confirmedSettings, queuedValues(), pending);
        settingsOperation = "";
        ready = true;
        if (initial) {
          send("performance-ready");
          send("settings-context", {
            focused: configurationActive
          });
          send("outputs", {
            names: Quickshell.screens.map(screen => screen.name)
          });
          send("panel", {
            name: ShellState.panel
          });
          stableTimer.restart();
        }
        if (queuedSettingsOperation || settingsQueue.length || (Object.keys(pending).length && !saveTimer.running && settingsEditDepth === 0))
          flush();
        if (!saving && !queuedSettingsOperation && !hasPendingSettings) {
          drainActions();
          settingsSettled();
        }
        break;
      case "settings-history":
        settingsHistory = event.data;
        break;
      case "settings-revisions":
        settingsRevisions = event.data;
        break;
      case "settings-revision-diff":
        revisionDiff = event.data;
        break;
      case "diagnostics":
        diagnostics = event.data;
        break;
      case "performance":
        performance = event.data;
        break;
      case "settings-rejected":
        afterSaving = [];
        if (event.data.action === "settings" && queuedSettingsOperation === "settings-undo")
          queuedSettingsOperation = "";
        break;
      case "power":
        power = event.data;
        break;
      case "usb":
        usb = event.data;
        break;
      case "night-light":
        nightLight = event.data;
        break;
      case "system":
        system = event.data;
        break;
      case "network":
        network = event.data;
        break;
      case "bluetooth":
        bluetooth = event.data;
        break;
      case "clipboard-thumbnail":
        {
          const next = Object.assign({}, clipboardThumbnails);
          delete next[event.data.id];
          next[event.data.id] = event.data.url;
          for (const key of Object.keys(next).slice(0, -16))
            delete next[key];
          clipboardThumbnails = next;
        }
        break;
      case "clipboard":
        clipboard = event.data;
        {
          const present = new Set(clipboard.map(entry => String(entry.id)));
          const kept = {};
          for (const key of Object.keys(clipboardThumbnails))
            if (present.has(key))
              kept[key] = clipboardThumbnails[key];
          clipboardThumbnails = kept;
        }
        break;
      case "wallpapers":
        wallpapers = event.data;
        break;
      case "wallpaper-palette":
        wallpaperPalette = event.data;
        break;
      case "wallpaper-tools":
        wallpaperTools = event.data;
        break;
      case "window-gaps":
        windowGapsState = event.data;
        break;
      case "displays":
        displays = event.data;
        break;
      case "wallpaper-state":
        wallpaperState = event.data;
        break;
      case "bluetooth-prompt":
        bluetoothPrompt = event.data;
        break;
      case "action-error":
        actionFailed(event.data.action, event.data.message);
        break;
      case "history":
        history = event.data;
        historyLoaded(event.data);
        break;
      case "battery-alert":
        batteryAlerts = batteryAlerts.concat([event.data]).slice(-8);
        break;
      case "faults":
        faults = event.data;
        break;
      case "error":
        toast(event.data, true);
        break;
      case "message":
        toast(event.data, false);
        break;
      case "done":
        actionFinished(event.data.action);
        break;
      case "idle":
        const remaining = Object.assign({}, busyActions);
        remaining[event.data.action] = Math.max(0, (remaining[event.data.action] || 1) - 1);
        busyActions = remaining;
        if (busyAction === event.data.action)
          busyAction = "";
        break;
      }
    } catch (error) {
      console.warn("HyprLarp bridge:", String(error));
    }
  }
  Timer {
    id: saveTimer
    interval: 250
    onTriggered: root.flush()
  }
  Timer {
    id: toastTimer
    interval: 6000
    onTriggered: root.message = ""
  }
  Timer {
    id: restartTimer
    onTriggered: service.running = true
  }
  Timer {
    id: stableTimer
    interval: 60000
    onTriggered: root.restartAttempts = 0
  }
  Connections {
    target: Quickshell
    function onScreensChanged() {
      if (root.connected && root.ready)
        root.send("outputs", {
          names: Quickshell.screens.map(screen => screen.name)
        });
    }
  }
  Process {
    id: service
    command: ["python3", Quickshell.shellPath("backend/service.py")].concat(root.preview ? ["--preview"] : ["--native-services"]).concat(root.settingsOnly ? ["--settings-only"] : [])
    stdinEnabled: true
    running: true
    onStarted: {
      root.connected = true;
      root.awaitingInitial = true;
    }
    onExited: (code, status) => {
      root.connected = false;
      stableTimer.stop();
      if (root.settingsOperation === "settings" && Object.keys(root.submittedSettings).length)
        root.settingsQueue = [
          {
            updates: root.submittedSettings,
            source: root.submittedSource
          }
        ].concat(root.settingsQueue);
      root.submittedSettings = {};
      if (root.captureDraft) {
        root.captureDraft = null;
        root.toast("El borrador de captura se cerró al reiniciar el servicio", true);
      }
      root.busyActions = {};
      root.busyAction = "";
      root.afterSaving = [];
      root.settingsOperation = "";
      root.queuedSettingsOperation = "";
      if (root.restartAttempts < 3) {
        restartTimer.interval = 1000 * Math.pow(2, root.restartAttempts++);
        restartTimer.restart();
        root.toast("Servicio desconectado. Reconectando…", true);
      } else {
        root.toast("El servicio no pudo reiniciarse después de tres intentos. Revisa el registro.", true);
        if (!root.preview && !root.settingsOnly)
          Resilience.recover();
      }
    }
    stdout: SplitParser {
      onRead: data => root.consume(data)
    }
    stderr: SplitParser {
      onRead: data => console.warn("HyprLarp:", data)
    }
  }
}
