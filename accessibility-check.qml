//@ pragma UseQApplication
//@ pragma Env QT_QUICK_CONTROLS_STYLE=Basic
//@ pragma Env QT_LINUX_ACCESSIBILITY_ALWAYS_ON=1
import Quickshell
import "tools"

ShellRoot {
  AccessibilityChecks {
    onCompleted: if (Quickshell.env("HYPRLARP_A11Y_HOLD") !== "1")
      Qt.quit()
  }
}
