import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Services.Greetd

Scope {
  id: root
  readonly property bool preview: Quickshell.env("HYPRLARP_GREETER_PREVIEW") === "1"
  readonly property bool testMode: preview && Quickshell.env("HYPRLARP_GREETER_TEST") === "1"
  readonly property string stateDirectory: Quickshell.env("HYPRLARP_GREETER_STATE_DIR") || "/var/lib/noctalia-greeter"
  readonly property string preferencesPath: Quickshell.env("HYPRLARP_GREETER_PREFERENCES") || "/var/lib/hyprlarp-greeter/preferences/layout.json"
  property var model: ({
      appearance: {},
      users: [],
      sessions: [],
      hostname: ""
    })
  property bool ready: false
  property bool busy: false
  property bool awaitingResponse: false
  readonly property bool authenticating: busy || awaitingResponse
  property bool echoResponse: false
  property string prompt: "Contraseña"
  property string message: ""
  property bool messageIsError: false
  property string userName: ""
  property int sessionIndex: 0
  property string pendingResponse: ""
  property bool hasPendingResponse: false
  property var loginSession: null
  property bool reloadPending: false
  property string powerConfirmation: ""
  property var keyboard: ({capsLock: null, layout: "Predeterminado"})
  signal clearInput
  signal modelUpdated

  function applyModel(text) {
    try {
      const next = JSON.parse(text);
      if (next.error || !next.appearance || !Array.isArray(next.sessions))
        throw new Error(next.error || "Datos del greeter inválidos");
      const previous = model.sessions[sessionIndex]?.id || next.default_session;
      model = next;
      if (!userName)
        userName = next.default_user || next.users[0]?.name || "";
      sessionIndex = Math.max(0, next.sessions.findIndex(entry => entry.id === previous));
      ready = true;
      modelUpdated();
    } catch (error) {
      message = "No se pudo leer la configuración del inicio de sesión.";
      messageIsError = true;
    }
  }
  function reload() {
    reloadPending = true;
    reloadTimer.restart();
  }
  function clearSecret() {
    pendingResponse = "";
    hasPendingResponse = false;
    clearInput();
  }
  function failure(text) {
    clearSecret();
    busy = false;
    awaitingResponse = false;
    echoResponse = false;
    prompt = "Contraseña";
    message = text || "No se pudo iniciar sesión. Inténtalo de nuevo.";
    messageIsError = true;
  }
  function submit(response) {
    if (busy)
      return;
    if (!Greetd.available || (preview && !testMode)) {
      failure(preview ? "Vista previa: el inicio de sesión está desactivado." : "No se pudo conectar con el servicio de inicio de sesión.");
      return;
    }
    message = "";
    messageIsError = false;
    if (awaitingResponse) {
      awaitingResponse = false;
      busy = true;
      clearInput();
      Greetd.respond(response);
      return;
    }
    if (!userName.trim() || !model.sessions[sessionIndex]) {
      failure("Selecciona un usuario y una sesión.");
      return;
    }
    if (Greetd.state !== GreetdState.Inactive) {
      failure("Espera a que termine la solicitud anterior o pulsa Cancelar.");
      return;
    }
    loginSession = model.sessions[sessionIndex];
    pendingResponse = response;
    hasPendingResponse = true;
    busy = true;
    clearInput();
    Greetd.createSession(userName.trim());
  }
  function cancel() {
    powerConfirmation = "";
    clearSecret();
    if (Greetd.available && Greetd.state !== GreetdState.Inactive)
      Greetd.cancelSession();
    busy = false;
    awaitingResponse = false;
    echoResponse = false;
    prompt = "Contraseña";
    message = "";
    messageIsError = false;
  }
  function power(action) {
    if (preview || authenticating || !["poweroff", "reboot", "suspend"].includes(action))
      return;
    if (powerConfirmation !== action) {
      powerConfirmation = action;
      return;
    }
    powerConfirmation = "";
    powerProcess.command = ["/usr/bin/systemctl", action];
    powerProcess.running = true;
  }

  Timer {
    interval: 60000
    running: root.busy
    onTriggered: {
      root.cancel();
      root.failure("El servicio tardó demasiado en responder. Inténtalo de nuevo.");
    }
  }
  Timer {
    id: reloadTimer
    interval: 70
    onTriggered: {
      if (dataProcess.running)
        return;
      root.reloadPending = false;
      dataProcess.running = true;
    }
  }
  Process {
    id: keyboardProcess
    command: ["/usr/bin/python3", Quickshell.shellPath("model.py"), "--keyboard-watch"]
    environment: ({HYPRLARP_GREETER_STATE_DIR: root.stateDirectory})
    running: true
    stdout: SplitParser {
      onRead: data => {
        try { root.keyboard = JSON.parse(data); } catch (error) {}
      }
    }
  }
  Process {
    id: dataProcess
    command: ["/usr/bin/python3", Quickshell.shellPath("model.py")]
    environment: ({
        HYPRLARP_GREETER_STATE_DIR: root.stateDirectory,
        HYPRLARP_GREETER_PREFERENCES: root.preferencesPath
      })
    stdout: StdioCollector {
      onStreamFinished: root.applyModel(text)
    }
    onExited: {
      if (root.reloadPending)
        reloadTimer.restart();
    }
  }
  FileView {
    path: root.stateDirectory + "/sync.toml"
    watchChanges: true
    printErrors: false
    onFileChanged: {
      reload();
      root.reload();
    }
  }
  FileView {
    path: root.preferencesPath
    watchChanges: true
    printErrors: false
    onFileChanged: {
      reload();
      root.reload();
    }
  }
  FileView {
    path: root.stateDirectory + "/greeter.toml"
    watchChanges: true
    printErrors: false
    onFileChanged: {
      reload();
      root.reload();
    }
  }
  Process {
    id: powerProcess
    onExited: (code, status) => {
      if (code !== 0) {
        root.message = "No se pudo completar la acción de energía.";
        root.messageIsError = true;
      }
    }
  }
  Connections {
    target: Greetd
    function onAuthMessage(message, error, responseRequired, echoResponse) {
      if (responseRequired) {
        if (root.hasPendingResponse && !echoResponse) {
          const response = root.pendingResponse;
          root.clearSecret();
          Greetd.respond(response);
        } else {
          root.clearSecret();
          root.prompt = message || "Respuesta";
          root.echoResponse = echoResponse;
          root.awaitingResponse = true;
          root.busy = false;
        }
      } else {
        root.message = message;
        root.messageIsError = error;
      }
    }
    function onAuthFailure(message) {
      root.failure("No se pudo autenticar. Comprueba tus datos e inténtalo de nuevo.");
    }
    function onError(error) {
      root.failure("No se pudo completar el inicio de sesión. Vuelve a intentarlo.");
    }
    function onReadyToLaunch() {
      root.clearSecret();
      if (!root.loginSession) {
        root.cancel();
        return;
      }
      root.busy = true;
      root.message = "Iniciando " + root.loginSession.name + "…";
      Greetd.launch(root.loginSession.command, root.loginSession.environment);
    }
  }
  Component.onCompleted: reload()
}
