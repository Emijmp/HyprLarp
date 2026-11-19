import QtQuick
import QtQuick.Layouts
import "../core"
import "../core/performance.js" as Performance

ColumnLayout {
  id: root
  property string title: ""
  property string metric: "cpuPercent"
  property string unit: "%"
  property var samples: []
  property color lineColor: Theme.accent
  property color gridColor: Theme.separator
  readonly property real maximum: Math.max(metric === "cpuPercent" ? 1 : 16, ...samples.map(item => typeof item[metric] === "number" ? item[metric] * 1.15 : 0))
  Layout.fillWidth: true
  spacing: 6
  RowLayout {
    Layout.fillWidth: true
    Label {
      text: root.title
      Layout.fillWidth: true
    }
    Label {
      text: "0–" + Performance.format(root.maximum, root.unit, root.metric === "cpuPercent" ? 1 : 0)
      color: Theme.muted
      font.family: Theme.mono
      font.pixelSize: Theme.fontPx(10)
    }
  }
  Canvas {
    id: chart
    Layout.fillWidth: true
    Layout.preferredHeight: Theme.px(74)
    Accessible.ignored: true
    onWidthChanged: requestPaint()
    onHeightChanged: requestPaint()
    onPaint: {
      const context = getContext("2d");
      context.reset();
      context.strokeStyle = root.gridColor;
      context.lineWidth = 1;
      for (const y of [1, height / 2, height - 1]) {
        context.beginPath();
        context.moveTo(0, y);
        context.lineTo(width, y);
        context.stroke();
      }
      if (root.samples.length < 2)
        return;
      const start = root.samples[0].time;
      const span = Math.max(.001, root.samples[root.samples.length - 1].time - start);
      context.strokeStyle = root.lineColor;
      context.lineWidth = 2;
      context.beginPath();
      let previous = false;
      for (const sample of root.samples) {
        const value = sample[root.metric];
        if (!Performance.numeric(value)) {
          previous = false;
          continue;
        }
        const x = (sample.time - start) / span * width;
        const y = height - 2 - Math.min(1, Math.max(0, value / root.maximum)) * (height - 4);
        if (previous)
          context.lineTo(x, y);
        else
          context.moveTo(x, y);
        previous = true;
      }
      context.stroke();
    }
  }
  onSamplesChanged: chart.requestPaint()
  onLineColorChanged: chart.requestPaint()
  onGridColorChanged: chart.requestPaint()
}
