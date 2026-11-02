import QtQuick
import "../core"

Text {
  color: Theme.text
  font.family: Theme.font
  font.pixelSize: 12
  renderType: Text.NativeRendering
  textFormat: Text.PlainText
  elide: Text.ElideRight
  verticalAlignment: Text.AlignVCenter
}
