import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import "../core"
import "../components"
import "../core/performance.js" as Performance

ColumnLayout {
  id: root
  objectName: "performance-panel"
  spacing: 12
  readonly property var performanceState: Bridge.performance
  readonly property var current: root.performanceState.current || ({})
  readonly property var history: (root.performanceState.history || []).slice().reverse()
  readonly property var screenContext: Quickshell.screens.map(screen => ({
        name: screen.name,
        width: screen.width,
        height: screen.height
      }))
  readonly property bool recording: !!root.performanceState.recording
  property string seconds: "15"
  property string firstId: ""
  property string secondId: ""
  property string latestId: ""
  property string historyQuery: ""
  property bool compact: false
  readonly property var filteredHistory: history.filter(item => (item.label + " " + item.revision + " " + new Date(item.createdAt).toLocaleDateString()).toLowerCase().includes(historyQuery.trim().toLowerCase()))
  readonly property int recentFaults: {
    const now = Math.max(Clock.date.getTime(), Date.now());
    return Bridge.faults.reduce((total, item) => total + (item.events || []).filter(stamp => {
        const milliseconds = stamp * 1000;
        return milliseconds <= now && now - milliseconds <= 300000;
      }).length, 0);
  }
  readonly property var first: filteredHistory.find(item => item.id === firstId) || null
  readonly property var second: filteredHistory.find(item => item.id === secondId) || null
  readonly property var comparison: Performance.compare(first, second)
  function context() {
    if (Bridge.ready)
      Bridge.send("performance-context", {
        screens: screenContext
      });
  }
  function copyCsv(report) {
    if (!report)
      return;
    const quote = value => '"' + String(value ?? "").replaceAll('"', '""') + '"';
    const rows = [["nombre", "fecha", "revision", "modo", "duracion_s", "muestras", "cpu_media_pct", "rss_final_mib", "rss_pico_mib", "pss_final_mib", "arranque_ms"], [report.label, new Date(report.createdAt).toISOString(), report.revision, report.context.mode, report.summary.seconds, report.summary.samples, report.summary.cpuPercent, report.summary.rssMiB, report.summary.peakRssMiB, report.summary.pssMiB, report.startupMs]];
    Quickshell.clipboardText = rows.map(row => row.map(quote).join(",")).join("\n");
    Bridge.toast("Informe CSV copiado", false);
  }
  onScreenContextChanged: context()
  Component.onCompleted: context()
  Connections {
    target: Bridge
    function onActionFinished(action) {
      if (action === "performance-ready")
        root.context();
    }
  }
  IpcHandler {
    target: "performance"
    function status(): string {
      return JSON.stringify(root.performanceState);
    }
  }
  onFilteredHistoryChanged: {
    if (!filteredHistory.some(item => item.id === firstId))
      firstId = filteredHistory[Math.min(1, filteredHistory.length - 1)]?.id || "";
    const latest = filteredHistory[0]?.id || "";
    if (latest !== latestId) {
      secondId = latest;
      latestId = latest;
    } else if (!filteredHistory.some(item => item.id === secondId))
      secondId = filteredHistory[0]?.id || "";
  }
  Label {
    objectName: "performance-mode"
    Layout.fillWidth: true
    color: Theme.muted
    text: ({
        native: "Sesión real",
        preview: "Vista previa · medición aislada",
        "settings-only": "Configuración independiente"
      })[root.performanceState.mode] || "Preparando medición…"
  }
  Label {
    Layout.fillWidth: true
    wrapMode: Text.WordWrap
    text: "Interfaz, backend y supervisor de HyprLarp. Las aplicaciones abiertas y hyprlock quedan fuera de esta medición."
    color: Theme.muted
    font.pixelSize: Theme.fontPx(11)
  }
  Flow {
    Layout.fillWidth: true
    spacing: 8
    ActionButton {
      text: root.compact ? "Vista completa" : "Vista compacta"
      onClicked: root.compact = !root.compact
    }
    Label {
      objectName: "performance-stability"
      text: root.recentFaults ? "Fallos de módulos · últimos 5 min: " + root.recentFaults : "Sin fallos de módulos · últimos 5 min"
      color: root.recentFaults ? Theme.danger : Theme.muted
      font.pixelSize: Theme.fontPx(10)
      height: Theme.controlHeight(30)
      Accessible.name: text
    }
  }
  Flow {
    Layout.fillWidth: true
    spacing: 8
    ActionButton {
      objectName: "performance-pause"
      text: root.performanceState.paused ? "Reanudar" : "Pausar"
      enabled: !root.recording
      onClicked: Bridge.perform("performance-pause", {
        paused: !root.performanceState.paused
      })
    }
    ActionButton {
      text: "Actualizar"
      enabled: !root.recording
      onClicked: Bridge.perform("performance-refresh")
    }
    Label {
      text: root.performanceState.paused ? "Muestreo pausado" : "Cada 2 s · solo con este panel abierto"
      color: Theme.muted
      font.pixelSize: Theme.fontPx(10)
      height: Theme.controlHeight(30)
    }
  }
  GridLayout {
    Layout.fillWidth: true
    columns: root.width < Theme.px(440) ? 1 : 2
    columnSpacing: Theme.px(24)
    uniformCellWidths: true
    ColumnLayout {
      Layout.fillWidth: true
      Label {
        text: "CPU · un núcleo"
        Layout.fillWidth: true
        color: Theme.muted
        font.pixelSize: Theme.fontPx(11)
      }
      Label {
        objectName: "performance-cpu"
        Layout.fillWidth: true
        text: Performance.format(root.current.cpuPercent, "%", 2)
        color: Number.isFinite(root.current.cpuPercent) && root.current.cpuPercent >= (root.performanceState.thresholds?.cpuPercent ?? 80) ? Theme.danger : Theme.text
        font.pixelSize: Theme.fontPx(25)
        font.family: Theme.mono
      }
    }
    ColumnLayout {
      Layout.fillWidth: true
      Label {
        text: "Memoria · RSS"
        Layout.fillWidth: true
        color: Theme.muted
        font.pixelSize: Theme.fontPx(11)
      }
      Label {
        text: Performance.format(root.current.rssMiB, " MiB", 1)
        Layout.fillWidth: true
        color: Number.isFinite(root.current.rssMiB) && root.current.rssMiB >= (root.performanceState.thresholds?.rssMiB ?? 1024) ? Theme.danger : Theme.text
        font.pixelSize: Theme.fontPx(25)
        font.family: Theme.mono
      }
    }
  }
  ValueRow {
    title: "Memoria · PSS"
    value: Performance.format(root.current.pssMiB, " MiB", 1)
  }
  ValueRow {
    title: "Procesos / hilos"
    value: root.current.processes !== undefined ? root.current.processes + " / " + root.current.threads : "N/D"
  }
  PerformanceChart {
    title: "CPU · muestras recientes"
    samples: root.performanceState.samples || []
    visible: !root.compact
  }
  PerformanceChart {
    title: "Memoria · muestras recientes"
    metric: "rssMiB"
    unit: " MiB"
    samples: root.performanceState.samples || []
    visible: !root.compact
  }
  Label {
    Layout.fillWidth: true
    wrapMode: Text.WordWrap
    objectName: "performance-note"
    text: "100% de CPU equivale a un núcleo. RSS incluye páginas compartidas; PSS las reparte entre procesos y se actualiza cada 8 s. Los valores pequeños pueden quedar por debajo de la resolución del contador (" + Performance.format(root.performanceState.cpuTickMs, " ms", 0) + ")."
    color: Theme.muted
    font.pixelSize: Theme.fontPx(10)
  }
  SectionTitle {
    text: "Procesos de HyprLarp"
    visible: !root.compact
  }
  Repeater {
    model: root.compact ? [] : root.current.parts || []
    ColumnLayout {
      required property var modelData
      Layout.fillWidth: true
      Label {
        text: ({
            interface: "Interfaz · Quickshell",
            backend: "Backend",
            supervisor: "Supervisor"
          })[modelData.role] || modelData.role
        Layout.fillWidth: true
      }
      Label {
        text: "CPU " + Performance.format(modelData.cpuPercent, "%", 2) + " · RSS " + Performance.format(modelData.rssMiB, " MiB", 1) + " · PID " + modelData.pid
        color: Theme.muted
        font.pixelSize: Theme.fontPx(10)
        Layout.fillWidth: true
        wrapMode: Text.WordWrap
      }
    }
  }
  Rule {}
  SectionTitle {
    text: "Arranque y carga"
  }
  ValueRow {
    title: "Interfaz lista"
    value: Performance.duration(root.performanceState.startup?.readyMs)
  }
  ValueRow {
    title: "Revisión del paquete"
    value: root.performanceState.revision || "Identificando…"
  }
  Label {
    Layout.fillWidth: true
    wrapMode: Text.WordWrap
    text: "El arranque se mide desde que inicia Quickshell hasta que la interfaz recibe la configuración del backend. La carga de paneles termina cuando su componente está listo; estas cifras no miden el primer fotograma ni los FPS."
    color: Theme.muted
    font.pixelSize: Theme.fontPx(10)
  }
  Repeater {
    model: root.compact ? [] : (root.performanceState.panelLoads || []).slice().reverse().slice(0, 5)
    ValueRow {
      required property var modelData
      title: "Carga · " + modelData.name
      value: Performance.duration(modelData.milliseconds)
    }
  }
  SectionTitle {
    text: "Avisos de consumo"
  }
  Label {
    Layout.fillWidth: true
    wrapMode: Text.WordWrap
    text: "Se resaltan los valores actuales por encima de estos límites."
    color: Theme.muted
    font.pixelSize: Theme.fontPx(10)
  }
  Flow {
    Layout.fillWidth: true
    spacing: 10
    ColumnLayout {
      Label {
        text: "CPU · % de un núcleo"
        color: Theme.muted
        font.pixelSize: Theme.fontPx(10)
      }
      Field {
        id: cpuThreshold
        text: String(root.performanceState.thresholds?.cpuPercent ?? 80)
        validator: DoubleValidator {
          bottom: 1
          top: 1000
          decimals: 1
        }
        Accessible.name: "Umbral de CPU en porcentaje"
        onAccepted: Bridge.perform("performance-thresholds", {
          cpuPercent: Number(text),
          rssMiB: Number(ramThreshold.text)
        })
      }
    }
    ColumnLayout {
      Label {
        text: "Memoria · MiB RSS"
        color: Theme.muted
        font.pixelSize: Theme.fontPx(10)
      }
      Field {
        id: ramThreshold
        text: String(root.performanceState.thresholds?.rssMiB ?? 1024)
        validator: DoubleValidator {
          bottom: 64
          top: 1048576
          decimals: 0
        }
        Accessible.name: "Umbral de memoria RSS en MiB"
        onAccepted: Bridge.perform("performance-thresholds", {
          cpuPercent: Number(cpuThreshold.text),
          rssMiB: Number(text)
        })
      }
    }
  }
  Rule {}
  SectionTitle {
    text: "Guardar una medición"
  }
  Field {
    id: label
    objectName: "performance-label"
    placeholderText: "Nombre de la medición (opcional)"
    Accessible.name: "Nombre de la medición"
    maximumLength: 64
    Layout.fillWidth: true
  }
  Selection {
    Accessible.name: "Duración de la medición"
    choices: ["15", "30", "60"]
    labels: ["15 segundos", "30 segundos", "60 segundos"]
    value: root.seconds
    enabled: !root.recording
    Layout.fillWidth: true
    onEdited: value => root.seconds = value
  }
  Flow {
    Layout.fillWidth: true
    spacing: 8
    ActionButton {
      objectName: "performance-record"
      text: root.recording ? "Midiendo…" : "Medir " + root.seconds + " s"
      enabled: !root.recording && !root.performanceState.paused && root.current.processes !== undefined
      onClicked: Bridge.perform("performance-record", {
        label: label.text,
        seconds: Number(root.seconds)
      })
    }
    ActionButton {
      text: "Cancelar medición"
      visible: root.recording
      onClicked: Bridge.perform("performance-cancel")
    }
  }
  StatMeter {
    visible: root.recording
    title: "Medición en curso"
    value: 100 * (root.performanceState.recording?.progress || 0)
    detail: Performance.format(root.performanceState.recording?.elapsed, " s", 0) + " / " + (root.performanceState.recording?.seconds || 0) + " s"
  }
  StatusMessage {
    visible: !!root.performanceState.error
    text: root.performanceState.error || ""
    error: true
  }
  StatusMessage {
    visible: !!root.performanceState.notice
    text: root.performanceState.notice || ""
  }
  Label {
    Layout.fillWidth: true
    wrapMode: Text.WordWrap
    text: "Las mediciones incluyen el coste de mantener este panel abierto. Se guardan las últimas 20. Cerrar el panel cancela la medición en curso."
    color: Theme.muted
    font.pixelSize: Theme.fontPx(10)
  }
  Rule {}
  SectionTitle {
    objectName: "performance-history"
    text: "Historial y comparación"
  }
  Field {
    placeholderText: "Buscar por nombre, fecha o revisión"
    Accessible.name: "Buscar mediciones guardadas"
    Layout.fillWidth: true
    text: root.historyQuery
    onTextEdited: root.historyQuery = text
  }
  EmptyState {
    visible: !root.filteredHistory.length
    title: root.history.length ? "No hay coincidencias" : "Aún no hay mediciones"
    description: root.history.length ? "Prueba con otro nombre, fecha o revisión." : "Guarda una para conservar su revisión y sus resultados."
  }
  ColumnLayout {
    visible: root.filteredHistory.length > 0
    Layout.fillWidth: true
    Label {
      text: "Referencia · A"
      color: Theme.muted
    }
    Selection {
      Accessible.name: "Medición de referencia A"
      Layout.fillWidth: true
      choices: root.filteredHistory.map(item => item.id)
      labels: root.filteredHistory.map(item => Performance.reportLabel(item))
      value: root.firstId
      onEdited: value => root.firstId = value
    }
    Label {
      text: "Comparar con · B"
      color: Theme.muted
    }
    Selection {
      Accessible.name: "Medición a comparar B"
      Layout.fillWidth: true
      choices: root.filteredHistory.map(item => item.id)
      labels: root.filteredHistory.map(item => Performance.reportLabel(item))
      value: root.secondId
      onEdited: value => root.secondId = value
    }
    Repeater {
      model: [root.first, root.second].filter((item, index) => item && (index === 0 || item.id !== root.first?.id))
      ColumnLayout {
        required property var modelData
        Layout.fillWidth: true
        Label {
          text: (modelData.id === root.firstId ? "A · " : "B · ") + modelData.label + " · revisión " + modelData.revision
          Layout.fillWidth: true
          wrapMode: Text.WordWrap
        }
        ValueRow {
          title: "Duración / muestras"
          value: Performance.format(modelData.summary.seconds, " s", 1) + " / " + modelData.summary.samples
        }
        ValueRow {
          title: "CPU media"
          value: Performance.format(modelData.summary.cpuPercent, "%", 2)
        }
        ValueRow {
          title: "RSS final / pico"
          value: Performance.format(modelData.summary.rssMiB, "", 1) + " / " + Performance.format(modelData.summary.peakRssMiB, " MiB", 1)
        }
        ValueRow {
          title: "PSS final"
          value: Performance.format(modelData.summary.pssMiB, " MiB", 1)
        }
      }
    }
    Label {
      visible: !root.comparison.compatible
      text: root.comparison.reason || ""
      color: Theme.muted
      Layout.fillWidth: true
      wrapMode: Text.WordWrap
    }
    ColumnLayout {
      visible: root.comparison.compatible
      Layout.fillWidth: true
      SectionTitle {
        text: "Diferencia · A → B"
      }
      ValueRow {
        title: "CPU media"
        value: Performance.signed(root.comparison.cpu, " puntos", 2)
      }
      ValueRow {
        title: "RSS final"
        value: Performance.signed(root.comparison.rss, " MiB", 1)
      }
      ValueRow {
        title: "PSS final"
        value: Performance.signed(root.comparison.pss, " MiB", 1)
      }
      ValueRow {
        title: "Arranque"
        value: Performance.signed(root.comparison.startup, " ms", 0)
      }
      Label {
        text: "Mismo modo, configuración y pantallas; la carga del sistema puede variar entre mediciones."
        color: Theme.muted
        Layout.fillWidth: true
        wrapMode: Text.WordWrap
        font.pixelSize: Theme.fontPx(10)
      }
    }
    Flow {
      Layout.fillWidth: true
      spacing: 8
      ActionButton {
        text: "Copiar informe B"
        enabled: !!root.second
        onClicked: {
          Quickshell.clipboardText = JSON.stringify(root.second, null, 2);
          Bridge.toast("Informe de rendimiento copiado", false);
        }
      }
      ActionButton {
        text: "Copiar CSV B"
        enabled: !!root.second
        onClicked: root.copyCsv(root.second)
      }
      ActionButton {
        text: "Eliminar medición B"
        enabled: !!root.second
        onClicked: Bridge.perform("performance-delete", {
          id: root.secondId
        })
      }
    }
  }
}
