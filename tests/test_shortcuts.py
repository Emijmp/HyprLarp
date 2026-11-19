import copy
import importlib.machinery
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from backend.service import DEFAULTS, ROOT, Service, Store, generate_bindings, validate_setting
from backend.shortcuts import invocation, lua_value, validate_custom
from backend.layouts import section_updates


def binding(**updates):
  return {"id": "custom-test", "name": "Terminal", "chord": "SUPER CTRL, T", "type": "command", "command": "kitty", **updates}


class ShortcutTests(unittest.TestCase):
  def test_capture_modes_have_distinct_default_keys_and_direct_commands(self):
    self.assertEqual(DEFAULTS["shortcuts"]["screenshot-region"], ", Print")
    self.assertEqual(DEFAULTS["shortcuts"]["screenshot-region-frozen"], "CTRL, Print")
    self.assertEqual(DEFAULTS["shortcuts"]["screenshot-screen"], "SHIFT, Print")
    generated = generate_bindings(DEFAULTS, Path("/tmp/a shell/hyprlarp"))
    self.assertIn("screenshot-region-frozen", generated)
    self.assertNotIn("toggle screenshot-", generated)
    self.assertEqual(invocation("screenshot-region-frozen", Path("/tmp/a shell/hyprlarp")), "'/tmp/a shell/hyprlarp' screenshot-region-frozen")
    self.assertEqual(invocation("screenshot-window", Path("/tmp/hyprlarp")), "/tmp/hyprlarp screenshot-window")

  def test_capture_cli_preserves_dynamic_ipc_and_routes_frozen_modes(self):
    loader = importlib.machinery.SourceFileLoader("hyprlarp_capture_cli_test", str(ROOT / "bin/hyprlarp"))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    cases = [(["screenshot-region"], "capture", "region"),
      (["screenshot-screen"], "capture", "screen"),
      (["screenshot-window"], "capture", "window"),
      (["screenshot-region-frozen"], "captureFrozen", "region"),
      (["screenshot-region", "--freeze"], "captureFrozen", "region"),
      (["screenshot-window", "--freeze"], "captureFrozen", "window"),
      (["screenshot-screen", "--freeze"], "captureFrozen", "screen")]
    for arguments, method, mode in cases:
      with self.subTest(arguments=arguments), patch("sys.argv", ["hyprlarp", *arguments]), \
          patch.object(module, "runtime", return_value="qs"), patch.object(module, "ipc", return_value=True) as ipc:
        self.assertEqual(module.main(), 0)
        ipc.assert_called_once_with("qs", method, mode)
    with patch("sys.argv", ["hyprlarp", "settings", "--freeze"]), patch("sys.stderr", new=io.StringIO()), \
        patch.object(module, "runtime") as runtime, self.assertRaises(SystemExit) as error:
      module.main()
    self.assertEqual(error.exception.code, 2)
    runtime.assert_not_called()

  def test_personal_layout_preserves_noctalia_combinations_and_scratchpad(self):
    self.assertEqual(DEFAULTS["shortcuts"]["control"], "SUPER, M")
    self.assertEqual(DEFAULTS["shortcuts"]["settings"], "SUPER, comma")
    self.assertEqual(DEFAULTS["shortcuts"]["session"], "SUPER, X")
    self.assertNotIn("SUPER SHIFT, S", DEFAULTS["shortcuts"].values())
    generated = generate_bindings(DEFAULTS, ROOT / "bin/hyprlarp")
    self.assertNotIn("hl.unbind", generated)
    self.assertNotIn("workspace = ", generated)

  def test_custom_binds_validate_types_limits_sources_and_commands(self):
    for values in [[binding(id="../bad")], [binding(command="echo safe\nshutdown now")], [binding(type="lua")], [binding(type="inherit")], [binding(name="")], [binding(locked="true")], [binding(action=[])], [binding(chord="HYPER, A")], [binding(), binding()], [binding(source="|SUPER,T"), binding(id="other", source="|SUPER,T")]]:
      with self.subTest(values=values), self.assertRaises(ValueError):
        validate_setting("customBindings", values)
    normalized = validate_setting("customBindings", [binding(chord="MOD4 CTRL, mouse:272")])
    self.assertEqual(normalized[0]["chord"], "CTRL SUPER, mouse:272")
    self.assertEqual(normalized[0]["enabled"], True)

  def test_cross_list_duplicates_are_atomic_and_disabled_binds_can_be_retained(self):
    with tempfile.TemporaryDirectory() as temporary:
      store = Store(Path(temporary))
      original = copy.deepcopy(store.settings)
      with self.assertRaises(ValueError):
        store.update({"customBindings": [binding(chord="MOD4, SPACE")]})
      self.assertEqual(store.settings, original)
      store.update({"customBindings": [binding(chord="MOD4, SPACE", enabled=False)]})
      self.assertEqual(len(Store(Path(temporary)).settings["customBindings"]), 1)

  def test_custom_binds_undo_redo_and_section_reset(self):
    with tempfile.TemporaryDirectory() as temporary:
      store = Store(Path(temporary))
      store.update({"customBindings": [binding()]})
      store.undo()
      self.assertEqual(store.settings["customBindings"], [])
      store.redo()
      self.assertEqual(store.settings["customBindings"][0]["command"], "kitty")
      store.update(section_updates("Shortcuts", DEFAULTS, store.settings))
      self.assertEqual(store.settings["customBindings"], [])
      store.undo()
      self.assertEqual(len(store.settings["customBindings"]), 1)

  def test_apply_requires_configuration_and_ready_integration(self):
    with tempfile.TemporaryDirectory() as temporary:
      service = Service(Store(Path(temporary)))
      self.addCleanup(service.executor.shutdown, wait=True)
      events = []
      service.emit = lambda kind, data: events.append((kind, data))
      with patch("backend.service.command") as command:
        service.action({"action": "apply-shortcuts", "source": "shell"})
        command.assert_not_called()
      service.configuration_focused = True
      with patch.object(service, "shortcut_state", return_value={"available": False}):
        service.action({"action": "apply-shortcuts", "source": "config"})
      self.assertFalse((Path(temporary) / "bindings.lua").exists())
      self.assertEqual(sum(kind == "error" for kind, _ in events), 2)

  def test_failed_reload_restores_previous_owned_bindings(self):
    with tempfile.TemporaryDirectory() as temporary:
      service = Service(Store(Path(temporary)))
      self.addCleanup(service.executor.shutdown, wait=True)
      service.configuration_focused = True
      service.emit = lambda *args: None
      filename = Path(temporary) / "bindings.lua"
      filename.write_text("previous")
      with patch.object(service, "shortcut_state", return_value={"available": True}), patch("backend.service.command", side_effect=RuntimeError("reload failed")):
        service.action({"action": "apply-shortcuts", "source": "config"})
      self.assertEqual(filename.read_text(), "previous")


