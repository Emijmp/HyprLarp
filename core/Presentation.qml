pragma Singleton
import QtQuick
import Quickshell

Singleton {
  property bool active: false
  function toggle() {
    active = !active;
  }
}