@unittest.skipUnless(shutil.which("Hyprland"), "Hyprland native Lua verifier is optional")
class NativeShortcutTests(unittest.TestCase):
  def run_lua(self, body, settings=None):
    with tempfile.TemporaryDirectory(prefix="hyprlarp-native-binds-") as temporary:
      folder = Path(temporary)
      compiled = folder / "bindings.lua"
      compiled.write_text(generate_bindings(settings or DEFAULTS, Path("/tmp/path with 'quote'/hyprlarp")))
      script = folder / "verify.lua"
      source = 'local manager=dofile(' + lua_value(str(ROOT / "config/bindings-runtime.lua")) + ')\nmanager.begin()\n'
      source += body.replace("APPLY()", "dofile(" + lua_value(str(compiled)) + ")")
      script.write_text(source)
      result = subprocess.run(["Hyprland", "--verify-config", "--config", str(script)], capture_output=True, text=True, timeout=10)
      self.assertEqual(result.returncode, 0, result.stdout[-1500:] + result.stderr[-2500:])
      self.assertIn("config ok", result.stdout)
      return result.stdout

  def empty_settings(self):
    settings = copy.deepcopy(DEFAULTS)
    settings["shortcuts"] = {key: "" for key in settings["shortcuts"]}
    settings["migrateNoctaliaBinds"] = False
    return settings

  def test_native_external_handlers_workspace_loops_and_submaps_are_preserved(self):
    self.run_lua('''
local protected=hl.bind("SUPER + SHIFT + S",function() end)
local collision=hl.bind("SUPER + C",hl.dsp.exec_cmd("kitty"))
local numbers={}
for index=1,10 do numbers[index]=hl.bind("SUPER + " .. (index % 10),function() end) end
local other
hl.define_submap("resize",function() other=hl.bind("SUPER + C",function() end) end)
APPLY()
assert(protected:is_enabled())
assert(collision:is_enabled())
assert(other:is_enabled())
for _,item in ipairs(numbers) do assert(item:is_enabled()) end
assert(#manager.conflicts==1)
APPLY()
assert(protected:is_enabled() and collision:is_enabled() and other:is_enabled())
''')

  def test_native_session_shortcut_replaces_only_the_noctalia_session_handler(self):
    settings = self.empty_settings()
    settings['shortcuts']['session'] = 'SUPER, X'
    settings['migrateNoctaliaBinds'] = True
    self.run_lua('''
local original=hl.bind("SUPER+X",hl.dsp.exec_cmd("noctalia msg panel-toggle session"))
local terminal=hl.bind("SUPER+T",function() end)
local scratchpad=hl.bind("SUPER+SHIFT+S",function() end)
APPLY()
assert(not original:is_enabled())
assert(terminal:is_enabled() and scratchpad:is_enabled())
assert(#manager.owned==1 and #manager.conflicts==0)
assert(manager.owned[1]:is_enabled())
assert(manager.owned[1].key:upper()=="X" and manager.owned[1].modmask==64)
''', settings)

  def test_native_inherit_keeps_both_press_and_release_callbacks(self):
    settings = self.empty_settings()
    settings["customBindings"] = validate_custom([binding(type="inherit", source="|SUPER,T", chord="SUPER CTRL, T")], DEFAULTS["shortcuts"])
    self.run_lua('''
local original=hl.bind("SUPER+T",function() end,{repeating=true,locked=true})
local release=hl.bind("SUPER+T",function() end,{release=true})
APPLY()
assert(not original:is_enabled() and not release:is_enabled())
assert(#manager.owned==2)
assert(manager.owned[1].repeating and manager.owned[1].locked)
assert(manager.owned[2].release)
manager.apply({}, {}, false, {})
assert(original:is_enabled() and release:is_enabled())
''', settings)

  def test_native_disable_delete_and_replace_restore_the_original(self):
    settings = self.empty_settings()
    settings["customBindings"] = validate_custom([binding(type="inherit", source="|SUPER,T", enabled=False)], DEFAULTS["shortcuts"])
    self.run_lua('''
local original=hl.bind("SUPER + T",function() end)
APPLY()
assert(not original:is_enabled() and #manager.owned==0)
manager.apply({}, {}, false, {})
assert(original:is_enabled())
''', settings)
    settings["customBindings"] = validate_custom([binding(chord="SUPER, T", replace=True)], DEFAULTS["shortcuts"])
    self.run_lua('''
local original=hl.bind("SUPER + T",function() end)
local other
hl.define_submap("other",function() other=hl.bind("SUPER + T",function() end) end)
APPLY()
assert(not original:is_enabled() and other:is_enabled())
manager.apply({}, {}, false, {})
assert(original:is_enabled() and other:is_enabled())
''', settings)

  def test_native_inherit_in_submap_preserves_other_submap_entries(self):
    settings = self.empty_settings()
    settings["customBindings"] = validate_custom([binding(type="inherit", source="resize|SUPER,T")], DEFAULTS["shortcuts"])
    self.run_lua('''
local original, other
hl.define_submap("resize",function()
  original=hl.bind("SUPER+T",function() end)
  other=hl.bind("SUPER+W",function() end)
end)
APPLY()
assert(not original:is_enabled() and other:is_enabled())
assert(manager.owned[1].submap=="resize")
''', settings)

  def test_native_noctalia_transfer_keeps_combinations_and_translates_callback_commands(self):
    output = self.run_lua('''
local original=hl.bind("SUPER+M",hl.dsp.exec_cmd("noctalia msg panel-toggle control-center"))
local settings=hl.bind("SUPER+comma",hl.dsp.exec_cmd("noctalia msg settings-toggle"))
local tab=hl.bind("ALT+Tab",hl.dsp.exec_cmd("noctalia msg window-switcher"))
local media=hl.bind("XF86AudioRaiseVolume",function() hl.dispatch(hl.dsp.exec_cmd("noctalia msg volume-up")) end,{repeating=true})
APPLY()
assert(not original:is_enabled() and not settings:is_enabled() and not tab:is_enabled())
assert(media:is_enabled())
local translated=hl.dsp.exec_cmd("noctalia msg volume-up")
assert(type(translated)=="userdata")
local actual
manager.nativeExec=function(command) actual=command; return function() end end
hl.dispatch=function(handler) assert(type(handler)=="function") end
manager.records[4].handler()
assert(actual=="wpctl set-volume -l 1 @DEFAULT_AUDIO_SINK@ 5%+")
print("SNAPSHOT",manager.snapshot())
''')
    marker = output.index('SNAPSHOT\t') + len('SNAPSHOT\t')
    snapshot = json.loads(output[marker:].splitlines()[0])
    self.assertTrue(snapshot["available"])
    self.assertEqual(len(snapshot["bindings"]), 4)

  def test_native_command_quotes_cannot_escape_the_generated_lua(self):
    settings = self.empty_settings()
    settings["customBindings"] = [binding(command='\"); error("injected Lua"); --')]
    self.run_lua('APPLY()\nassert(#manager.owned==1)\n', settings)

  def test_native_stop_restores_handlers_and_original_factories(self):
    settings = self.empty_settings()
    settings["customBindings"] = [binding(chord="SUPER, T", replace=True)]
    self.run_lua('''
local original=hl.bind("SUPER+T",function() end)
APPLY()
assert(not original:is_enabled())
manager.stop()
assert(original:is_enabled())
assert(hl.bind==manager.nativeBind and hl.dsp.exec_cmd==manager.nativeExec)
assert(HyprLarpBinds==nil)
''', settings)
